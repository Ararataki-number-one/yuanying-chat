#!/usr/bin/env python3
"""Exercise production file opens, grants and error handling with host viewer doubles."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('download_members', ROOT / 'tests/download-resume-host/run.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

JAVA = r'''
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.function.*;import org.json.*;
public final class PendingViewerHost {
  static final JSONArray checks=new JSONArray();
  static final ExecutorService queue=Executors.newSingleThreadExecutor(r->new Thread(r,"host-ui-viewer"));
  static <T>T ui(Callable<T> callback)throws Exception {return queue.submit(callback).get(5,TimeUnit.SECONDS);}
  static void check(String name,boolean pass)throws Exception {checks.put(new JSONObject().put("name",name).put("pass",pass));}
  static void pendingCases()throws Exception {
    for(String mime:new String[]{"application/octet-stream","application/pdf","image/png"})for(String outcome:new String[]{"success","no-viewer","permission-denied"}){
      FileDownloads d=new FileDownloads();d.a.outcome=outcome;
      Path partial=Files.createTempFile("pending-viewer-source-",".part");byte[] bytes=new byte[]{2,4,6};Files.write(partial,bytes);
      try{
        JSONObject row=new JSONObject().put("id","fixture").put("state","paused").put("reason","保存结果待确认").put("complete",true).put("partial",partial.toString()).put("mime",mime).put("name","source.bin").put("pendingName","待确认.bin").put("pendingDestination","content://external.fixture/unresolved-target").put("pendingGeneration","fixture-generation").put("pendingOwner","fixture-owner");
        String before=row.toString();d.a.message="保存结果待确认";
        ui(()->{d.taskActions(row);Button button=((LinearLayout)AppAppearance.last.view).buttons.get(0);if(!button.text.equals("查看待确认文件"))throw new AssertionError("actual pending action missing");button.click();return null;});
        String expected=outcome.equals("no-viewer")?"保存结果仍待确认；手机尚未安装支持此格式的查看器":outcome.equals("permission-denied")?"保存结果仍待确认；无法访问原保存位置，请检查文件权限后重试核验":"保存结果待确认";
        check("Pending "+mime+" / "+outcome+" has truthful UI callback result",d.a.starts==1&&d.a.message.equals(expected)&&!d.a.message.contains("文件已保存")&&d.a.externalView(row.optString("pendingDestination"),mime));
        check("Pending "+mime+" / "+outcome+" preserves metadata, source and confirmation state",before.equals(row.toString())&&Files.exists(partial)&&Arrays.equals(Files.readAllBytes(partial),bytes)&&d.tasks.saves==0&&d.savedActions.shown==0);
      }finally{Files.deleteIfExists(partial);}
    }
  }
  static void savedCases()throws Exception {
    for(String mime:new String[]{"application/octet-stream","application/pdf","image/png"})for(String outcome:new String[]{"success","no-viewer","permission-denied"}){
      FileDownloads d=new FileDownloads();d.a.outcome=outcome;
      ui(()->{d.openSaved(Uri.parse("content://known.saved/confirmed"),mime,"saved.bin");return null;});
      String expected=outcome.equals("no-viewer")?"文件已保存；手机尚未安装支持此格式的查看器":outcome.equals("permission-denied")?"文件已移动或访问失效，请重新下载":"";
      check("Confirmed "+mime+" / "+outcome+" retains saved viewer behavior",d.a.starts==1&&d.a.message.equals(expected));
      Activity saved=new Activity();saved.outcome=outcome;
      JSONObject row=new JSONObject().put("uri","content://known.saved/confirmed").put("mime","application/octet-stream").put("actualMime",mime+"; fixture=ignored");
      ui(()->{SavedFileActions.open(saved,row);return null;});
      String savedMessage=outcome.equals("no-viewer")?"手机尚未安装支持此格式的查看器":outcome.equals("permission-denied")?"文件无法打开，可能已移动或访问权限已失效":"";
      check("Saved row "+mime+" / "+outcome+" uses the external viewer and saved MIME",saved.starts==1&&saved.externalView(row.optString("uri"),mime)&&saved.message.equals(savedMessage));
    }
    FileDownloads d=new FileDownloads();d.a.outcome="no-viewer";
    ui(()->{d.openSaved(Uri.parse("content://known.saved/confirmed"),"application/octet-stream");return null;});
    check("Confirmed default-title overload retains existing saved message",d.a.message.equals("文件已保存；手机尚未安装支持此格式的查看器"));
  }
  static void attachmentCases()throws Exception {
    Attachments attachments=new Attachments();
    MainActivity a=attachments.a;
    a.session.attachments.put(new JSONObject().put("uri","content://known.saved/photo").put("name","photo.png").put("mime","image/png"));
    ui(()->{attachments.preview("","photo.png");return null;});
    check("Local attachment opens in the external image viewer",a.starts==1&&a.externalView("content://known.saved/photo","image/png"));
    a.prefs.put("preview:current|archive|doc.pdf",new JSONObject().put("uri","content://known.saved/doc").put("mime","application/pdf").toString());
    ui(()->{attachments.preview("archive","doc.pdf");return null;});
    check("Archived attachment keeps its content URI and PDF type",a.starts==2&&a.externalView("content://known.saved/doc","application/pdf"));
    a.outcome="no-viewer";
    ui(()->{attachments.preview("archive","doc.pdf");return null;});
    check("Missing viewer is explained without a preview fallback",a.starts==3&&a.pageOpens==0&&a.message.equals("手机尚未安装支持此格式的查看器"));
    ui(()->{attachments.preview("archive","absent.pdf");return null;});
    check("An attachment without a local copy keeps the website fallback",a.starts==3&&a.pageOpens==1);
    a.outcome="success";
    a.prefs.put("preview:current|archive|legacy.PDF",new JSONObject().put("uri","content://known.saved/legacy").toString());
    ui(()->{attachments.preview("archive","legacy.PDF");return null;});
    check("Legacy attachment without MIME uses its file extension",a.starts==4&&a.externalView("content://known.saved/legacy","application/pdf"));
    a.prefs.put("preview:current|archive|invalid.pdf",new JSONObject().put("uri","file:///local/unavailable.pdf").toString());
    ui(()->{attachments.preview("archive","invalid.pdf");return null;});
    check("An invalid URI does not get passed to an external activity",a.starts==4&&a.message.equals("附件无法打开，可能已移动或访问权限已失效"));
  }
  public static void main(String[] args)throws Exception {
    try{pendingCases();savedCases();attachmentCases();}finally{queue.shutdownNow();}
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).getBoolean("pass"))passed++;
    System.out.println(new JSONObject().put("status",passed==checks.length()?"passed":"failed").put("passed",passed).put("total",checks.length()).put("checks",checks));
    if(passed!=checks.length())System.exit(1);
  }
}
final class FileDownloads {
  final MainActivity a=new MainActivity();final DownloadTasks tasks=new DownloadTasks();final SavedFileActions savedActions=new SavedFileActions();
  boolean retiringPartial,active,minimized,awaitingPicker,completeFile,cancelled;JSONObject task;String name="文件",retryUrl="",sourceId="";long ticket;
  void showProgress(String v){}void pause(){}void requestCancel(){}String continuationAction(JSONObject r){return "继续保存";}void requestRedownload(JSONObject r){}boolean loadTask(JSONObject r){return false;}boolean sameSource(){return true;}void retry(){}void chooseManually(long ticket){}
  /* ACTUAL_METHODS */
}
class Activity {
  String message="",outcome="success";int starts;Intent lastIntent;
  void status(String value){message=value;}
  void startActivity(Intent intent){starts++;lastIntent=intent;if(outcome.equals("no-viewer"))throw new ActivityNotFoundException();if(outcome.equals("permission-denied"))throw new SecurityException("Injected permission denial");}
  boolean externalView(String uri,String mime){return Intent.ACTION_VIEW.equals(lastIntent.action)&&uri.equals(lastIntent.uri.toString())&&mime.equals(lastIntent.mime)&&lastIntent.flags==Intent.FLAG_GRANT_READ_URI_PERMISSION&&lastIntent.clip.uri==lastIntent.uri;}
}
final class MainActivity extends Activity {
  final Session session=new Session();final Prefs prefs=new Prefs();String conversation="current";int pageOpens;
  int dp(int n){return n;}TextView label(String value,int size,int color){return new TextView();}void showPage(boolean opened){pageOpens++;}
}
final class Prefs extends HashMap<String,String>{String getString(String key,String fallback){return getOrDefault(key,fallback);}}
final class J{static JSONObject parse(String value){return new JSONObject(value);}}
final class Attachments{final MainActivity a=new MainActivity();/* ATTACHMENT_OPEN */}
final class Session {final JSONArray attachments=new JSONArray();boolean transferActive;void updateBrowserActivity(){}}
final class DownloadTasks {boolean recovering;int saves;File partial(JSONObject r){return null;}static String progress(JSONObject r){return "fixture progress";}}
final class SavedFileActions {
  int shown;void show(JSONObject r){shown++;}
  static void problem(Activity a,String message){a.status(message);}
  /* SAVED_FILE_OPEN */
}
final class DownloadMetadataValues {/* SAVED_FILE_METADATA */}
final class DownloadResumePolicy {static final String RESTART="重新下载";}
final class Uri {final String value;Uri(String value){this.value=value;}static Uri parse(String value){return new Uri(value);}public String toString(){return value;}String getScheme(){return java.net.URI.create(value).getScheme();}String getAuthority(){return java.net.URI.create(value).getAuthority();}}
final class ClipData {final Uri uri;ClipData(Uri uri){this.uri=uri;}static ClipData newRawUri(String label,Uri uri){return new ClipData(uri);}}
final class MimeTypeMap {
  static MimeTypeMap getSingleton(){return new MimeTypeMap();}
  String getMimeTypeFromExtension(String value){return "pdf".equals(value)?"application/pdf":null;}
}
final class Intent {
  static final String ACTION_VIEW="view";static final int FLAG_GRANT_READ_URI_PERMISSION=1;final String action;Uri uri;String mime;ClipData clip;int flags;
  Intent(String action){this.action=action;}
  static String normalizeMimeType(String mime){return mime==null?null:mime.trim().toLowerCase(Locale.ROOT).split(";",2)[0];}
  Intent setDataAndType(Uri value,String type){uri=value;mime=type;return this;}
  Intent addFlags(int added){flags|=added;return this;}
  void setClipData(ClipData data){clip=data;}
}
final class ActivityNotFoundException extends RuntimeException {}
final class Ui {static final int MUTED=0;}
class TextView {void setPadding(int a,int b,int c,int d){}}
final class Button extends TextView {String text;Consumer<Object> listener;Button(MainActivity a){}void setText(String value){text=value;}void setOnClickListener(Consumer<Object> value){listener=value;}void click(){listener.accept(this);}}
final class LinearLayout {static final int VERTICAL=1;final List<Button> buttons=new ArrayList<>();LinearLayout(MainActivity a){}void setOrientation(int value){}void addView(Object v){if(v instanceof Button)buttons.add((Button)v);}}
final class AppAppearance {static Builder last;static Builder dialog(MainActivity a){return last=new Builder();}}
final class Builder {Object view;Builder setTitle(String v){return this;}Builder setView(Object v){view=v;return this;}Builder setItems(String[] v,BiConsumer<Object,Integer> action){return this;}Builder setPositiveButton(String v,BiConsumer<Object,Integer> action){return this;}Builder setNeutralButton(String v,BiConsumer<Object,Integer> action){return this;}Builder setNegativeButton(String v,BiConsumer<Object,Integer> action){return this;}void show(){}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    production = ROOT / 'app/src/main/java/local/pocketchat'
    selections = {
        'ACTUAL_METHODS': ('FileDownloads.java', ['void taskActions(', 'void openSaved(Uri uri,String type)',
            'void openSaved(Uri uri,String type,String title)', 'void openSaved(Uri uri,String type,String title,boolean confirmed)']),
        'SAVED_FILE_OPEN': ('SavedFileActions.java', ['private static boolean documentUri(', 'static Intent openIntent(', 'static void open(Activity a,JSONObject row)']),
        'SAVED_FILE_METADATA': ('DownloadMetadataValues.java', ['static String mime(', 'static String name(']),
        'ATTACHMENT_OPEN': ('Attachments.java', ['void preview(String message,String name)']),
    }
    java = JAVA
    needles, methods = [], []
    inputs = [Path(__file__).resolve(), ROOT / 'tests/download-resume-host/run.py']
    for token, (file_name, signatures) in selections.items():
        source = production / file_name
        inputs.append(source)
        selected = [adapter.member(source.read_text(encoding='utf-8'), item) for item in signatures]
        java = java.replace('/* '+token+' */', '\n'.join(selected))
        needles.extend(signatures)
        methods.extend(selected)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    binary = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    with tempfile.TemporaryDirectory(prefix='pending-viewer-closure-') as directory:
        temp = Path(directory)
        code = temp / 'PendingViewerHost.java'
        code.write_text(java, encoding='utf-8')
        subprocess.run([binary('javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()), str(code)], check=True)
        result = subprocess.run([binary('java'), '-cp', str(temp) + os.pathsep + str(args.json_jar.resolve()), 'PendingViewerHost'], capture_output=True, text=True, timeout=30)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.stdout.txt').write_text(result.stdout)
    args.output.with_suffix('.stderr.txt').write_text(result.stderr)
    report = json.loads(result.stdout)
    report.update(sourceFiles=hashes, selectedProductionMethods=needles, selectedMethodSha256=[hashlib.sha256(method.encode()).hexdigest() for method in methods], executionInputsUnchanged=all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items()), jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(), actualAndroidExecution=False, actualExternalProviderExecution=False, scope='Production saved, pending and attachment open callbacks run on a host UI queue. Intent action, URI, MIME, read grant and clip are checked against host doubles. Viewer success, missing handler and permission denial are explicit host injections.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['status', 'passed', 'total', 'executionInputsUnchanged']}))
    if result.returncode or report['status'] != 'passed' or not report['executionInputsUnchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
