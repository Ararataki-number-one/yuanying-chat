#!/usr/bin/env python3
"""Execute actual pending-view button callbacks against explicit host viewer failures."""
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
        check("Pending "+mime+" / "+outcome+" has truthful UI callback result",d.a.starts==1&&d.a.message.equals(expected)&&!d.a.message.contains("文件已保存")&&d.a.lastUri.equals(row.optString("pendingDestination")));
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
    }
    FileDownloads d=new FileDownloads();d.a.outcome="no-viewer";
    ui(()->{d.openSaved(Uri.parse("content://known.saved/confirmed"),"application/octet-stream");return null;});
    check("Confirmed default-title overload retains existing saved message",d.a.message.equals("文件已保存；手机尚未安装支持此格式的查看器"));
  }
  public static void main(String[] args)throws Exception {
    try{pendingCases();savedCases();}finally{queue.shutdownNow();}
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
final class MainActivity {
  final Session session=new Session();String message="",outcome="success",lastUri="";int starts;
  void status(String value){message=value;}int dp(int n){return n;}TextView label(String value,int size,int color){return new TextView();}
  void startActivity(Intent intent){starts++;lastUri=intent.uri;if(outcome.equals("no-viewer"))throw new ActivityNotFoundException();if(outcome.equals("permission-denied"))throw new SecurityException("Injected permission denial");}
}
final class Session {boolean transferActive;void updateBrowserActivity(){}}
final class DownloadTasks {boolean recovering;int saves;File partial(JSONObject r){return null;}static String progress(JSONObject r){return "fixture progress";}}
final class SavedFileActions {int shown;void show(JSONObject r){shown++;}}
final class DownloadResumePolicy {static final String RESTART="重新下载";}
final class Uri {final String value;Uri(String value){this.value=value;}static Uri parse(String value){return new Uri(value);}public String toString(){return value;}}
final class Intent {static final String ACTION_VIEW="view";static final int FLAG_GRANT_READ_URI_PERMISSION=1;String uri="";Intent(String action){}Intent(MainActivity a,Object preview){}Intent putExtra(String key,String value){if(key.equals("uri"))uri=value;return this;}Intent setDataAndType(Uri value,String type){uri=value.toString();return this;}Intent addFlags(int flags){return this;}}
final class Profiles {static Object preview(MainActivity a){return new Object();}}
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
    source = ROOT / 'app/src/main/java/local/pocketchat/FileDownloads.java'
    text = source.read_text()
    needles = ['void taskActions(', 'void openSaved(Uri uri,String type)', 'void openSaved(Uri uri,String type,String title)', 'void openSaved(Uri uri,String type,String title,boolean confirmed)']
    methods = [adapter.member(text, needle) for needle in needles]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [source, Path(__file__).resolve(), ROOT / 'tests/download-resume-host/run.py']}
    java = JAVA.replace('/* ACTUAL_METHODS */', '\n'.join(methods))
    binary = lambda name: str(args.java_home / 'bin' / name) if args.java_home else name
    with tempfile.TemporaryDirectory(prefix='pending-viewer-closure-') as directory:
        temp = Path(directory)
        code = temp / 'PendingViewerHost.java'
        code.write_text(java)
        subprocess.run([binary('javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()), str(code)], check=True)
        result = subprocess.run([binary('java'), '-cp', str(temp) + os.pathsep + str(args.json_jar.resolve()), 'PendingViewerHost'], capture_output=True, text=True, timeout=30)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.stdout.txt').write_text(result.stdout)
    args.output.with_suffix('.stderr.txt').write_text(result.stderr)
    report = json.loads(result.stdout)
    report.update(sourceFiles=hashes, selectedProductionMethods=needles, selectedMethodSha256=[hashlib.sha256(method.encode()).hexdigest() for method in methods], executionInputsUnchanged=all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items()), jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(), actualAndroidExecution=False, actualExternalProviderExecution=False, scope='Exact production taskActions creates the pending-view button; its actual callback and all production openSaved overloads execute on a host UI queue. Viewer success, missing handler and permission denial are explicit host injections. Pending JSON and real host source bytes remain unchanged; no Android/provider behavior claimed.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['status', 'passed', 'total', 'executionInputsUnchanged']}))
    if result.returncode or report['status'] != 'passed' or not report['executionInputsUnchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
