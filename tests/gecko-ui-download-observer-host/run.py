#!/usr/bin/env python3
"""Execute source-bound native observation logic with explicit host Android adapters.

The adapters expose controlled geometry, not Android rendering or device evidence.
No production code is changed, and no UI acceptance gate is replaced by this test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OBSERVER = ROOT / 'tests/gecko/DownloadLocationLayoutEvidence.java'
ACTIVITY = ROOT / 'tests/gecko/UiVisualIntegrationActivity.java'
PINS = {
    'observer': '31f238e1ca1a94b59cc924a4e21822d078da087687daf8885f4c467de6dfb77e',
    'activity': '29d641025853a52cf00dbffb9fccad54126e33d04805f8f4dfe483fafb3180a5',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def member(source, needle):
    start = source.index(needle)
    opened = source.index('{', start)
    depth = 0
    quote = None
    escaped = line = block = False
    index = opened
    while index < len(source):
        char, pair = source[index], source[index:index + 2]
        if line:
            if char == '\n':
                line = False
        elif block:
            if pair == '*/':
                block = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif pair == '//':
            line = True
            index += 1
        elif pair == '/*':
            block = True
            index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
        index += 1
    raise ValueError('Incomplete actual Activity member: ' + needle)


STUBS = {
    'android/app/Activity.java': '''package android.app;
public class Activity {
  public String packageName="local.pocketchat.test";
  public android.content.Intent intent=new android.content.Intent();
  public final android.content.res.AssetManager assets=new android.content.res.AssetManager();
  public final android.content.res.Resources resources=new android.content.res.Resources();
  public int superclassIntents,mutations;
  protected void onNewIntent(android.content.Intent request){superclassIntents++;}
  public String getPackageName(){return packageName;}
  public android.content.Intent getIntent(){return intent;}
  public android.content.res.AssetManager getAssets(){return assets;}
  public android.content.res.Resources getResources(){return resources;}
  public void setIntent(android.content.Intent value){mutations++;throw new AssertionError("setIntent changed fixture ownership");}
  public void setContentView(android.view.View value){mutations++;throw new AssertionError("UI reconstruction");}
  public void startActivity(android.content.Intent value){mutations++;throw new AssertionError("UI navigation");}
}''',
    'android/content/Intent.java': '''package android.content;
public final class Intent {
  public final java.util.Map<String,String> extras=new java.util.HashMap<>();
  public boolean unreadable;
  public Intent putExtra(String name,String value){extras.put(name,value);return this;}
  public String getStringExtra(String name){if(unreadable)throw new IllegalArgumentException("Unreadable extras");return extras.get(name);}
}''',
    'android/content/res/AssetManager.java': '''package android.content.res;
public final class AssetManager {
  public String stamp="{\\"sourceCommit\\":\\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\",\\"dirtySource\\":false}";
  public int opens;
  public java.io.InputStream open(String name)throws java.io.IOException{
    if(!"pocketchat-integration-build.json".equals(name))throw new AssertionError("Wrong source asset");
    opens++;return new java.io.ByteArrayInputStream(stamp.getBytes(java.nio.charset.StandardCharsets.UTF_8));
  }
}''',
    'android/content/res/Resources.java': '''package android.content.res;
public final class Resources {
  public final Configuration configuration=new Configuration();
  public final android.util.DisplayMetrics metrics=new android.util.DisplayMetrics();
  public Configuration getConfiguration(){return configuration;}
  public android.util.DisplayMetrics getDisplayMetrics(){return metrics;}
}''',
    'android/content/res/Configuration.java': 'package android.content.res;public final class Configuration {public float fontScale=1f;}',
    'android/util/DisplayMetrics.java': 'package android.util;public final class DisplayMetrics {public float density=3f;}',
    'android/graphics/Rect.java': '''package android.graphics;
public final class Rect {public int left,top,right,bottom;public int width(){return right-left;}public int height(){return bottom-top;}}''',
    'android/os/Looper.java': 'package android.os;public final class Looper {public static Looper getMainLooper(){return new Looper();}}',
    'android/os/SystemClock.java': 'package android.os;public final class SystemClock {public static long now=100;public static long uptimeMillis(){return now;}}',
    'android/os/Handler.java': '''package android.os;
public final class Handler {
  public static final java.util.List<Long> allDelays=new java.util.ArrayList<>();
  public final java.util.List<Runnable> posted=new java.util.ArrayList<>(),delayed=new java.util.ArrayList<>();
  public int removed;
  public Handler(Looper ignored){}
  public boolean post(Runnable value){posted.add(value);return true;}
  public boolean postDelayed(Runnable value,long delay){allDelays.add(delay);delayed.add(value);return true;}
  public void removeCallbacks(Runnable value){removed++;posted.remove(value);delayed.remove(value);}
  public void runPosted(){java.util.List<Runnable> copy=new java.util.ArrayList<>(posted);posted.clear();for(Runnable value:copy)value.run();}
  public void runDelayed(){java.util.List<Runnable> copy=new java.util.ArrayList<>(delayed);delayed.clear();for(Runnable value:copy)value.run();}
}''',
    'android/util/Log.java': '''package android.util;
public final class Log {
  public static final java.util.List<String> records=new java.util.ArrayList<>();
  public static int i(String tag,String raw){records.add(raw);return 0;}
  public static int w(String tag,String raw){records.add(raw);return 0;}
  public static int e(String tag,String raw){records.add(raw);return 0;}
}''',
    'android/view/ViewTreeObserver.java': '''package android.view;
public final class ViewTreeObserver {
  public interface OnPreDrawListener {boolean onPreDraw();}
  public final java.util.List<OnPreDrawListener> listeners=new java.util.ArrayList<>();
  public int added,removed;
  public boolean alive=true;
  public void addOnPreDrawListener(OnPreDrawListener value){added++;listeners.add(value);}
  public void removeOnPreDrawListener(OnPreDrawListener value){removed++;listeners.remove(value);}
  public boolean isAlive(){return alive;}
}''',
    'android/view/View.java': '''package android.view;
public class View {
  public boolean requested,laidOut=true,attached=true,focused=true,shown=true,enabled=true,clickable=true,globallyVisible=true;
  public int width=192,height=144,left=20,top=750,visibleWidth=192,visibleHeight=78,scrollX,scrollY,mutations;
  public final ViewTreeObserver observer=new ViewTreeObserver();
  public ViewTreeObserver getViewTreeObserver(){return observer;}
  public boolean isLayoutRequested(){return requested;}
  public boolean isLaidOut(){return laidOut;}
  public boolean isAttachedToWindow(){return attached;}
  public boolean hasWindowFocus(){return focused;}
  public int getWidth(){return width;}public int getHeight(){return height;}
  public boolean getGlobalVisibleRect(android.graphics.Rect out){out.left=left;out.top=top;out.right=left+visibleWidth;out.bottom=top+visibleHeight;return globallyVisible;}
  public void getLocationOnScreen(int[] point){point[0]=left;point[1]=top;}
  public boolean isShown(){return shown;}public boolean isEnabled(){return enabled;}public boolean isClickable(){return clickable;}
  public int getScrollX(){return scrollX;}public int getScrollY(){return scrollY;}
  public void requestLayout(){mutations++;throw new AssertionError("Layout mutation");}
  public void invalidate(){mutations++;throw new AssertionError("Draw invalidation");}
  public void scrollTo(int x,int y){mutations++;throw new AssertionError("Scroll mutation");}
  public void scrollBy(int x,int y){mutations++;throw new AssertionError("Scroll mutation");}
  public void setVisibility(int value){mutations++;throw new AssertionError("Visibility mutation");}
  public void layout(int l,int t,int r,int b){mutations++;throw new AssertionError("Layout mutation");}
}''',
    'android/view/ViewGroup.java': '''package android.view;
public class ViewGroup extends View {
  public final java.util.List<View> children=new java.util.ArrayList<>();
  public int getChildCount(){return children.size();}public View getChildAt(int index){return children.get(index);}
}''',
    'android/text/Layout.java': '''package android.text;
public class Layout {
  public int lineCount=1,ellipsisCount,width=176,height=80;
  public CharSequence text="保存位置";
  public int getLineCount(){return lineCount;}public int getLineStart(int index){return 0;}public int getLineEnd(int index){return text.length();}
  public float getLineLeft(int index){return 0f;}public float getLineRight(int index){return 160f;}
  public int getLineBottom(int index){return 80;}public int getEllipsisCount(int index){return ellipsisCount;}
  public CharSequence getText(){return text;}public int getWidth(){return width;}public int getHeight(){return height;}
}''',
    'android/widget/Button.java': '''package android.widget;
public class Button extends android.view.View {
  public CharSequence text="保存位置";public android.text.Layout layout=new android.text.Layout();
  public CharSequence getText(){return text;}public android.text.Layout getLayout(){return layout;}
  public int getCompoundPaddingLeft(){return 8;}public int getCompoundPaddingRight(){return 8;}
  public int getCompoundPaddingTop(){return 16;}public int getCompoundPaddingBottom(){return 16;}
}''',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/ui-download-observer-host/results.json')
    args = parser.parse_args()
    sources = {'observer': OBSERVER.read_bytes(), 'activity': ACTIVITY.read_bytes()}
    assert {key: digest(value) for key, value in sources.items()} == PINS, 'Unreviewed complete observer/activity source'
    activity = sources['activity'].decode('utf-8')
    needles = ('@Override protected void onNewIntent(Intent request)',
               'String downloadObservationRejection(Intent request)',
               'void rejectDownloadObservation(String nonce,String reason)')
    methods = [member(activity, value) for value in needles]
    template = (HERE / 'ObserverCases.java.in').read_text()
    assert template.count('/* ACTUAL_ACTIVITY_MEMBERS */') == 1
    cases = template.replace('/* ACTUAL_ACTIVITY_MEMBERS */', '\n'.join(methods))
    tool = lambda name: str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
    assert tool('java') and tool('javac'), 'JDK required'
    version = subprocess.check_output([tool('java'), '-version'], stderr=subprocess.STDOUT).decode()
    assert 'version "17.' in version, 'Use the CI JDK 17 toolchain'
    jar = args.json_jar.resolve()
    assert jar.is_file(), 'Real JSON dependency required'
    with tempfile.TemporaryDirectory(prefix='ui-download-observer-') as directory:
        base = Path(directory)
        values = dict(STUBS)
        values.update({'local/pocketchat/DownloadLocationLayoutEvidence.java': sources['observer'].decode(),
                       'local/pocketchat/ObserverCases.java': cases,
                       'local/pocketchat/J.java': (ROOT / 'app/src/main/java/local/pocketchat/J.java').read_text()})
        paths = []
        for name, text in values.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(str(path))
        classes = base / 'classes'
        subprocess.run([tool('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(classes), *paths], check=True)
        output = subprocess.check_output([tool('java'), '-cp', str(classes) + os.pathsep + str(jar), 'local.pocketchat.ObserverCases']).decode()
    result = json.loads(output)
    result.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                  sourceSha256=PINS, methodSha256={key: digest(value.encode()) for key, value in zip(needles, methods)},
                  adapterSha256=digest(Path(__file__).read_bytes()), caseTemplateSha256=digest((HERE / 'ObserverCases.java.in').read_bytes()),
                  jsonJarSha256=digest(jar.read_bytes()), javaVersion=version.splitlines()[0], actualAndroidExecution=False,
                  boundary='Explicit synthetic Android View/Layout/Activity/Intent/Handler/assets adapters; complete actual observer and verbatim Activity methods')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
