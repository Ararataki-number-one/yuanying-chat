"""Production context regression with an Android 12 callback-forwarding model.

The host model is not Android execution. The separate API test compiles the
actual wrapper classes against the pinned real Android 35 API jar.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'
JAVA_HOME = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')
ANDROID35 = Path('/workspace/yuanying-chat/work/cloud-setup/platform/android-35/android.jar')
NAMES = ('GeckoEnvironmentContext.java', 'ProfileContext.java', 'EnvironmentProcessPolicy.java',
         'Profiles.java', 'PocketApplication.java')
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def java_tools():
    selected_java = os.environ.get('PROFILE_JAVA')
    javac = Path(os.environ.get('PROFILE_JAVAC') or (Path(selected_java).with_name('javac') if selected_java else None)
                 or shutil.which('javac') or Path(os.environ.get('JAVA_HOME', JAVA_HOME)) / 'bin/javac')
    java = Path(os.environ.get('PROFILE_JAVA') or javac.with_name('java'))
    if not javac.is_file() or not java.is_file():
        raise RuntimeError('JDK 17 java/javac required for actual host execution')
    return javac, java


def application_adapter():
    """Keep real cache and application-context methods; omit unrelated startup."""
    raw = (PRODUCTION / 'PocketApplication.java').read_text()
    cache = re.findall(r'^  final Context\[\] profiles=.*$', raw, re.M)
    profile = re.findall(r'^  synchronized Context profile\(int id\).*$', raw, re.M)
    application = re.findall(r'^  @Override public Context getApplicationContext\(\).*$', raw, re.M)
    if not all(len(values) == 1 for values in (cache, profile, application)):
        raise AssertionError('Production Application ownership methods changed; review the host boundary')
    return ('package local.pocketchat; import android.content.Context;\n'
            'class PocketApplication extends android.app.Application {\n'
            + '\n'.join(cache + profile + application) + '\n}\n')


def profile_helpers():
    """Compile unchanged production MAX/processSlot/slot/global/context methods."""
    raw = (PRODUCTION / 'Profiles.java').read_text()
    boundary = '  static Class<?> activity(int id)'
    if raw.count(boundary) != 1:
        raise AssertionError('Production profile helper boundary changed')
    return raw[:raw.index(boundary)] + '}\n'


def materialize(directory, wrapper=None, host=False, profile=None):
    for name in ('GeckoEnvironmentContext.java', 'ProfileContext.java', 'EnvironmentProcessPolicy.java'):
        actual = wrapper if name == 'GeckoEnvironmentContext.java' else profile if name == 'ProfileContext.java' else None
        (directory / name).write_text(actual if actual is not None else (PRODUCTION / name).read_text())
    (directory / 'Profiles.java').write_text(profile_helpers())
    (directory / 'PocketApplication.java').write_text(application_adapter())
    if host:
        for name, text in MODEL.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (directory / 'CallbackHost.java').write_text(HOST)


def compile_java(directory, android=None):
    javac, _ = java_tools()
    command = [str(javac), '-encoding', 'UTF-8', '-d', str(directory / 'classes')]
    if android is not None:
        command += ['-cp', str(android)]
    command += [str(path) for path in sorted(directory.rglob('*.java'))]
    return subprocess.run(command, capture_output=True, text=True, timeout=45)


class GeckoContextCallbacks(unittest.TestCase):
    reports = []

    def execute(self, wrapper=None, mode='current', profile=None):
        _, java = java_tools()
        before = {name: SHA((PRODUCTION / name).read_bytes()) for name in NAMES}
        with tempfile.TemporaryDirectory(prefix='profile-context-callbacks-') as temporary:
            directory = Path(temporary)
            materialize(directory, wrapper, host=True, profile=profile)
            compiled = compile_java(directory)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(java), '-Xss256k', '-Djava.io.tmpdir=' + str(directory / 'model-data'), '-cp', str(directory / 'classes'),
                                     'local.pocketchat.CallbackHost', mode],
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(before, {name: SHA((PRODUCTION / name).read_bytes()) for name in NAMES})
        return result

    def test_actual_profile_base_same_application_callbacks_storage_and_services(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed, dict(status='passed', slots=8, callbackOwners=1,
                                        registrations=32, removals=32, callbackDeliveries=144,
                                        retainedActivities=0, serviceRoutes=72))
        self.reports.append(dict(kind='production-host-model', **observed))

    def test_original_inherited_callback_registration_and_removal_recurse_on_android12_model(self):
        raw = (PRODUCTION / 'GeckoEnvironmentContext.java').read_text()
        for method in ('registerComponentCallbacks', 'unregisterComponentCallbacks'):
            pattern = r'^  @Override public void ' + method + r'\(ComponentCallbacks callback\)\{[^\n]*\}\n'
            raw, count = re.subn(pattern, '', raw, flags=re.M)
            self.assertEqual(count, 1)
        result = self.execute(raw, mode='inherited')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(status='old-recursion-reproduced', stackOverflows=2))
        self.reports.append(dict(kind='old-inherited-callback-model', registrationAndRemovalOverflow=True))

    def test_registration_and_removal_must_both_reach_the_same_owner(self):
        for name in ('GeckoEnvironmentContext.java', 'ProfileContext.java'):
            raw = (PRODUCTION / name).read_text()
            for method in ('registerComponentCallbacks', 'unregisterComponentCallbacks'):
                with self.subTest(source=name, method=method):
                    call = 'callbackOwner.' + method + '(callback);'
                    self.assertEqual(raw.count(call), 1)
                    arguments = {'wrapper' if name == 'GeckoEnvironmentContext.java' else 'profile': raw.replace(call, '', 1)}
                    result = self.execute(**arguments)
                    self.assertNotEqual(result.returncode, 0, method + ' loss was accepted')
                    self.assertIn('AssertionError', result.stderr)
        self.reports.append(dict(kind='dropped-callback-mutants', rejected=4))

    def test_direct_profile_context_original_callbacks_recurse_on_same_android12_model(self):
        raw = (PRODUCTION / 'ProfileContext.java').read_text()
        for method in ('registerComponentCallbacks', 'unregisterComponentCallbacks'):
            pattern = r'^  @Override public void ' + method + r'\(ComponentCallbacks callback\)\{[^\n]*\}\n'
            raw, count = re.subn(pattern, '', raw, flags=re.M)
            self.assertEqual(count, 1)
        result = self.execute(mode='profile-inherited', profile=raw)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(status='old-recursion-reproduced', stackOverflows=2))
        self.reports.append(dict(kind='old-direct-profile-callback-model', registrationAndRemovalOverflow=True))

    def test_actual_wrapper_sources_compile_against_pinned_android35_api(self):
        selected = os.environ.get('PROFILE_ANDROID_JAR')
        sdk_candidates = tuple(Path(os.environ[key]) / 'platforms/android-35/android.jar'
                               for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT') if os.environ.get(key))
        candidates = (*sdk_candidates,
                      Path('/usr/local/lib/android/sdk/platforms/android-35/android.jar'),
                      Path('/tmp/pocketchat-shared-tools/android-35/android.jar'),
                      ROOT / 'work/cloud-setup/platform/android-35/android.jar', ANDROID35)
        android = Path(selected) if selected else next((path for path in candidates if path.is_file()), candidates[0])
        self.assertTrue(android.is_file(), 'Pinned Android35 API jar required')
        self.assertEqual(SHA(android.read_bytes()), '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
        with tempfile.TemporaryDirectory(prefix='profile-context-android35-') as temporary:
            directory = Path(temporary)
            materialize(directory)
            result = compile_java(directory, android)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.reports.append(dict(kind='actual-android-api-compile', api=35, androidJarSha256=SHA(android.read_bytes())))


MODEL = {
    'android/content/ComponentCallbacks.java': '''package android.content;
public interface ComponentCallbacks {void onConfigurationChanged(android.content.res.Configuration c);void onLowMemory();}''',
    'android/content/ComponentCallbacks2.java': '''package android.content;
public interface ComponentCallbacks2 extends ComponentCallbacks {void onTrimMemory(int level);}''',
    'android/content/res/Configuration.java': 'package android.content.res; public final class Configuration {}',
    'android/content/Context.java': '''package android.content;
import java.io.File; import java.util.concurrent.Executor; import android.database.*; import android.database.sqlite.*;
public abstract class Context {
 public static final int MODE_MULTI_PROCESS=4;
 public Context getApplicationContext(){return this;}
 // Android 12 Context.java:682 behavior. ContextWrapper has no override here.
 public void registerComponentCallbacks(ComponentCallbacks callback){getApplicationContext().registerComponentCallbacks(callback);}
 public void unregisterComponentCallbacks(ComponentCallbacks callback){getApplicationContext().unregisterComponentCallbacks(callback);}
 public String getPackageName(){return "local.pocketchat.test";}
 public <T>T getSystemService(Class<T> type){return null;}
 public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences(name);}
 public File getDatabasePath(String name){return new File("/app/databases",name);}
 public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory){return new SQLiteDatabase(name);}
 public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory,DatabaseErrorHandler handler){return new SQLiteDatabase(name);}
 public boolean deleteDatabase(String name){return true;}
 public File getFilesDir(){return new File(System.getProperty("java.io.tmpdir"),"callback-model-files");}
 public File getCacheDir(){return new File(System.getProperty("java.io.tmpdir"),"callback-model-cache");}
 public File getNoBackupFilesDir(){return new File(System.getProperty("java.io.tmpdir"),"callback-model-nobackup");}
 public boolean bindService(Intent intent,ServiceConnection connection,int flags){return true;}
 public boolean bindService(Intent intent,int flags,Executor executor,ServiceConnection connection){return true;}
 public boolean bindIsolatedService(Intent intent,int flags,String instance,Executor executor,ServiceConnection connection){return true;}
}''',
    'android/content/ContextWrapper.java': '''package android.content;
import java.io.File; import java.util.concurrent.Executor; import android.database.*; import android.database.sqlite.*;
public class ContextWrapper extends Context {
 private final Context base; public ContextWrapper(Context c){base=c;} public Context getBaseContext(){return base;}
 @Override public Context getApplicationContext(){return base.getApplicationContext();}
 @Override public String getPackageName(){return base.getPackageName();}
 @Override public <T>T getSystemService(Class<T> type){return base.getSystemService(type);}
 @Override public SharedPreferences getSharedPreferences(String n,int m){return base.getSharedPreferences(n,m);}
 @Override public File getDatabasePath(String n){return base.getDatabasePath(n);}
 @Override public SQLiteDatabase openOrCreateDatabase(String n,int m,SQLiteDatabase.CursorFactory f){return base.openOrCreateDatabase(n,m,f);}
 @Override public SQLiteDatabase openOrCreateDatabase(String n,int m,SQLiteDatabase.CursorFactory f,DatabaseErrorHandler h){return base.openOrCreateDatabase(n,m,f,h);}
 @Override public boolean deleteDatabase(String n){return base.deleteDatabase(n);}
 @Override public File getFilesDir(){return base.getFilesDir();} @Override public File getCacheDir(){return base.getCacheDir();}
 @Override public File getNoBackupFilesDir(){return base.getNoBackupFilesDir();}
 @Override public boolean bindService(Intent i,ServiceConnection c,int f){return base.bindService(i,c,f);}
 @Override public boolean bindService(Intent i,int f,Executor e,ServiceConnection c){return base.bindService(i,f,e,c);}
 @Override public boolean bindIsolatedService(Intent i,int f,String n,Executor e,ServiceConnection c){return base.bindIsolatedService(i,f,n,e,c);}
}''',
    'android/content/ComponentName.java': '''package android.content;
public final class ComponentName {private final String pkg,name;public ComponentName(String p,String n){pkg=p;name=n;}public String getClassName(){return name;}public String getPackageName(){return pkg;}}''',
    'android/content/Intent.java': '''package android.content;
public final class Intent {private ComponentName component;public Intent(){}public Intent(Intent i){component=i.component;}public ComponentName getComponent(){return component;}public Intent setClassName(String p,String n){component=new ComponentName(p,n);return this;}}''',
    'android/content/ServiceConnection.java': 'package android.content; public interface ServiceConnection {}',
    'android/content/SharedPreferences.java': 'package android.content; public final class SharedPreferences {public final String name;public SharedPreferences(String n){name=n;}}',
    'android/database/DatabaseErrorHandler.java': 'package android.database; public interface DatabaseErrorHandler {}',
    'android/database/sqlite/SQLiteDatabase.java': 'package android.database.sqlite; public final class SQLiteDatabase {public interface CursorFactory {}public final String name;public SQLiteDatabase(String n){name=n;}}',
    'android/os/Build.java': 'package android.os; public final class Build {public static final class VERSION {public static int SDK_INT=32;}}',
    'android/os/Process.java': 'package android.os; public final class Process {public static int myPid(){return 10;}}',
    'android/app/ActivityManager.java': '''package android.app; public class ActivityManager {public static class RunningAppProcessInfo {public int pid;public String processName;}public java.util.List<RunningAppProcessInfo> getRunningAppProcesses(){return null;}}''',
    'android/app/Activity.java': 'package android.app; public final class Activity extends android.content.ContextWrapper {public Activity(android.content.Context c){super(c);}}',
    'android/app/Application.java': '''package android.app;
import android.content.*;import java.util.*;import java.util.concurrent.Executor;
public class Application extends Context {
 public static String processName="local.pocketchat.test";
 public static String getProcessName(){return processName;}
 public final List<ComponentCallbacks> callbacks=new ArrayList<>(); public int registrations,removals;
 public Intent bound; public String instance;
 @Override public void registerComponentCallbacks(ComponentCallbacks c){registrations++;callbacks.add(c);}
 @Override public void unregisterComponentCallbacks(ComponentCallbacks c){removals++;callbacks.remove(c);}
 public void dispatch(){for(ComponentCallbacks c:new ArrayList<>(callbacks)){c.onConfigurationChanged(new android.content.res.Configuration());c.onLowMemory();if(c instanceof ComponentCallbacks2)((ComponentCallbacks2)c).onTrimMemory(15);}}
 @Override public boolean bindService(Intent i,ServiceConnection c,int f){bound=i;return true;}
 @Override public boolean bindService(Intent i,int f,Executor e,ServiceConnection c){bound=i;return true;}
 @Override public boolean bindIsolatedService(Intent i,int f,String n,Executor e,ServiceConnection c){bound=i;instance=n;return true;}
}''',
    'org/json/JSONObject.java': 'package org.json; public final class JSONObject {}',
}

HOST = r'''package local.pocketchat;
import android.app.*; import android.content.*;
public final class CallbackHost {
 static int deliveries;
 static void require(boolean condition,String reason){if(!condition)throw new AssertionError(reason);}
 static final class Callback implements ComponentCallbacks2 {
  int configurations,low,trim;
  public void onConfigurationChanged(android.content.res.Configuration c){configurations++;deliveries++;}
  public void onLowMemory(){low++;deliveries++;} public void onTrimMemory(int n){trim++;deliveries++;}
 }
 static Intent child(String kind){return new Intent().setClassName("local.pocketchat.test","org.mozilla.gecko.process.GeckoChildProcessServices$"+kind);}
 public static void main(String[] args)throws Exception {
  PocketApplication app=new PocketApplication();
  if(args[0].equals("inherited")||args[0].equals("profile-inherited")){
   ProfileContext profile=(ProfileContext)app.profile(3);
   GeckoEnvironmentContext runtime=new GeckoEnvironmentContext(new Activity(profile));
   Context original=args[0].equals("profile-inherited")?profile:runtime;
   int overflows=0;try{original.registerComponentCallbacks(new Callback());}catch(StackOverflowError expected){overflows++;}
   try{original.unregisterComponentCallbacks(new Callback());}catch(StackOverflowError expected){overflows++;}
   require(overflows==2,"Old inherited callbacks did not expose both recursive paths");
   require(app.callbacks.isEmpty(),"Old recursion unexpectedly reached Application");
   System.out.println("{\"status\":\"old-recursion-reproduced\",\"stackOverflows\":2}");return;
  }
  java.lang.reflect.Field owner=GeckoEnvironmentContext.class.getDeclaredField("callbackOwner");owner.setAccessible(true);
  java.lang.reflect.Field profileOwner=ProfileContext.class.getDeclaredField("callbackOwner");profileOwner.setAccessible(true);
  int routes=0;
  for(int slot=0;slot<8;slot++){
   Application.processName="local.pocketchat.test"+(slot==0?"":":profile"+slot);
   ProfileContext isolated=(ProfileContext)app.profile(slot);
   Activity activity=new Activity(isolated);
   GeckoEnvironmentContext context=new GeckoEnvironmentContext(activity);
   require(context.getApplicationContext()==context,"Runtime lost its isolated application context");
   require(context.getBaseContext()==isolated&&context.slot==slot,"Runtime base or slot changed");
   require(owner.get(context)==app&&profileOwner.get(isolated)==app,"Callback owner retained an Activity or profile wrapper");
   require(Profiles.global(isolated)==app&&isolated.getApplicationContext()==isolated,"Profile ownership changed");
   String prefix=slot==0?"":"env"+slot+"_";
   require(context.getSharedPreferences("chat",0).name.equals(prefix+"chat"),"Preferences lost slot isolation");
   require(context.getDatabasePath("chat.db").getName().equals(prefix+"chat.db"),"Database lost slot isolation");
   require(context.getFilesDir().equals(isolated.getFilesDir())&&context.getNoBackupFilesDir().equals(isolated.getNoBackupFilesDir()),"Storage base changed");
   Callback first=new Callback(),second=new Callback();
   context.registerComponentCallbacks(first);context.registerComponentCallbacks(second);
   require(app.callbacks.size()==2,"Registration did not reach Application exactly once");
   app.dispatch();require(first.configurations==1&&first.low==1&&first.trim==1&&second.trim==1,"Callback was lost");
   context.unregisterComponentCallbacks(first);require(app.callbacks.size()==1&&app.callbacks.get(0)==second,"Unregister used a different owner");
   app.dispatch();require(first.trim==1&&second.configurations==2&&second.low==2&&second.trim==2,"Removed callback survived or live callback was lost");
   context.unregisterComponentCallbacks(second);require(app.callbacks.isEmpty(),"Callback leaked after unregister");
   Callback profileFirst=new Callback(),profileSecond=new Callback();
   isolated.registerComponentCallbacks(profileFirst);isolated.registerComponentCallbacks(profileSecond);
   require(app.callbacks.size()==2,"Direct profile callback did not reach Application exactly once");
   app.dispatch();require(profileFirst.configurations==1&&profileFirst.low==1&&profileFirst.trim==1&&profileSecond.trim==1,"Direct profile callback was lost");
   context.unregisterComponentCallbacks(profileFirst);require(app.callbacks.size()==1&&app.callbacks.get(0)==profileSecond,"Cross-wrapper removal changed callback owner");
   app.dispatch();require(profileFirst.trim==1&&profileSecond.configurations==2&&profileSecond.low==2&&profileSecond.trim==2,"Direct profile callback removal was lost");
   isolated.unregisterComponentCallbacks(profileSecond);require(app.callbacks.isEmpty(),"Direct profile callback leaked after unregister");
   for(String kind:new String[]{"socket","gpu","rdd","utility","gmplugin","ipdlunittest","tab0"}){
    Intent original=child(kind);context.bindService(original,null,0);
    require(app.bound!=original&&app.bound.getComponent().getClassName().equals("local.pocketchat.GeckoEnvironmentServices$E"+slot+kind),"Child service escaped its slot");
    require(original.getComponent().getClassName().endsWith("$"+kind),"Caller Intent mutated");routes++;
   }
   context.bindService(child("gpu"),0,Runnable::run,null);
   require(app.bound.getComponent().getClassName().equals("local.pocketchat.GeckoEnvironmentServices$E"+slot+"gpu"),"Executor bind escaped its slot");routes++;
   Intent original=child("isolatedTab");context.bindIsolatedService(original,0,"child.1",Runnable::run,null);
   require(app.bound==original&&app.instance.equals("environment"+slot+"_child.1"),"Isolated service instance mapping changed");routes++;
   Intent zygote=child("zygoteTab");context.bindService(zygote,null,0);require(app.bound==zygote,"Zygote bypass changed");
   boolean rejected=false;try{context.bindService(child("unknown"),null,0);}catch(IllegalStateException expected){rejected=true;}require(rejected,"Unknown child service accepted");
  }
  require(app.registrations==32&&app.removals==32&&deliveries==144,"Unexpected callback count");
  System.out.println("{\"status\":\"passed\",\"slots\":8,\"callbackOwners\":1,\"registrations\":32,\"removals\":32,\"callbackDeliveries\":144,\"retainedActivities\":0,\"serviceRoutes\":"+routes+"}");
 }
}'''


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GeckoContextCallbacks))
    report = dict(schema=1, status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
                  sourceSha256={name: SHA((PRODUCTION / name).read_bytes()) for name in NAMES},
                  observations=GeckoContextCallbacks.reports,
                  actualAndroidExecution=False, actualGeckoExecution=False,
                  android32RuntimeAccepted=False, android32ApiCompiled=False,
                  scope='Actual production wrappers and unchanged profile/Application helper methods on a faithful callback-forwarding host model; separate real Android35 API compilation. No device, APK, login, network or visual acceptance.')
    output = os.environ.get('PROFILE_GECKO_CONTEXT_CALLBACKS_REPORT')
    if output:
        path = Path(output);path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
