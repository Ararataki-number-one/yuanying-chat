#!/usr/bin/env python3
"""Host test of production popup admission policy and verbatim external-response callback.
Queue/session/stream boundaries are controlled adapters; no Gecko or Android run.
"""
import argparse, hashlib, json, pathlib, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];PROD=ROOT/'app/src/main/java/local/pocketchat'
sys.path.insert(0,str(ROOT/'tests/review-host'))
from run_deferred_browser_host import production_member
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
method=production_member((PROD/'GeckoWebView.java').read_text(),'public void onExternalResponse(')
host=r'''package local.pocketchat;
import java.util.*;import java.io.*;
class PopupHost {
 static class GeckoSession {}
 static class Stream extends ByteArrayInputStream {boolean closed;Stream(){super(new byte[]{1,2,3});}public void close()throws IOException{closed=true;super.close();}}
 static class WebResponse {Stream body=new Stream();}
 static class Guard {boolean ready=true;boolean allowed(){return ready;}}
 static class Queue {ArrayDeque<Runnable> queue=new ArrayDeque<>();void post(Runnable task){queue.add(task);}void drain(){while(!queue.isEmpty())queue.remove().run();}}
 static class Owner {Guard guard=new Guard();Queue handler=new Queue();}
 interface Receiver {void receive(WebResponse response);}
 boolean destroyed,addonDisabled,protectedRoute=true;Owner owner=new Owner();GeckoSession current=new GeckoSession();
 Set<GeckoSession> popups=new HashSet<>(),crashed=new HashSet<>(),pendingLoads=new HashSet<>();Map<GeckoSession,String> locations=new HashMap<>(),loadingTargets=new HashMap<>();int received;Receiver responseDownload=r->received++;
 PopupHost(){locations.put(current,"https://chatgpt.com/");}
 boolean protectionAllowsNetwork(){return protectedRoute;}
 __CALLBACK__
 static void check(boolean ok,String label){if(!ok)throw new AssertionError(label);}
 public static void main(String[] args){
  check(GeckoNavigationPolicy.blobFrom("blob:https://chatgpt.com/token","https://chatgpt.com/c/a"),"same origin blob opens");
  check(GeckoNavigationPolicy.blobFrom("blob:https://chatgpt.com:443/token","https://chatgpt.com/c/a"),"default port normalization");
  for(String bad:new String[]{"blob:https://evil.example/id","blob:http://chatgpt.com/id","blob:https://chatgpt.com:444/id","blob:null/id","blob:https://user@chatgpt.com/id","javascript:alert(1)","blob:https://127.0.0.1/id"})
   check(!GeckoNavigationPolicy.blobFrom(bad,"https://chatgpt.com/c/a"),"foreign or unsafe blob rejected: "+bad);
  PopupHost h=new PopupHost();WebResponse direct=new WebResponse();h.onExternalResponse(h.current,direct);check(h.received==1&&!direct.body.closed,"current response delivered immediately");
  GeckoSession popup=new GeckoSession();h.popups.add(popup);h.locations.put(popup,"https://chatgpt.com/file");h.pendingLoads.add(popup);
  h.owner.handler.post(()->h.current=popup);WebResponse early=new WebResponse();h.onExternalResponse(popup,early);
  check(h.received==1&&!early.body.closed,"early popup stream retained before activation");h.owner.handler.drain();
  check(h.received==2&&!early.body.closed&&!h.pendingLoads.contains(popup),"queued activation precedes download delivery");
  for(int mode=0;mode<5;mode++){
   PopupHost x=new PopupHost();GeckoSession p=new GeckoSession();x.popups.add(p);x.locations.put(p,"https://chatgpt.com/file");WebResponse r=new WebResponse();x.onExternalResponse(p,r);
   if(mode==0)x.destroyed=true;else if(mode==1)x.owner.guard.ready=false;else if(mode==2)x.protectedRoute=false;else if(mode==3)x.locations.remove(p);
   if(mode!=4)x.current=p; // Mode 4 is an old/background popup; never activate it.
   x.owner.handler.drain();check(x.received==0&&r.body.closed,"stale/blocked popup closes stream: "+mode);
  }
  System.out.println("17 popup policy and callback cases passed");
 }
}'''.replace('__CALLBACK__',method)
with tempfile.TemporaryDirectory() as tmp:
 d=pathlib.Path(tmp);f=d/'PopupHost.java';f.write_text(host)
 subprocess.run([str(a.java_home/'bin/javac'),'-d',str(d),str(f),str(PROD/'GeckoNavigationPolicy.java'),str(PROD/'BrowserAddressPolicy.java')],check=True)
 r=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(d),'local.pocketchat.PopupHost'],check=True,capture_output=True,text=True)
report=dict(status='passed',cases=17,callbackSha256=hashlib.sha256(method.encode()).hexdigest(),actualAndroidExecution=False,scope=__doc__,output=r.stdout.strip())
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
