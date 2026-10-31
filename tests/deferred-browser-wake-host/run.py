#!/usr/bin/env python3
"""Actual event-driven browser-setting wake + existing draft coordinator on declared JVM edges."""
import argparse,hashlib,json,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/review-host'))
from run_deferred_browser_host import production_member

def main():
 p=argparse.ArgumentParser();p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--before-source',type=pathlib.Path);a=p.parse_args();out=a.output.parent;out.mkdir(parents=True,exist_ok=True);prod=ROOT/'app/src/main/java/local/pocketchat';chatpath=a.before_source or prod/'ChatSession.java';chat=chatpath.read_text();fixed=a.before_source is None
 selections=['static ChatSession peek(','void completeReply(','void updateBrowserActivity(){','void updateBrowserActivity(boolean poll)','void resourceFileWork(','void resourceUploadObservation(','boolean uploading(','boolean fileWorkActive(','boolean resourceFilesActive(','boolean replyObservationAllowed(','boolean browserWorkActive(','void wakePolling(']
 methods={n:production_member(chat,n) for n in selections}
 wake='boolean deferredBrowserWakeQueued;final Runnable deferredBrowserWake=()->{throw new AssertionError("Unused current-wake boundary in original-source counterexample");};void wakeDeferredBrowserSettings(){throw new AssertionError("Original source unexpectedly called new maintenance wake");}'
 if fixed:
  wake=production_member(chat,'final Runnable deferredBrowserWake=')+';\n'+production_member(chat,'void wakeDeferredBrowserSettings(')
  wake=re.search(r'  boolean deferredBrowserWakeQueued;',chat).group(0)+'\n'+wake
 template=pathlib.Path(__file__).with_name('WakeHost.java.in');text=template.read_text().replace('@CHAT_METHODS@','\n'.join(methods.values())).replace('@WAKE_MEMBERS@',wake).replace('@TICK@',production_member(chat,'final Runnable tick=')+';')
 extra={'@TASK_IDLE@':('NetworkUiProvider.java','static boolean taskIdle('),'@PROFILE_WORKING@':('ProfileUi.java','static boolean working('),'@CHAT_URL@':('MainActivity.java','static boolean chatUrl('),'@COMPLETE_DRAFT@':('PageMemory.java','static boolean completeDraft('),'@HAS_DRAFT@':('PageMemory.java','static boolean hasDraft(')}
 for marker,(name,key) in extra.items():text=text.replace(marker,production_member((prod/name).read_text(),key))
 text=text.replace('package local.pocketchat;','package local.pocketchat;\nimport android.net.Uri;',1)
 generated=out/'generated';generated.mkdir(exist_ok=True);host=generated/'WakeHost.java';host.write_text(text)
 clock=generated/'SystemClock.java';clock.write_text('package android.os;public final class SystemClock{public static long now=20001;public static long elapsedRealtime(){return now;}}')
 uri=generated/'Uri.java';uri.write_text('package android.net;public final class Uri{final java.net.URI u;private Uri(String v){u=java.net.URI.create(v);}public static Uri parse(String v){return new Uri(v);}public String getScheme(){return u.getScheme();}public String getHost(){return u.getHost();}public String getUserInfo(){return u.getUserInfo();}public int getPort(){return u.getPort();}}')
 files=[prod/(n+'.java') for n in ['J','DeferredBrowserSettings','TaskGuardSnapshot','EnvironmentResourcePolicy']]+[host,clock,uri];classes=out/'classes';classes.mkdir(exist_ok=True)
 cmd=[str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)];c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'compile.stdout.txt').write_text(c.stdout);(out/'compile.stderr.txt').write_text(c.stderr)
 if c.returncode:print(c.stderr);raise SystemExit(c.returncode)
 run=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-Dfixed='+str(fixed).lower(),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.WakeHost'],capture_output=True,text=True,timeout=45);(out/'run.stdout.json').write_text(run.stdout);(out/'run.stderr.txt').write_text(run.stderr)
 if run.returncode:print(run.stdout);print(run.stderr);raise SystemExit(run.returncode)
 report=json.loads(run.stdout);assert report['status']==('passed' if fixed else 'expected-baseline-gap') and report['count']==len(report['checks']) and all(x['pass'] for x in report['checks']);assert report['replyServiceStarts']==0 and report['backgroundReplyDetection'] is False
 report.update(sourceSha256=hashlib.sha256(chat.encode()).hexdigest(),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),productionMembersSha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in methods.items()},wakeMembersSha256=hashlib.sha256(wake.encode()).hexdigest(),filesSha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [*files,chatpath,template,pathlib.Path(__file__)]},baselineSource=bool(a.before_source));a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':report['count'],'output':str(a.output)}))
if __name__=='__main__':main()
