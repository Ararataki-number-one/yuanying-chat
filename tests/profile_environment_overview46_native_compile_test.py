"""Native overview/UI API compilation against pinned Android 35, with app/Gecko adapters.

This is not compilation against real Gecko or execution on Android.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
class Overview46NativeCompile(unittest.TestCase):
 def test_native_ui_android_api(self):
  android=Path(os.environ.get('PROFILE_ANDROID_JAR','/tmp/pocketchat-shared-tools/android-35/android.jar'))
  if not android.is_file():self.skipTest('Android 35 API jar unavailable')
  self.assertEqual(hashlib.sha256(android.read_bytes()).hexdigest(),'4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
  java=Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '');javac=java.with_name('javac');self.assertTrue(javac.is_file())
  names=['EnvironmentOverviewUi.java','EnvironmentOverviewInfo.java','EnvironmentOverviewState.java','ExitIpPageUi.java','ThemedDialog.java']
  before={name:hashlib.sha256((PRODUCTION/name).read_bytes()).hexdigest() for name in names}
  with tempfile.TemporaryDirectory(prefix='overview46-android-api-') as directory:
   base=Path(directory)
   for name in names:(base/name).write_bytes((PRODUCTION/name).read_bytes())
   (base/'NativeAdapters.java').write_text(ADAPTERS)
   result=subprocess.run([str(javac),'-encoding','UTF-8','-cp',str(android),'-d',str(base),*map(str,base.glob('*.java'))],capture_output=True,text=True,timeout=45)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertEqual(before,{name:hashlib.sha256((PRODUCTION/name).read_bytes()).hexdigest() for name in names})
  report=dict(status='passed',scope='Actual native UI sources compiled against pinned Android35 API with declared application and Gecko adapters; no real Gecko or Android execution.',sourceSha256=before,androidJarSha256=hashlib.sha256(android.read_bytes()).hexdigest(),actualAndroidExecution=False,actualGeckoExecution=False,actualGeckoApiCompilation=False)
  output=os.environ.get('OVERVIEW46_NATIVE_REPORT')
  if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')
ADAPTERS='''package local.pocketchat;
import android.app.*;import android.content.*;import android.os.*;import android.widget.*;import org.json.*;
class MainActivity extends Activity {Handler handler=new Handler();ChatSession session;GeckoWebView remote;AppHub hub;DesignChrome designChrome;int dp(int v){return v;}void hideKeyboard(){}}
class ChatSession {Context context;String environmentId="A",appliedIdentity="",connectionStage="";int environmentGeneration;boolean networkReady,offline,connecting;Guard guard=new Guard();GeckoWebView web;Audit audit=new Audit();boolean internalNetwork(){return true;}String networkIdentity(){return "";}static class Guard{boolean allowed(){return true;}}static class Audit{JSONObject report=new JSONObject();boolean deepObservationCurrent(){return false;}}}
class GeckoWebView extends FrameLayout {GeckoWebView(Context c){super(c);}interface ExitIpPageListener{void changed(String m);void closed();}int exitIpTopInset;boolean hasExitIpPage(){return false;}String openExitIpPage(ExitIpPageListener l){return "";}boolean closeExitIpPage(){return false;}GeckoSettings getSettings(){return new GeckoSettings();}}
class GeckoSettings {boolean policyAcknowledged;JSONObject acceptedBrowserIdentity=new JSONObject();String[] requestedLocales=new String[0];}
class AppHub{static int CHAT=0;int page;}class DesignChrome{void cancelWebGesture(){}}
class NativeNetwork {static NativeNetwork peek(){return null;}String exitIp="";long lastVerified;boolean starting;NetworkHealthPolicy.Admission connectionAdmission(){return NetworkHealthPolicy.Admission.VERIFIED;}String exitCheckUrl(){return "https://api.ipify.org?format=json";}}
class NetworkHealthPolicy{enum Admission{VERIFIED}}
class NetworkRegion{static JSONObject read(Context c){return new JSONObject();}static String region(Context c,String ip){return "";}}
class BrowserIdentitySpec{static BrowserIdentitySpec from(JSONObject o){return new BrowserIdentitySpec();}String label(){return "";}}
class FingerprintObservationHistory{static boolean integer(Object o,int min,int max){return true;}}
class AuditReport{static boolean observedField(JSONObject o,String field){return true;}}
class Profiles{static int slot(Context c){return 0;}static String display(Context c,int slot){return "";}}
class ProfileCatalog{static ProfileCatalog get(Context c){return new ProfileCatalog();}JSONObject item(int slot){return new JSONObject();}boolean available(int slot){return true;}}
class NetworkStatusUi{static boolean current(MainActivity a,ChatSession s){return true;}}
class DesignUi{static LinearLayout screen(Context c){return new LinearLayout(c);}static LinearLayout column(Context c){return new LinearLayout(c);}static LinearLayout row(Context c){return new LinearLayout(c);}static void action(LinearLayout box,String text,boolean primary,Runnable action){}static void message(Activity a,String title,String message){}}
class ReferenceUi{static int TEXT=0,MUTED=0,CHAT_BG=0;static TextView text(Context c,String t,int size,int color,boolean bold){return new TextView(c);}static TextView secondary(Context c,String t){return new TextView(c);}static Button small(Context c,String t,boolean primary,Runnable action){return new Button(c);}}
class AppAppearance{static void shown(Dialog d){}}
'''
if __name__=='__main__':unittest.main(verbosity=2)
