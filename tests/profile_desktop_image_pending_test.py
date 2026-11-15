"""Execute actual desktop-image fixture methods against controlled JVM edges.

These controls exercise fixture timing, not a real Android chooser or upload.
The historical snippet is copied without rewriting from source 1178ce488bc1,
Git blob cacdb3cd9362f65980abfe7364a625ee649d6428. Keeping its scoped bytes here
avoids requiring a moving shallow CI checkout to retain that old commit.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SNIPPET = ROOT / 'tests/fixtures/desktop-image-pending-1178.java.txt'
HISTORICAL_SHA = '3bd80e0014c95046a4c766b29e8642add836a37bcfc0dfceefa7cbd21779a37c'


def methods():
    source = (ROOT / 'tests/gecko/GeckoIntegrationTestActivity.java').read_text()
    start = source.index('  void desktopImage(long serial)')
    return source[start:source.index('  void usability(', start)]


STUBS = {
    'android/view/Window.java': 'package android.view; public class Window {}',
    'android/app/Activity.java': '''package android.app; public class Activity {
      public static final int RESULT_OK=-1; public android.view.Window getWindow(){return new android.view.Window();}
      public void startActivityForResult(android.content.Intent i,int r){}
    }''',
    'android/net/Uri.java': '''package android.net; public class Uri {
      public final String value; private Uri(String s){value=s;}public static Uri parse(String s){return new Uri(s);}
    }''',
    'android/content/Intent.java': '''package android.content; public class Intent {
      public static final String ACTION_OPEN_DOCUMENT="open",EXTRA_ALLOW_MULTIPLE="multiple";
      public android.net.Uri uri;public String getAction(){return ACTION_OPEN_DOCUMENT;}
      public String getType(){return "image/*";}public boolean getBooleanExtra(String k,boolean d){return true;}
      public Intent setData(android.net.Uri v){uri=v;return this;}
    }''',
    'android/webkit/WebView.java': 'package android.webkit; public class WebView {}',
    'android/webkit/ValueCallback.java': 'package android.webkit; public interface ValueCallback<T>{void onReceiveValue(T value);}',
    'android/webkit/WebChromeClient.java': '''package android.webkit; public class WebChromeClient {
      public static class FileChooserParams {} public boolean onShowFileChooser(WebView v,ValueCallback<android.net.Uri[]> c,FileChooserParams p){return false;}
    }''',
    'android/widget/TextView.java': 'package android.widget;public class TextView{public TextView(Object x){}}',
    'android/os/SystemClock.java': 'package android.os;public class SystemClock{public static long now;public static long elapsedRealtime(){return now;}}',
}

HOST = r'''import org.json.*;
import android.app.Activity;import android.content.Intent;import android.os.SystemClock;
import android.webkit.WebView;import android.widget.TextView;
final class GeckoIntegrationTestActivity extends Activity {
  long run=1;final Session session=new Session();final EventStore eventStore=new EventStore();
  JSONObject result;String resultKind;int taps,evals;boolean defer,ready=true;Runnable deferred;
  static final class J {static JSONObject held;static JSONObject obj(Object... pairs){JSONObject o=new JSONObject();for(int i=0;i<pairs.length;i+=2)o.put((String)pairs[i],pairs[i+1]);if("web".equals(o.optString("kind")))held=o;return o;}static JSONObject parse(String s){return new JSONObject(s);}}
  static final class EventStore{String nonce="controlled-nonce";}
  static final class Privacy{int level(){return 0;}}
  static final class Reading{void configure(boolean v){}}
  static final class Handler{
    final java.util.ArrayDeque<Runnable> work=new java.util.ArrayDeque<>();
    final java.util.ArrayDeque<Long> delays=new java.util.ArrayDeque<>();
    void post(Runnable r){postDelayed(r,0);}void postDelayed(Runnable r,long d){work.add(r);delays.add(d);}
    void next(){check(!work.isEmpty(),"scheduled work required");SystemClock.now+=delays.remove();work.remove().run();}
  }
  final class Session{final Reading reading=new Reading();final Privacy privacy=new Privacy();final Handler handler=new Handler();
    final FixtureView web=new FixtureView();JSONObject pending;boolean navigating;Object prefs=new Object();JSONArray attachments=new JSONArray();}
  class GeckoWebView extends WebView{boolean desktop;}
  final class DisplayContext{Object base;Object getBaseContext(){return base;}}
  final class FixtureView extends GeckoWebView{
    boolean chooserOrigin,visible;String target,upload="";MainActivity host;android.webkit.WebChromeClient chrome;
    final DisplayContext displayContext=new DisplayContext();
    void configure(boolean desktop,int level){this.desktop=desktop;}
    void setHost(Object h){displayContext.base=h;if(h instanceof MainActivity)host=(MainActivity)h;}
    void setWebChromeClient(android.webkit.WebChromeClient c){chrome=c;}
    void loadUrl(String t){target=t;session.pending=null;session.navigating=true;visible=false;}
    boolean hasVisibleDocument(){return visible;}
    void evaluateJavascript(String js,android.webkit.ValueCallback<String> callback){
      evals++;check(js.contains(JSONObject.quote(target)),"readiness must bind the exact invocation URL");
      Runnable r=()->callback.onReceiveValue(J.obj("ready",ready,"value",upload).toString());
      if(defer)deferred=r;else r.run();
    }
  }
  class MainActivity extends Activity{
    Session session;FixtureView remote;Object prefs;boolean pageMode;TextView status;LoadingUi loading;Attachments attachments;
    void attachBaseContext(Object x){}void status(String s){}
  }
  static final class LoadingUi{LoadingUi(Object x){}}
  final class Attachments{
    static final int FIRST_REQUEST=100,LAST_REQUEST=200;final MainActivity host;boolean destroyed;
    Attachments(MainActivity h){host=h;}
    android.webkit.WebChromeClient chrome(){return new android.webkit.WebChromeClient(){@Override public boolean onShowFileChooser(WebView w,android.webkit.ValueCallback<android.net.Uri[]> c,FileChooserParams p){host.startActivityForResult(new Intent(),101);return true;}};}
    void result(int request,int code,Intent intent){check(host.remote.chooserOrigin,"chooser origin must be scoped to result");check(code==Activity.RESULT_OK,"actual result boundary");String value=intent.uri.value;check(value.equals("content://synthetic.pocket.upload/image")||value.equals("content://local.pocketchat.test.upload/image"),"provider result identity");host.remote.upload="ok:"+value;}
    void destroy(){destroyed=true;}
  }
  void event(long serial,String kind,JSONObject value){check(serial==run,"event owner");resultKind=kind;result=value;}
  void tapElement(long serial,String id){
    check(serial==run&&"upload".equals(id),"tap owner and actual fixture target");
    check(session.pending==J.held,"held pending must precede first actual upload tap");
    taps++;session.web.chrome.onShowFileChooser(session.web,value->{},new android.webkit.WebChromeClient.FileChooserParams());
  }
  static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
  void visible(){session.web.visible=true;session.navigating=false;}
  void start(boolean own){desktopImage(1,own);check(session.pending==null,"navigation has cleared pending");check(session.handler.delays.peek()==200L,"original initial polling interval");visible();}
  void finish(boolean own){for(int i=0;i<5&&result==null;i++)session.handler.next();
    check(taps==1,"exactly one upload tap");check("desktopImage".equals(resultKind),"real completion callback");
    for(String k:new String[]{"productionChooserOpened","imageMimeAndMultiple","pendingPreserved","noPhantomUpload","desktop"})check(result.optBoolean(k),k);
    check(result.optString("upload").equals("ok:"+(own?"content://local.pocketchat.test.upload/image":"content://synthetic.pocket.upload/image")),"selected provider completed");
    check(session.pending==null&&session.web.displayContext.base==this,"completion cleanup");
  }
__METHODS__
  public static void main(String[] args){String mode=args[0];boolean own=args.length>1&&args[1].equals("own");SystemClock.now=0;
    if(mode.equals("ordinary")){GeckoIntegrationTestActivity a=new GeckoIntegrationTestActivity();a.start(own);a.finish(own);}
    else if(mode.equals("gates")){for(int gate=0;gate<3;gate++){
      GeckoIntegrationTestActivity a=new GeckoIntegrationTestActivity();a.start(own);
      if(gate==0)a.ready=false;if(gate==1)a.session.web.visible=false;if(gate==2)a.session.navigating=true;
      a.session.handler.next();check(a.taps==0&&a.session.pending==null,"all three document gates must precede pending and upload");
      check(a.session.handler.delays.peek()==100L,"original recurring polling interval");a.ready=true;a.visible();a.finish(own);
    }}
    else if(mode.equals("stale")){
      GeckoIntegrationTestActivity a=new GeckoIntegrationTestActivity();a.start(own);a.defer=true;a.session.handler.next();
      check(a.deferred!=null,"real callback held at async boundary");a.run=2;JSONObject newer=new JSONObject();a.session.pending=newer;
      a.deferred.run();check(a.session.pending==newer&&a.taps==0&&a.result==null&&a.session.handler.work.isEmpty(),"stale callback must be inert");
      int before=a.evals;a.desktopImageReady(1,25000,a.session.web.host,J.held,new boolean[1],new boolean[1],false,a.session.web.target);
      check(a.evals==before,"stale invocation must not query document");
    }
    else if(mode.equals("deadline")){
      GeckoIntegrationTestActivity a=new GeckoIntegrationTestActivity();a.start(own);a.ready=false;a.session.handler.next();
      SystemClock.now=25201;a.session.handler.next();check("error".equals(a.resultKind)&&a.session.pending==null&&a.taps==0,"original 25 second deadline");
      check(a.session.handler.work.isEmpty(),"no retry after deadline");
    }
    else if(mode.equals("already")){
      GeckoIntegrationTestActivity a=new GeckoIntegrationTestActivity();a.start(own);JSONObject newer=new JSONObject();a.session.pending=newer;
      a.desktopImageReady(1,25000,a.session.web.host,J.held,new boolean[1],new boolean[1],true,a.session.web.target);
      check(a.taps==0&&a.session.pending==newer,"already tapped must not overwrite or tap again");
    }else throw new AssertionError("unknown scenario");
    System.out.println("fixture-control-passed:"+mode+":"+(own?"own":"external"));
  }
}
'''


class DesktopImagePendingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        cls.compiler = Path(home) / 'bin/javac' if home else Path(shutil.which('javac') or '')
        cls.runtime = cls.compiler.with_name('java')
        cls.jar = Path(os.environ.get('PROFILE_JSON_JAR', ROOT/'work/gecko-integration/catalog-json.jar'))
        assert cls.compiler.is_file() and cls.runtime.is_file() and cls.jar.is_file(), 'Actual JDK and JSON jar required'
        cls.temporary = tempfile.TemporaryDirectory();cls.directory = Path(cls.temporary.name)
        cls.current = cls.compile(methods(), 'current')

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    @classmethod
    def compile(cls, body, name):
        directory = cls.directory/name;directory.mkdir()
        files = dict(STUBS, **{'GeckoIntegrationTestActivity.java': HOST.replace('__METHODS__', body)})
        for name, source in files.items():
            path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source)
        command=[str(cls.compiler),'-encoding','UTF-8','-cp',str(cls.jar),'-d',str(directory)] + [str(directory/name) for name in files]
        built=subprocess.run(command,capture_output=True,text=True,timeout=25)
        if built.returncode: raise AssertionError('Actual fixture methods did not compile: '+built.stderr)
        return directory

    def run_fixture(self, directory, mode, own=False):
        return subprocess.run([str(self.runtime),'-cp',str(directory)+os.pathsep+str(self.jar),
            'GeckoIntegrationTestActivity',mode,'own' if own else 'external'],capture_output=True,text=True,timeout=10)

    def passes(self, mode):
        for own in (False,True):
            result=self.run_fixture(self.current,mode,own)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('fixture-control-passed:'+mode,result.stdout)

    def test_actual_methods_retain_pending_for_both_providers(self): self.passes('ordinary')
    def test_all_three_ready_document_gates_precede_pending_and_input(self): self.passes('gates')
    def test_old_invocation_and_callback_cannot_touch_new_invocation(self): self.passes('stale')
    def test_original_deadline_and_poll_intervals_remain_bounded(self): self.passes('deadline')
    def test_already_tapped_does_not_retap_or_overwrite_pending(self): self.passes('already')

    def test_original_scoped_git_methods_fail_the_same_both_provider_control(self):
        original=SNIPPET.read_bytes()
        self.assertEqual(len(original),4008);self.assertEqual(hashlib.sha256(original).hexdigest(),HISTORICAL_SHA)
        directory=self.compile(original.decode(),'historical-1178')
        for own in (False,True):
            result=self.run_fixture(directory,'ordinary',own)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('held pending must precede first actual upload tap',result.stderr)

    def test_seven_compiled_semantic_changes_fail_their_behavior_control(self):
        changes=(
            ('session.pending=held;tapElement(serial,"upload")','tapElement(serial,"upload")','ordinary'),
            ('      if(serial!=run)return;\n','','stale'),
            ('!touched&&current.optBoolean("ready")','!touched','gates'),
            ('&&session.web.hasVisibleDocument()','','gates'),
            ('&&!session.navigating','','gates'),
            ('if(!touched&&current.optBoolean("ready")','if(current.optBoolean("ready")','already'),
            ('session.pending==held','session.pending!=held','ordinary'),
        )
        body=methods()
        for index,(old,new,scenario) in enumerate(changes):
            self.assertEqual(body.count(old),1,old)
            directory=self.compile(body.replace(old,new,1),'negative-'+str(index))
            result=self.run_fixture(directory,scenario)
            with self.subTest(change=old):
                self.assertNotEqual(result.returncode,0)
                self.assertIn('AssertionError',result.stderr)


if __name__ == '__main__': unittest.main()
