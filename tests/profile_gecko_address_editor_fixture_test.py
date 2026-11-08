"""Current native URL-editor fixture contract and preserved policy assertions.

The widget adapters below are explicit host models. Android API compilation
checks types only; neither result is a new device or IP-policy acceptance.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / 'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java'
IP = ROOT / 'tests/gecko/GeckoIpTimeZoneIntegrationActivity.java'
# Exact original fixture bytes at06a8026, read before this bounded patch. The
# inverse check needs no additional historical Git object in a shallow CI clone.
BEFORE_SHA = {
    'environment': 'd82c365f85dd14fd67f480bdd60175f96b3ce5b4bc79cc9f61d1b1e124f60574',
    'ip': 'ee8ac9afb5ca9d8c6a23fd0c88c5cbf3f5ba82854c78115e12ed25a45993f056',
}
MARKER = '  /** Current native address contract; never use a webpage field or a legacy label. */\n'


def current_helper():
    source = ENVIRONMENT.read_text()
    start = source.index('  static final class CurrentAddressEditor {')
    at = source.index('{', start)
    depth = 1
    end = at + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def java_tools():
    home = os.environ.get('JAVA_HOME')
    if home:
        return str(Path(home) / 'bin/javac'), str(Path(home) / 'bin/java')
    return 'javac', 'java'


HOST_STUBS = {
    'android/content/ContextWrapper.java': '''package android.content;
public class ContextWrapper {public Object base;public ContextWrapper(Object value){base=value;}public Object getBaseContext(){return base;}}
''',
    'android/graphics/Rect.java': '''package android.graphics;
public class Rect { public int left,top,right,bottom;
  public Rect(){} public Rect(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}
  public void set(Rect a){left=a.left;top=a.top;right=a.right;bottom=a.bottom;}
  public int width(){return right-left;}public int height(){return bottom-top;}
}
''',
    'android/view/View.java': '''package android.view;
public class View {
  public int width=100,height=48,x,y,scrollX,scrollY;public boolean attached=true,shown=true,enabled=true,clickable=true,focused=true,windowFocus=true;
  public ViewGroup parent;public android.graphics.Rect clip,frame=new android.graphics.Rect(0,0,1000,1000);
  public int clicks;public Runnable callback;
  public boolean isAttachedToWindow(){return attached;}
  public boolean isShown(){return shown&&(parent==null||parent.isShown());}
  public boolean isEnabled(){return enabled;}public boolean isClickable(){return clickable;}
  public boolean isFocused(){return focused;}public boolean hasWindowFocus(){return windowFocus;}
  public int getWidth(){return width;}public int getHeight(){return height;}
  public View getRootView(){return parent==null?this:parent.getRootView();}
  public boolean getLocalVisibleRect(android.graphics.Rect out){out.set(clip==null?new android.graphics.Rect(scrollX,scrollY,scrollX+width,scrollY+height):clip);return isShown();}
  public boolean getGlobalVisibleRect(android.graphics.Rect out){out.set(clip==null?new android.graphics.Rect(x,y,x+width,y+height):clip);return isShown();}
  public void getWindowVisibleDisplayFrame(android.graphics.Rect out){out.set(getRootView().frame);}
  public void getLocationOnScreen(int[] p){p[0]=x;p[1]=y;}
  public boolean performClick(){clicks++;if(callback!=null)callback.run();return true;}
}
''',
    'android/view/ViewGroup.java': '''package android.view;
public class ViewGroup extends View {
  public final java.util.ArrayList<View> children=new java.util.ArrayList<>();
  public void add(View v){if(v.parent!=null)v.parent.children.remove(v);children.add(v);v.parent=this;}
  public int getChildCount(){return children.size();}public View getChildAt(int i){return children.get(i);}
}
''',
    'android/view/Window.java': '''package android.view;
public class Window {public View decor;public View getDecorView(){return decor;}}
''',
    'android/widget/TextView.java': '''package android.widget;
public class TextView extends android.view.View {
  public CharSequence text="";public CharSequence getText(){return text;}public void setText(CharSequence v){text=v;}
}
''',
    'android/widget/EditText.java': '''package android.widget;
public class EditText extends TextView {
  public int inputType=17;public int getInputType(){return inputType;}
}
''',
    'android/widget/Button.java': '''package android.widget;
public class Button extends TextView {}
''',
    'android/text/InputType.java': '''package android.text;
public interface InputType {int TYPE_MASK_CLASS=15,TYPE_MASK_VARIATION=4080,TYPE_CLASS_TEXT=1,TYPE_TEXT_VARIATION_URI=16;}
''',
    'android/app/AlertDialog.java': '''package android.app;
public class AlertDialog {
  public static final int BUTTON_POSITIVE=-1,BUTTON_NEGATIVE=-2,BUTTON_NEUTRAL=-3;
  public boolean showing=true;public android.view.Window window=new android.view.Window();public Object context;
  public final java.util.HashMap<Integer,android.widget.Button> buttons=new java.util.HashMap<>();
  public boolean isShowing(){return showing;}public android.view.Window getWindow(){return window;}
  public Object getContext(){return context;}
  public android.widget.Button getButton(int id){return buttons.get(id);}
}
''',
    'android/webkit/WebView.java': '''package android.webkit;public class WebView extends android.view.ViewGroup {}
''',
    'org/mozilla/geckoview/GeckoView.java': '''package org.mozilla.geckoview;public class GeckoView extends android.view.ViewGroup {}
''',
    'local/pocketchat/MainActivity.java': '''package local.pocketchat;
class MainActivity {GeckoAddressUi geckoAddress;}
''',
    'local/pocketchat/GeckoAddressUi.java': '''package local.pocketchat;
class GeckoAddressUi {
  final MainActivity a;private android.app.AlertDialog dialog;private android.widget.EditText editor;
  GeckoAddressUi(MainActivity a,android.app.AlertDialog d,android.widget.EditText e){this.a=a;dialog=d;editor=e;}
}
''',
    'local/pocketchat/GeckoWebView.java': '''package local.pocketchat;class GeckoWebView extends android.view.ViewGroup {}
''',
}


HOST_PROGRAM = r'''
package local.pocketchat;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.Field;
public final class AddressFixtureHost {
__ACTUAL_HELPER__
  static int checks;
  static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
  static final class Scene {
    MainActivity owner=new MainActivity();android.app.AlertDialog dialog=new android.app.AlertDialog();
    ViewGroup root=new ViewGroup(),row=new ViewGroup();
    EditText input=new EditText();TextView title=new TextView();
    Button go=new Button(),home=new Button(),cancel=new Button();
    Scene(){
      root.width=1000;root.height=500;root.add(title);root.add(row);row.add(input);
      title.setText("打开网址");title.width=160;title.x=10;title.y=10;
      input.width=600;input.x=10;input.y=80;
      go.setText("前往");go.x=700;go.y=400;home.setText("主页");home.x=10;home.y=400;
      cancel.setText("取消");cancel.x=500;cancel.y=400;
      root.add(go);root.add(home);root.add(cancel);dialog.window.decor=root;dialog.context=owner;
      dialog.buttons.put(-1,go);dialog.buttons.put(-3,home);dialog.buttons.put(-2,cancel);
      owner.geckoAddress=new GeckoAddressUi(owner,dialog,input);
    }
    CurrentAddressEditor read()throws Exception{return CurrentAddressEditor.read(owner);}
  }
  interface Change{void apply(Scene s)throws Exception;}
  static void rejects(String why,Change edit)throws Exception{
    Scene s=new Scene();edit.apply(s);check(s.read()==null,why);check(s.go.clicks==0,"no submit while "+why);
  }
  public static void main(String[] ignored)throws Exception{
    Scene normal=new Scene();CurrentAddressEditor state=normal.read();
    check(state!=null&&state.dialog==normal.dialog&&state.input==normal.input&&state.forward==normal.go,"actual owned objects");
    normal.input.setText("https://fp-a.pocketchat.test/gecko-restored");state.submit();
    check(normal.go.clicks==1&&normal.home.clicks==0&&normal.cancel.clicks==0,"one exact positive click");
    check(normal.input.getText().equals("https://fp-a.pocketchat.test/gecko-restored"),"target preserved");
    Scene compact=new Scene();compact.row.add(compact.title);compact.title.y=80;compact.input.x=200;
    check(compact.read()!=null,"same title alongside input remains current");
    Scene flags=new Scene();flags.input.inputType|=0x80000;check(flags.read()!=null,"URI with unrelated text flags");
    Scene scrolled=new Scene();scrolled.input.scrollX=700;check(scrolled.read()!=null,"long native URL text scroll is not widget clipping");
    Scene wrapped=new Scene();wrapped.dialog.context=new android.content.ContextWrapper(new android.content.ContextWrapper(wrapped.owner));check(wrapped.read()!=null,"actual owner through native theme wrappers");
    Scene hiddenOld=new Scene();Button hidden=new Button();hidden.setText("取消");hidden.shown=false;hiddenOld.root.add(hidden);
    check(hiddenOld.read()!=null,"hidden old duplicate is not selected");
    rejects("legacy positive",s->s.go.setText("打开"));
    rejects("title missing",s->s.title.shown=false);
    rejects("wrong title",s->s.title.setText("打开文件"));
    rejects("not URI",s->s.input.inputType=129);
    rejects("field hidden",s->s.input.shown=false);
    rejects("field detached",s->s.input.attached=false);
    rejects("no input focus",s->s.input.focused=false);
    rejects("no native window focus",s->s.root.windowFocus=false);
    rejects("dialog not showing",s->s.dialog.showing=false);
    rejects("dialog window gone",s->s.dialog.window=null);
    rejects("field clipped locally",s->s.input.clip=new android.graphics.Rect(0,1,600,48));
    rejects("field below visible display",s->s.root.frame.bottom=100);
    rejects("field outside owner root",s->{s.row.children.remove(s.input);s.input.parent=null;});
    rejects("duplicate native field",s->s.row.add(new EditText()));
    rejects("wrong owner",s->{MainActivity other=new MainActivity();s.owner.geckoAddress=new GeckoAddressUi(other,s.dialog,s.input);});
    rejects("foreign native window context",s->s.dialog.context=new MainActivity());
    rejects("cyclic native context",s->{android.content.ContextWrapper cyclic=new android.content.ContextWrapper(null);cyclic.base=cyclic;s.dialog.context=cyclic;});
    rejects("duplicate title",s->{TextView t=new TextView();t.setText("打开网址");s.root.add(t);});
    rejects("duplicate positive",s->{Button b=new Button();b.setText("前往");s.root.add(b);});
    rejects("disabled positive",s->s.go.enabled=false);
    rejects("unclickable positive",s->s.go.clickable=false);
    rejects("hidden positive",s->s.go.shown=false);
    rejects("clipped positive",s->s.go.clip=new android.graphics.Rect(0,0,99,48));
    rejects("wrong home",s->s.home.setText("打开"));
    rejects("wrong cancel",s->s.cancel.setText("返回"));
    rejects("WebView descendant",s->s.root.add(new android.webkit.WebView()));
    rejects("GeckoView descendant",s->s.root.add(new org.mozilla.geckoview.GeckoView()));
    rejects("application Gecko frame",s->s.root.add(new GeckoWebView()));
    Scene closed=new Scene();CurrentAddressEditor stale=closed.read();closed.dialog.showing=false;
    boolean failed=false;try{stale.submit();}catch(IOException expected){failed=true;}
    check(failed&&closed.go.clicks==0,"closed stale state cannot submit");
    Scene replaced=new Scene();CurrentAddressEditor old=replaced.read();Scene newer=new Scene();
    replaced.owner.geckoAddress=new GeckoAddressUi(replaced.owner,newer.dialog,newer.input);
    failed=false;try{old.submit();}catch(IOException expected){failed=true;}
    check(failed&&replaced.go.clicks==0&&newer.go.clicks==0,"replacement cannot submit through old state");
    Scene injectionError=new Scene();CurrentAddressEditor once=injectionError.read();
    injectionError.go.callback=()->{throw new IllegalStateException("after-dispatch");};
    failed=false;try{once.submit();}catch(IllegalStateException expected){failed="after-dispatch".equals(expected.getMessage());}
    check(failed&&injectionError.go.clicks==1,"input exception propagates with no replay");
    check(CurrentAddressEditor.CONTRACT==2,"explicit current contract");
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false,\"scope\":\"actual helper methods with explicit host widget observations\"}");
  }
}
'''


class CurrentAddressFixtureTest(unittest.TestCase):
    def test_actual_current_helper_rejects_legacy_web_stale_hidden_clipped_and_duplicate_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for relative, text in HOST_STUBS.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                paths.append(str(path))
            program = root / 'local/pocketchat/AddressFixtureHost.java'
            program.write_text(HOST_PROGRAM.replace('__ACTUAL_HELPER__', current_helper()))
            compiler, java = java_tools()
            subprocess.run([compiler, '-encoding', 'UTF-8', '-d', str(root), *paths, str(program)],
                           check=True, capture_output=True)
            result = subprocess.check_output([java, '-cp', str(root), 'local.pocketchat.AddressFixtureHost']).decode()
            import json
            value = json.loads(result)
            self.assertEqual(value['status'], 'passed')
            self.assertGreaterEqual(value['checks'], 60)
            self.assertIs(value['actualAndroidExecution'], False)

    def test_current_helpers_compile_with_actual_android_api(self):
        selected = os.environ.get('PROFILE_ANDROID_JAR')
        sdk_candidates = tuple(Path(os.environ[key]) / 'platforms/android-35/android.jar'
                               for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT') if os.environ.get(key))
        candidates = (*sdk_candidates,
                      Path('/usr/local/lib/android/sdk/platforms/android-35/android.jar'),
                      Path('/tmp/pocketchat-shared-tools/android-35/android.jar'),
                      ROOT / 'work/cloud-setup/platform/android-35/android.jar',
                      Path('/workspace/yuanying-chat/work/cloud-setup/platform/android-35/android.jar'))
        android = Path(selected) if selected else next((path for path in candidates if path.is_file()), candidates[0])
        self.assertTrue(android.is_file(), 'Actual Android API jar is required')
        self.assertEqual(hashlib.sha256(android.read_bytes()).hexdigest(),
                         '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                'MainActivity.java': HOST_STUBS['local/pocketchat/MainActivity.java'],
                'GeckoAddressUi.java': HOST_STUBS['local/pocketchat/GeckoAddressUi.java'],
                'GeckoWebView.java': '''package local.pocketchat;class GeckoWebView extends android.view.View {GeckoWebView(android.content.Context c){super(c);}}\n''',
                'AddressApiCompile.java': '''package local.pocketchat;import android.view.*;import android.widget.*;import java.io.*;import java.lang.reflect.Field;final class AddressApiCompile {\n''' + current_helper() + '\n}\n',
            }
            paths = []
            for name, text in files.items():
                path = root / name
                path.write_text(text)
                paths.append(str(path))
            compiler, _ = java_tools()
            subprocess.run([compiler, '-encoding', 'UTF-8', '-cp', str(android),
                            '-d', str(root / 'classes'), *paths], check=True, capture_output=True)
            self.assertTrue((root / 'classes/local/pocketchat/AddressApiCompile$CurrentAddressEditor.class').is_file())

    def test_two_callsite_changes_and_helper_are_the_only_policy_fixture_changes(self):
        env = ENVIRONMENT.read_text()
        helper = current_helper()
        env = env.replace(MARKER + helper + '\n', '', 1)
        current = 'next("address-"+phase);geckoAddress.address.performClick();waitFor("actual address editor",()->CurrentAddressEditor.read(this)!=null,()->{CurrentAddressEditor editor=CurrentAddressEditor.require(this);EditText input=editor.input;input.setText("https://"+host+"/env-policy?phase="+phase);editor.submit();waitFor("address committed",()->ready()&&remote.getUrl().equals(input.getText().toString()),after);});'
        legacy = 'next("address-"+phase);geckoAddress.address.performClick();waitFor("actual address editor",()->window("打开")!=null,()->{View editor=window("打开");EditText input=first(editor,EditText.class);if(input==null)throw new IOException("Actual address field missing");input.setText("https://"+host+"/env-policy?phase="+phase);button(editor,"打开").performClick();waitFor("address committed",()->ready()&&remote.getUrl().equals(input.getText().toString()),after);});'
        self.assertEqual(env.count(current), 1)
        self.assertEqual(hashlib.sha256(env.replace(current, legacy, 1).encode()).hexdigest(), BEFORE_SHA['environment'])
        ip = IP.read_text()
        current_ip = '''geckoAddress.address.performClick();waitFor("actual negative target address",()->GeckoEnvironmentPolicyIntegrationActivity.CurrentAddressEditor.read(this)!=null,()->{
      GeckoEnvironmentPolicyIntegrationActivity.CurrentAddressEditor editor=GeckoEnvironmentPolicyIntegrationActivity.CurrentAddressEditor.require(this);editor.input.setText(ROOT+"gecko-restored");editor.submit();'''
        legacy_ip = '''geckoAddress.address.performClick();waitFor("actual negative target address",()->GeckoEnvironmentPolicyIntegrationActivity.window("打开")!=null,()->{
      View editor=GeckoEnvironmentPolicyIntegrationActivity.window("打开");GeckoEnvironmentPolicyIntegrationActivity.first(editor,EditText.class).setText(ROOT+"gecko-restored");GeckoEnvironmentPolicyIntegrationActivity.button(editor,"打开").performClick();'''
        self.assertEqual(ip.count(current_ip), 1)
        self.assertEqual(hashlib.sha256(ip.replace(current_ip, legacy_ip, 1).encode()).hexdigest(), BEFORE_SHA['ip'])
        production = (ROOT / 'app/src/main/java/local/pocketchat/GeckoAddressUi.java').read_text()
        self.assertIn('.setPositiveButton("前往",null)', production)
        self.assertNotIn('label.equals("打开")', helper)
        self.assertNotIn('session.browse', helper)
        self.assertEqual(helper.count('forward.performClick()'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
