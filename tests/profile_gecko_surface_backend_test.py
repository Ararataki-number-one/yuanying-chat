"""Actual Gecko initialization calls with counted adapters, plus real SDK API compile.

The JVM model does not render Android surfaces. API32/API35 transform, IME,
overlay, retention and original idle-frame acceptance remain device checks.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
SPEC = importlib.util.spec_from_file_location('surface_open_member', ROOT / 'tests/ux-shell-host/focus_run.py')
EXTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACT)
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def java_tools(java_home=None):
    java = (Path(java_home) / 'bin/java' if java_home else
            Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or ''))
    javac = java.with_name('javac')
    if not java.is_file() or not javac.is_file():
        raise RuntimeError('Actual JDK java/javac required')
    return java, javac


def actual_open():
    return EXTRACT.member(SOURCE.read_text(), 'private void open()')


def execute_model(method):
    java, javac = java_tools()
    before = SOURCE.read_bytes()
    with tempfile.TemporaryDirectory(prefix='gecko-surface-open-') as temporary:
        base = Path(temporary)
        source = base / 'BackendCases.java'
        source.write_text(MODEL.replace('/* ACTUAL_OPEN */', method))
        built = subprocess.run([str(javac), '-encoding', 'UTF-8', '--release', '17',
                                '-d', str(base / 'classes'), str(source)],
                               capture_output=True, text=True, timeout=45)
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        ran = subprocess.run([str(java), '-cp', str(base / 'classes'), 'local.pocketchat.BackendCases'],
                             capture_output=True, text=True, timeout=15)
    if SOURCE.read_bytes() != before:
        raise AssertionError('Production source changed during initialization proof')
    return ran


class GeckoSurfaceBackend(unittest.TestCase):
    def test_actual_current_open_chooses_surface_before_session_and_only_once(self):
        result = execute_model(actual_open())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(status='passed', checks=16,
                                                        actualAndroidExecution=False))

    def rejected(self, old, new):
        method = actual_open()
        self.assertEqual(method.count(old), 1)
        result = execute_model(method.replace(old, new, 1))
        self.assertNotEqual(result.returncode, 0, 'Initialization regression unexpectedly accepted')
        self.assertIn('AssertionError', result.stderr)

    def test_texture_backend_regression_is_rejected_by_call_trace(self):
        self.rejected('surface.coverUntilFirstPaint(',
                      'surface.setViewBackend(GeckoView.BACKEND_TEXTURE_VIEW);surface.coverUntilFirstPaint(')

    def test_reselecting_default_backend_and_losing_its_holder_listener_is_rejected(self):
        self.rejected('surface.coverUntilFirstPaint(',
                      'surface.setViewBackend(GeckoView.BACKEND_SURFACE_VIEW);surface.coverUntilFirstPaint(')

    def test_recreating_a_retained_surface_is_rejected(self):
        self.rejected('if(surface==null)', 'if(true)')

    def test_live_backend_selection_after_session_attachment_is_rejected(self):
        method = actual_open()
        call = 'surface.setViewBackend(GeckoView.BACKEND_SURFACE_VIEW);'
        self.assertEqual(method.count('setViewBackend('), 0)
        self.assertEqual(method.count('surface.setSession(primary);'), 1)
        changed = method.replace('surface.setSession(primary);',
                                 'surface.setSession(primary);' + call, 1)
        result = execute_model(changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AssertionError', result.stderr)

    def test_destroyed_owner_cannot_initialize_a_surface(self):
        self.rejected('if(!enabled||destroyed)return;', 'if(!enabled)return;')



def execute_actual_sdk_callbacks(sdk_jar, java, javac):
    """Execute unmodified SDK callback wiring with explicit Android boundaries.

    This does not instantiate a Gecko runtime or render a surface. Android
    boundary holders only count registrations and dispatch the standard callback;
    the wrapper, its listener and MagnifiableSurfaceView are the real SDK classes.
    """
    with tempfile.TemporaryDirectory(prefix='gecko-real-sdk-holder-') as temporary:
        base = Path(temporary)
        sources = []
        for name, raw in SDK_CALLBACK_ANDROID_BOUNDARIES.items():
            path = base / 'src' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw)
            sources.append(str(path))
        source = base / 'src/SurfaceCallbackProbe.java'
        source.write_text(SDK_CALLBACK_PROBE)
        sources.append(str(source))
        classes = base / 'classes'
        built = subprocess.run([str(javac), '-encoding', 'UTF-8', '--release', '17',
                                '-classpath', str(sdk_jar), '-d', str(classes), *sources],
                               capture_output=True, text=True, timeout=45)
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        ran = subprocess.run([str(java), '-cp', str(classes) + os.pathsep + str(sdk_jar),
                              'SurfaceCallbackProbe'], capture_output=True, text=True, timeout=15)
        if ran.returncode:
            raise AssertionError(ran.stdout + ran.stderr)
        result = json.loads(ran.stdout)
        if Path(result['actualSdkCodeSource']).resolve() != sdk_jar.resolve():
            raise AssertionError('Callback probe did not execute the receipt-bound real SDK')
        return result


def compile_actual_api(args):
    java, javac = java_tools(args.java_home)
    receipt = json.loads(args.sdk_receipt.read_text())
    inputs = [SOURCE, Path(__file__), args.sdk_jar, args.sdk_receipt, args.android_jar]
    before = {str(path.resolve()): SHA(path.read_bytes()) for path in inputs}
    if before[str(args.sdk_jar.resolve())] != receipt['sdkClassesJarSha256']:
        raise AssertionError('Real SDK JAR must match its build receipt')
    if before[str(args.android_jar.resolve())] != '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b':
        raise AssertionError('Pinned actual Android35 API required')
    spec = importlib.util.spec_from_file_location('surface_actual_sdk_constants', ROOT / 'tools/gecko/verify_official_sdk.py')
    verify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verify)
    with ZipFile(args.sdk_jar) as jar:
        view_class = jar.read('org/mozilla/geckoview/GeckoView.class')
        constants = verify.class_constants(view_class)
    if (constants['BACKEND_SURFACE_VIEW'], constants['BACKEND_TEXTURE_VIEW']) != (1, 2):
        raise AssertionError('Review the actual SDK backend constants')
    method = actual_open()
    if 'setViewBackend(' in method:
        raise AssertionError('Do not replace the SDK constructor holder or its listener')
    callback_proof = execute_actual_sdk_callbacks(args.sdk_jar, java, javac)
    with tempfile.TemporaryDirectory(prefix='gecko-surface-real-api-') as temporary:
        base = Path(temporary)
        source = base / 'GeckoWebView.java'
        source.write_text(API.replace('/* ACTUAL_OPEN */', method))
        empty = base / 'empty-source'
        empty.mkdir()
        command = [str(javac), '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-proc:none',
                   '-classpath', str(args.sdk_jar) + os.pathsep + str(args.android_jar),
                   '-sourcepath', str(empty), '-d', str(base / 'classes'), str(source)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
    if before != {str(path.resolve()): SHA(path.read_bytes()) for path in inputs}:
        raise AssertionError('Actual producer or API input changed during compilation')
    report = dict(schema=1, status='passed', sourceSha256=before[str(SOURCE.resolve())],
                  currentOpenSha256=SHA(method.encode()), sdkJarSha256=receipt['sdkClassesJarSha256'],
                  actualGeckoViewClassSha256=SHA(view_class), backendConstants=dict(surface=1, texture=2),
                  androidJarSha256=before[str(args.android_jar.resolve())], inputSha256=before,
                  actualSdkApiCompilation=True, actualSdkCallbackProof=callback_proof,
                  actualSdkCallbackExecution=True, syntheticAndroidCallbackTransport=True,
                  syntheticSdk=False, syntheticAndroidApi=False,
                  executionInputsUnchanged=True, actualAndroidExecution=False, actualGeckoExecution=False,
                  scope='Verbatim current production open() compiled against receipt-bound real GeckoView/GeckoSession/GeckoRuntime and pinned Android35. The unmodified real SDK SurfaceViewWrapper, listener and MagnifiableSurfaceView also execute with counted synthetic Android callback transport, proving constructor registration and the same-backend replacement negative control. Other app methods are explicit compile-only boundaries; no native Gecko runtime, device rendering, transform, IME, overlay or idle-frame runtime acceptance.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


MODEL = '''package local.pocketchat;
import java.util.*;
public final class BackendCases {
 static int checks;
 static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
 public static void main(String[] args){
  GeckoWebView owner=new GeckoWebView();owner.desktop=true;owner.queued="https://example.test/retained";
  owner.invoke();
  check(Events.values.equals(Arrays.asList("view","cover","attach","new-session","open-session","set-session","privacy","configure","load")),"Actual initialization order retains the SDK constructor's holder listener");
  check(owner.surface.backend==GeckoView.BACKEND_SURFACE_VIEW,"Native surface backend selected");
  check(owner.ready&&owner.primary==owner.current&&owner.surface.session==owner.primary,"Same opened session is attached and ready");
  check(owner.surface.cover==ReferenceUi.CHAT_BG,"Original first-paint cover retained");
  check(owner.configuredDesktop&&owner.configuredPrivacy==3,"Desktop and privacy arguments retained");
  check(owner.queued.isEmpty()&&owner.loaded.equals("https://example.test/retained"),"Queued navigation is consumed once");
  GeckoView retained=owner.surface;Events.values.clear();owner.invoke();
  check(owner.surface==retained,"Retained surface is not reconstructed");
  check(Events.values.equals(Arrays.asList("new-session","open-session","set-session","privacy","configure")),"Retained surface does not reselect a live backend or reattach");
  check(owner.surface.backendSelections==0,"Constructor's surface is never replaced with a listener-free holder");
  check(owner.surface.session==owner.current&&owner.current==owner.primary,"New session uses the retained surface");
  Events.values.clear();GeckoWebView disabled=new GeckoWebView();disabled.enabled=false;disabled.invoke();
  check(Events.values.isEmpty(),"Disabled owner performs no SDK calls");
  check(disabled.surface==null&&!disabled.ready&&disabled.current==null,"Disabled owner state retained");
  Events.values.clear();GeckoWebView destroyed=new GeckoWebView();destroyed.destroyed=true;destroyed.invoke();
  check(Events.values.isEmpty(),"Destroyed owner performs no SDK calls");
  check(destroyed.surface==null&&!destroyed.ready&&destroyed.current==null,"Destroyed owner state retained");
  check(retained.backend==1,"Guard cases do not alter the retained backend");
  check(retained.backendSelections==0,"Guard cases do not schedule backend reselection");
  System.out.println("{\\"status\\":\\"passed\\",\\"checks\\":"+checks+",\\"actualAndroidExecution\\":false}");
 }
}
final class Events {static final List<String> values=new ArrayList<>();}
final class GeckoWebView {
 boolean enabled=true,destroyed,ready,desktop,configuredDesktop;int configuredPrivacy;
 GeckoView surface;final Object displayContext=new Object();final GeckoRuntime runtime=new GeckoRuntime();
 GeckoSession primary,current;final Owner owner=new Owner();String queued="",loaded="";
 void invoke(){open();}
 GeckoSession newSession(){Events.values.add("new-session");return new GeckoSession();}
 void configure(boolean desktop,int privacy){Events.values.add("configure");configuredDesktop=desktop;configuredPrivacy=privacy;}
 void loadUrl(String value){if(!queued.isEmpty())throw new AssertionError("Queue not cleared");Events.values.add("load");loaded=value;}
 void addView(GeckoView view,FrameLayout.LayoutParams params){if(params.width!=-1||params.height!=-1)throw new AssertionError("Surface bounds changed");Events.values.add("attach");}
 /* ACTUAL_OPEN */
}
final class GeckoView {
 static final int BACKEND_SURFACE_VIEW=1,BACKEND_TEXTURE_VIEW=2;int backend=1,backendSelections,cover;GeckoSession session;
 GeckoView(Object context){Events.values.add("view");}
 void setViewBackend(int value){if(session!=null)throw new AssertionError("Live backend change");Events.values.add("backend:"+value);backend=value;backendSelections++;}
 void coverUntilFirstPaint(int value){Events.values.add("cover");cover=value;}
 void setSession(GeckoSession value){Events.values.add("set-session");session=value;}
}
final class GeckoRuntime {}
final class GeckoSession {void open(GeckoRuntime runtime){Events.values.add("open-session");}}
final class Owner {final Privacy privacy=new Privacy();}
final class Privacy {int level(){Events.values.add("privacy");return 3;}}
final class ReferenceUi {static final int CHAT_BG=77;}
final class FrameLayout {static final class LayoutParams {final int width,height;LayoutParams(int width,int height){this.width=width;this.height=height;}}}
'''

API = '''package local.pocketchat;
import android.content.Context;import android.widget.FrameLayout;import org.mozilla.geckoview.*;
final class GeckoWebView extends FrameLayout {
 boolean enabled,destroyed,ready,desktop;GeckoView surface;Context displayContext;GeckoRuntime runtime;
 GeckoSession primary,current;Owner owner;String queued="";
 GeckoWebView(Context context){super(context);displayContext=context;}
 GeckoSession newSession(){throw new UnsupportedOperationException("compile-only app boundary");}
 void configure(boolean desktop,int privacy){throw new UnsupportedOperationException("compile-only app boundary");}
 void loadUrl(String value){throw new UnsupportedOperationException("compile-only app boundary");}
 /* ACTUAL_OPEN */
}
final class Owner {Privacy privacy;}
final class Privacy {int level(){throw new UnsupportedOperationException("compile-only app boundary");}}
final class ReferenceUi {static int CHAT_BG;}
'''


SDK_CALLBACK_ANDROID_BOUNDARIES = {'android/content/Context.java': 'package android.content; public class Context {}\n',
 'android/graphics/Rect.java': 'package android.graphics; public class Rect { public int '
                               'right,bottom; public Rect(int w,int h){right=w;bottom=h;} }\n',
 'android/graphics/SurfaceTexture.java': 'package android.graphics; public class SurfaceTexture '
                                         '{}\n',
 'android/os/Build.java': 'package android.os; public class Build { public static class VERSION { '
                          'public static int SDK_INT=35; } }\n',
 'android/util/Log.java': 'package android.util; public class Log { public static int e(String '
                          'a,String b){return 0;} }\n',
 'android/view/Surface.java': 'package android.view; public class Surface { public Surface(){} '
                              'public Surface(android.graphics.SurfaceTexture t){} }\n',
 'android/view/SurfaceControl.java': 'package android.view; public class SurfaceControl {}\n',
 'android/view/SurfaceHolder.java': 'package android.view; public interface SurfaceHolder { void '
                                    'setFormat(int f); void addCallback(Callback c); Surface '
                                    'getSurface(); android.graphics.Rect getSurfaceFrame(); '
                                    'interface Callback { void surfaceCreated(SurfaceHolder h); '
                                    'void surfaceChanged(SurfaceHolder h,int f,int w,int z); void '
                                    'surfaceDestroyed(SurfaceHolder h); } }\n',
 'android/view/SurfaceView.java': 'package android.view; public class SurfaceView extends View { '
                                  'public final Holder holder=new Holder(); public '
                                  'SurfaceView(android.content.Context c){super(c);} public '
                                  'SurfaceHolder getHolder(){return holder;} public SurfaceControl '
                                  'getSurfaceControl(){return new SurfaceControl();} public static '
                                  'class Holder implements SurfaceHolder { public final '
                                  'java.util.List<Callback> callbacks=new java.util.ArrayList<>(); '
                                  'public void setFormat(int f){} public void addCallback(Callback '
                                  'c){callbacks.add(c);} public Surface getSurface(){return new '
                                  'Surface();} public android.graphics.Rect '
                                  'getSurfaceFrame(){return new android.graphics.Rect(2676,594);} '
                                  'public void dispatch(){for(Callback '
                                  'c:callbacks)c.surfaceChanged(this,-2,2676,594);} } }\n',
 'android/view/TextureView.java': 'package android.view; public class TextureView extends View { '
                                  'public TextureView(android.content.Context c){super(c);} public '
                                  'android.graphics.SurfaceTexture getSurfaceTexture(){return new '
                                  'android.graphics.SurfaceTexture();} public void '
                                  'setSurfaceTextureListener(SurfaceTextureListener l){} public '
                                  'interface SurfaceTextureListener { void '
                                  'onSurfaceTextureAvailable(android.graphics.SurfaceTexture t,int '
                                  'w,int h); void '
                                  'onSurfaceTextureSizeChanged(android.graphics.SurfaceTexture '
                                  't,int w,int h); boolean '
                                  'onSurfaceTextureDestroyed(android.graphics.SurfaceTexture t); '
                                  'void onSurfaceTextureUpdated(android.graphics.SurfaceTexture '
                                  't); } }\n',
 'android/view/View.java': 'package android.view; public class View { public '
                           'View(android.content.Context c){} public void setBackgroundColor(int '
                           'c){} }\n'}

SDK_CALLBACK_PROBE = 'import org.mozilla.gecko.SurfaceViewWrapper;\nimport android.view.*;\npublic final class SurfaceCallbackProbe {\n static final class Listener implements SurfaceViewWrapper.Listener {\n  int changed;\n  public void onSurfaceChanged(Surface surface,SurfaceControl control,int width,int height){\n   if(width!=2676||height!=594)throw new AssertionError("Actual SDK callback geometry changed");\n   changed++;\n  }\n  public void onSurfaceDestroyed(){}\n }\n public static void main(String[] args) throws Exception {\n  android.content.Context context=new android.content.Context();\n  SurfaceViewWrapper wrapper=new SurfaceViewWrapper(context);\n  Listener listener=new Listener();wrapper.setListener(listener);\n  SurfaceView initial=(SurfaceView)wrapper.getView();\n  int initialCallbacks=initial.holder.callbacks.size();\n  initial.holder.dispatch();int initialEvents=listener.changed;\n  if(initialCallbacks!=1||initialEvents!=1)throw new AssertionError("SDK constructor listener was not wired");\n  wrapper.useSurfaceView(context);\n  SurfaceView replacement=(SurfaceView)wrapper.getView();\n  int replacementCallbacks=replacement.holder.callbacks.size();\n  replacement.holder.dispatch();int replacementEvents=listener.changed-initialEvents;\n  if(initial==replacement||replacementCallbacks!=0||replacementEvents!=0)\n   throw new AssertionError("Review the actual SDK same-backend replacement behavior");\n  wrapper.setListener(listener);replacement.holder.dispatch();\n  if(replacement.holder.callbacks.size()!=1||listener.changed!=initialEvents+1)\n   throw new AssertionError("Synthetic callback transport did not preserve real SDK listener dispatch");\n  String codeSource=new java.io.File(SurfaceViewWrapper.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getAbsolutePath();\n  System.out.println("{\\"status\\":\\"passed\\",\\"actualSdkCodeSource\\":\\""+codeSource+"\\",\\"defaultHolderCallbacks\\":"+initialCallbacks+",\\"defaultSurfaceEventsDelivered\\":"+initialEvents+",\\"replacementHolderCallbacks\\":"+replacementCallbacks+",\\"replacementSurfaceEventsDelivered\\":"+replacementEvents+",\\"reboundHolderCallbacks\\":"+replacement.holder.callbacks.size()+",\\"reboundSurfaceEventsDelivered\\":"+(listener.changed-initialEvents)+",\\"actualAndroidExecution\\":false}");\n }\n}\n'


if __name__ == '__main__':
    if '--actual-sdk-jar' in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--actual-sdk-jar', dest='sdk_jar', type=Path, required=True)
        parser.add_argument('--sdk-receipt', type=Path, required=True)
        parser.add_argument('--android-jar', type=Path, required=True)
        parser.add_argument('--java-home', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        compile_actual_api(parser.parse_args())
    else:
        unittest.main(verbosity=2)
