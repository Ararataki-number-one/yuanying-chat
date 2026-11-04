package local.pocketchat;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.os.*;
import android.util.AtomicFile;
import android.webkit.*;
import android.webkit.CookieManager;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Integration-only real WebView/ProxyController workload. The proxy never forwards traffic. */
public final class BrowserIntegrationActivity extends BrowserActivity {
  static final String ORIGIN="http://browser-fixture.example";
  static final String BODY="Controlled Chromium download\n";
  static final String TARGET_SCROLL_SCRIPT="function(id){const e=document.getElementById(id);if(!e)throw new Error('Missing target '+id);e.scrollIntoView({block:'center',inline:'center'});return {id:e.id};}";
  static final String TARGET_SAMPLE_SCRIPT="function(id){const e=document.getElementById(id);if(!e)throw new Error('Missing target '+id);const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y),v=window.visualViewport;return {id:e.id,x,y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,viewportWidth:innerWidth,viewportHeight:innerHeight,scrollX,scrollY,devicePixelRatio,visualScale:window.visualViewport?visualViewport.scale:1,visualWidth:v&&Number.isFinite(v.width)?v.width:null,visualHeight:v&&Number.isFinite(v.height)?v.height:null,visualOffsetLeft:v&&Number.isFinite(v.offsetLeft)?v.offsetLeft:null,visualOffsetTop:v&&Number.isFinite(v.offsetTop)?v.offsetTop:null,documentFocus:document.hasFocus(),hitTarget:h===e||e.contains(h),hitId:h&&h.id||'',hitTag:h&&h.tagName||'',url:location.href};}";
  static final String PICKER_ARM_SCRIPT="function(b){const input=document.getElementById('upload');if(!input||!input.isConnected||location.href!==b.url||!/^([0-9a-f]{32})$/.test(b.nonce)||!/^([0-9a-f]{40})$/.test(b.source)||!/^([0-9a-f]{32})$/.test(b.token)||!Number.isInteger(b.ordinal)||b.ordinal<1||b.ordinal>2)throw new Error('Invalid picker document');let s=window.__fixturePickerBarrier;if(!s){if(b.ordinal!==1)throw new Error('Picker sequence did not start at one');s={nonce:b.nonce,source:b.source,url:b.url,input,completed:0,lastToken:'',active:null,rejected:0,events:[]};window.__fixturePickerBarrier=s;for(const type of ['pointerdown','pointerup','click'])document.addEventListener(type,e=>{if(e.target!==input)return;s.events.push({type:e.type,trusted:e.isTrusted,ordinal:s.active?s.active.ordinal:0,x:e.clientX,y:e.clientY,focused:document.hasFocus()});if(s.events.length>12)s.events.shift();},true);}if(s.nonce!==b.nonce||s.source!==b.source||s.url!==b.url||s.input!==input||s.active||s.completed!==b.ordinal-1||s.lastToken===b.token)throw new Error('Picker request is stale');const r={token:b.token,ordinal:b.ordinal,seen:false,afterTask:false,afterFrame:false};s.active=r;const current=()=>window.__fixturePickerBarrier===s&&s.active===r&&s.input===input&&input.isConnected&&document.getElementById('upload')===input&&location.href===s.url&&s.nonce===b.nonce&&s.source===b.source;const cancelled=e=>{s.events.push({type:e.type,trusted:e.isTrusted,ordinal:r.ordinal,focused:document.hasFocus()});if(s.events.length>12)s.events.shift();if(!current()||e.target!==input||e.isTrusted!==true||r.seen){s.rejected++;return;}r.seen=true;input.removeEventListener('cancel',cancelled);setTimeout(()=>{if(!current())return;r.afterTask=true;requestAnimationFrame(()=>{if(!current())return;r.afterFrame=true;s.completed=r.ordinal;s.lastToken=r.token;s.active=null;});},0);};input.addEventListener('cancel',cancelled);return {armed:true,ordinal:r.ordinal,token:r.token};}";
  static final String PICKER_OBSERVE_SCRIPT="function(b){const s=window.__fixturePickerBarrier,input=document.getElementById('upload');const matching=!!s&&s.nonce===b.nonce&&s.source===b.source&&s.url===b.url&&location.href===b.url&&s.input===input&&!!input&&input.isConnected;const current=matching&&s.active&&s.active.token===b.token&&s.active.ordinal===b.ordinal;const complete=matching&&s.completed===b.ordinal&&s.lastToken===b.token&&s.active===null;return {matching,ordinal:b.ordinal,completed:matching?s.completed:0,ready:!!complete,afterTask:complete||!!(current&&s.active.afterTask),afterFrame:!!complete,rejected:matching?s.rejected:0,events:matching?s.events:[]};}";
  static final String[] NATIVE_TARGET_FIELDS={"screenX","screenY","width","height","visibleLeft","visibleTop","visibleRight","visibleBottom"};
  static final String[] DOM_TARGET_FIELDS={"x","y","left","top","right","bottom","viewportWidth","viewportHeight","scrollX","scrollY","devicePixelRatio","visualScale"};
  final Handler probe=new Handler(Looper.getMainLooper());
  final JSONArray checks=new JSONArray();
  final JSONArray layoutObservations=new JSONArray();
  final JSONArray leaseObservations=new JSONArray();
  final JSONArray nativeInputEvents=new JSONArray();
  final JSONArray pickerBarrierHistory=new JSONArray();
  JSONObject pickerBarrierObservation=new JSONObject();
  FixtureProxy fixture;JSONObject build;String nonce,stage="starting",failure="";long deadline;
  WebView first,returnSurface;Object oldRoute;int picker;boolean pickerOpened,finished,switchedAway;
  int baselineDownloads;JSONObject target=new JSONObject();
  long targetGeneration,visualSequence;Runnable targetTimeout;

  @Override protected void onCreate(Bundle saved){
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    nonce=getIntent().getStringExtra("runNonce");
    if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new SecurityException("Fresh synthetic run required");
    try{
      build=IntegrationBuildIdentity.read(this);
      if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Installed source differs");
      fixture=new FixtureProxy();fixture.start();ProfileCatalog.get(this).created(Profiles.slot(this));
      getSharedPreferences("chat",0).edit().clear().putString("networkMode","external").putString("proxy","http://127.0.0.1:"+fixture.port()).putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false).commit();
      getSharedPreferences("universal-browser",0).edit().clear().commit();
      getIntent().putExtra("url",ORIGIN+"/start");
    }catch(Exception error){throw new IllegalStateException("Synthetic browser setup failed",error);}
    super.onCreate(null);deadline=SystemClock.elapsedRealtime()+90000;
    await("start",()->runtime!=null&&runtime.allowed()&&page("/start"),this::started);
  }
  interface Ready{boolean get()throws Exception;}
  interface Step{void run()throws Exception;}
  void check(String name,boolean pass)throws Exception{checks.put(new JSONObject().put("name",name).put("pass",pass));if(!pass)throw new AssertionError(name);}
  boolean page(String path){return web()!=null&&(ORIGIN+path).equals(web().getUrl())&&("Fixture "+path).equals(web().getTitle())&&!selected.loading;}
  void await(String name,Ready ready,Step next){
    probe.post(new Runnable(){public void run(){if(finished||destroyed)return;try{if(ready.get()){next.run();return;}if(SystemClock.elapsedRealtime()>deadline)throw new AssertionError("Timed out: "+name+" / "+(runtime==null?"no runtime":runtime.status()));probe.postDelayed(this,75);}catch(Throwable error){fail(error);}}});
  }
  void step(String value)throws Exception{stage=value;deadline=SystemClock.elapsedRealtime()+45000;publish(false);}
  void js(String code,java.util.function.Consumer<JSONObject> complete){
    WebView value=web();if(value==null){fail(new AssertionError("Missing real WebView"));return;}
    Runnable timeout=()->fail(new AssertionError("JavaScript callback timed out during "+stage));probe.postDelayed(timeout,45000);
    try{value.evaluateJavascript("JSON.stringify(("+code+"))",raw->{probe.removeCallbacks(timeout);try{if(finished)return;Object decoded=new JSONTokener(raw).nextValue();complete.accept(new JSONObject(String.valueOf(decoded)));}catch(Throwable error){fail(error);}});}catch(RuntimeException error){probe.removeCallbacks(timeout);fail(error);}
  }
  void started()throws Exception{
    check("Browser controls are created at Android font scale two",getResources().getConfiguration().fontScale>=1.9f);
    check("Default browser homepage is ChatGPT",BrowserPreferences.DEFAULT_URL.equals(BrowserPreferences.home(this)));
    check("Enhanced Gecko entry remains the initial entry preference",!BrowserPreferences.startBrowser(this));
    check("The fixture uses the production ChromiumRuntime",runtime.getClass()==ChromiumRuntime.class);
    java.net.Proxy actualProxy=runtime.verifiedProxy();
    check("The proxy override has acknowledged the actual route",runtime.allowed()&&actualProxy!=null&&actualProxy.type()==java.net.Proxy.Type.HTTP&&actualProxy.address() instanceof InetSocketAddress&&((InetSocketAddress)actualProxy.address()).getPort()==fixture.port());
    PackageInfo provider=WebView.getCurrentWebViewPackage();check("Android reports an installed WebView provider",provider!=null&&provider.versionName!=null&&!provider.versionName.isEmpty());
    check("The actual Android WebView rendered the proxy response",fixture.successes.get()>0&&web().getProgress()==100);
    ChromiumRouteLease.Snapshot liveLease=observeLease("first-surface");
    check("A live browser surface retains the actual native route",ChromiumRouteLease.held()&&liveLease.surfaces==1&&NativeNetwork.get(this).routeBusy());
    check("Production surface disables file and content access",!web().getSettings().getAllowFileAccess()&&!web().getSettings().getAllowContentAccess());
    check("Production surface blocks mixed content",web().getSettings().getMixedContentMode()==WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    check("The address bar follows the actual page URL",address.getText().toString().equals(ORIGIN+"/start"));
    js("({url:location.href,cookie:document.cookie,draft:document.getElementById('draft').value,chatBridge:typeof window.__pocketWebReplyObserver,cacheBridge:typeof window.__pocketWebPerformance})",value->{try{
      check("Synthetic login cookie is stored by the real WebView",value.getString("cookie").contains("browser_fixture=preserved"));
      check("The original website draft is present",value.getString("draft").equals("untouched website draft"));
      check("The general browser does not install the ChatGPT reply or transcript bridge",value.getString("chatBridge").equals("undefined")&&value.getString("cacheBridge").equals("undefined"));
      step("history-second");go(ORIGIN+"/second");await("second",()->page("/second"),this::historyBack);
    }catch(Throwable error){fail(error);}});
  }
  void historyBack()throws Exception{
    check("Production browser records completed history",library.list("history").length()>=2);
    check("The real WebView exposes back history",web().canGoBack());step("history-back");history(-1);await("back",()->page("/start"),()->{
      check("Production back navigates the actual WebView",web().canGoForward());step("history-forward");history(1);await("forward",()->page("/second"),this::tabs);
    });
  }
  void tabs()throws Exception{
    first=web();js("({draft:(document.getElementById('draft').value='first tab exact draft'),marker:(window.__fixtureProbe='kept')})",value->{try{
      step("second-tab");newTab(ORIGIN+"/tab");await("tab",()->page("/tab"),()->{
        check("A second tab uses another real WebView",tabs.size()==2&&web()!=first);
        check("Both live tab surfaces own separate route leases",observeLease("two-surfaces").surfaces==2);
        check("The same browser environment retains its cookie across tabs",CookieManager.getInstance().getCookie(ORIGIN).contains("browser_fixture=preserved"));
        select(tabs.get(0));check("Selecting the first tab reuses its existing surface",web()==first);
        js("({draft:document.getElementById('draft').value,marker:window.__fixtureProbe})",state->{try{
          check("Switching tabs preserves the exact live draft and document",state.getString("draft").equals("first tab exact draft")&&state.getString("marker").equals("kept"));
          String before=selected.url;go("javascript:document.body.remove()");check("Address entry rejects executable URLs without navigating",before.equals(selected.url));
          go("http://127.0.0.1/private");check("Address entry rejects private targets without navigating",before.equals(selected.url));
          library.remember("bookmarks",selected.url,"Fixture bookmark",100);check("Bookmark persistence uses the actual browser library",library.bookmarked(selected.url));
          library.clearHistory();check("Clearing history preserves the current URL and cookie",selected.url.equals(before)&&CookieManager.getInstance().getCookie(ORIGIN).contains("browser_fixture=preserved"));
          picker=1;preparePicker();
        }catch(Throwable error){fail(error);}});
      });
    }catch(Throwable error){fail(error);}});
  }
  void target(String id,Step next){
    try{
      if(!id.equals("upload")&&!id.equals("download"))throw new AssertionError("Unknown trusted target");
      WebView view=web();long generation=++targetGeneration;step("target-"+id+"-"+picker);
      target=new JSONObject().put("id",id).put("ready",false);publish(false);
      targetTimeout=()->fail(new AssertionError("Trusted target did not stabilize: "+id));probe.postDelayed(targetTimeout,45000);
      scrollTarget(view,id,generation,()->targetFrame(view,id,generation,next,null,null));
    }catch(Throwable error){fail(error);}
  }
  boolean targetCurrent(WebView view,long generation){return !finished&&!destroyed&&targetGeneration==generation&&view!=null&&view==web()&&foreground&&runtime.allowed();}
  void scrollTarget(WebView view,String id,long generation,Step next){
    if(!targetCurrent(view,generation)){fail(new AssertionError("Trusted target document is no longer current"));return;}
    js("("+TARGET_SCROLL_SCRIPT+")("+JSONObject.quote(id)+")",value->{try{if(!targetCurrent(view,generation))throw new AssertionError("Target changed during scroll");next.run();}catch(Throwable error){fail(error);}});
  }
  JSONObject nativeTargetFrame(WebView view)throws JSONException{
    int[] location=new int[2],rootLocation=new int[2];view.getLocationOnScreen(location);view.getRootView().getLocationOnScreen(rootLocation);android.graphics.Rect visible=new android.graphics.Rect();boolean shown=view.isShown()&&view.getGlobalVisibleRect(visible);visible.offset(rootLocation[0],rootLocation[1]);
    return new JSONObject().put("screenX",location[0]).put("screenY",location[1]).put("width",view.getWidth()).put("height",view.getHeight()).put("visibleLeft",visible.left).put("visibleTop",visible.top).put("visibleRight",visible.right).put("visibleBottom",visible.bottom).put("nativeScale",(double)view.getScale()).put("viewFocus",view.hasFocus()).put("shown",shown).put("windowFocus",view.hasWindowFocus()).put("foreground",foreground).put("layoutRequested",root.isLayoutRequested()||content.isLayoutRequested()||view.isLayoutRequested());
  }
  static boolean nativeTargetReady(JSONObject frame)throws JSONException{return frame.getBoolean("shown")&&frame.getBoolean("windowFocus")&&frame.getBoolean("foreground")&&!frame.getBoolean("layoutRequested")&&frame.getInt("width")>0&&frame.getInt("height")>0&&frame.getInt("visibleRight")>frame.getInt("visibleLeft")&&frame.getInt("visibleBottom")>frame.getInt("visibleTop");}
  static boolean sameNativeTarget(JSONObject first,JSONObject second)throws JSONException{if(first==null||second==null)return false;for(String key:NATIVE_TARGET_FIELDS)if(first.getInt(key)!=second.getInt(key))return false;return nativeTargetReady(first)&&nativeTargetReady(second);}
  static boolean sameDomTarget(JSONObject first,JSONObject second)throws JSONException{if(first==null||second==null)return false;for(String key:DOM_TARGET_FIELDS)if(Double.compare(first.getDouble(key),second.getDouble(key))!=0)return false;return first.getString("id").equals(second.getString("id"))&&first.getString("url").equals(second.getString("url"))&&first.getBoolean("hitTarget")&&second.getBoolean("hitTarget");}
  boolean domTargetReady(String id,JSONObject value,WebView view)throws JSONException{
    for(String key:DOM_TARGET_FIELDS)if(!Double.isFinite(value.getDouble(key)))return false;
    double x=value.getDouble("x"),y=value.getDouble("y");return id.equals(value.getString("id"))&&view.getUrl().equals(value.getString("url"))&&value.getBoolean("hitTarget")&&value.getDouble("right")>value.getDouble("left")&&value.getDouble("bottom")>value.getDouble("top")&&x>0&&x<value.getDouble("viewportWidth")&&y>0&&y<value.getDouble("viewportHeight");
  }
  void targetFrame(WebView view,String id,long generation,Step next,JSONObject previousNative,JSONObject previousDom){
    if(!targetCurrent(view,generation))return;
    view.postOnAnimation(()->{try{
      if(!targetCurrent(view,generation))return;JSONObject before=nativeTargetFrame(view);target=new JSONObject().put("id",id).put("ready",false).put("nativeFrame",before);
      if(!nativeTargetReady(before)){targetFrame(view,id,generation,next,null,null);return;}
      view.postVisualStateCallback(++visualSequence,new WebView.VisualStateCallback(){@Override public void onComplete(long request){
        view.postOnAnimation(()->{try{
          if(!targetCurrent(view,generation))return;JSONObject nativeBefore=nativeTargetFrame(view);
          if(!sameNativeTarget(before,nativeBefore)){targetFrame(view,id,generation,next,null,null);return;}
          js("("+TARGET_SAMPLE_SCRIPT+")("+JSONObject.quote(id)+")",dom->{try{
            if(!targetCurrent(view,generation))return;JSONObject nativeAfter=nativeTargetFrame(view);target=new JSONObject().put("id",id).put("ready",false).put("nativeFrame",nativeAfter).put("dom",dom);
            if(!sameNativeTarget(nativeBefore,nativeAfter)){targetFrame(view,id,generation,next,null,null);return;}
            if(!domTargetReady(id,dom,view)){scrollTarget(view,id,generation,()->targetFrame(view,id,generation,next,null,null));return;}
            if(!sameNativeTarget(previousNative,nativeAfter)||!sameDomTarget(previousDom,dom)){targetFrame(view,id,generation,next,nativeAfter,dom);return;}
            double scale=nativeAfter.getInt("width")/dom.getDouble("viewportWidth");int x=nativeAfter.getInt("screenX")+(int)Math.round(dom.getDouble("x")*scale),y=nativeAfter.getInt("screenY")+(int)Math.round(dom.getDouble("y")*scale);
            if(x<nativeAfter.getInt("visibleLeft")||x>=nativeAfter.getInt("visibleRight")||y<nativeAfter.getInt("visibleTop")||y>=nativeAfter.getInt("visibleBottom"))throw new AssertionError("Trusted target is outside the visible native WebView");
            target=new JSONObject().put("id",id).put("x",x).put("y",y).put("ready",true).put("stableSamples",2).put("visualStateComplete",true).put("nativeFrame",nativeAfter).put("dom",dom);probe.removeCallbacks(targetTimeout);targetTimeout=null;next.run();
          }catch(Throwable error){fail(error);}});
        }catch(Throwable error){fail(error);}});
      }});
    }catch(Throwable error){fail(error);}});
  }
  void preparePicker(){
    try{
      WebView owner=web();int ordinal=picker;
      JSONObject binding=new JSONObject().put("nonce",nonce).put("source",build.getString("sourceCommit")).put("url",owner.getUrl()).put("ordinal",ordinal).put("token",UUID.randomUUID().toString().replace("-",""));
      js("("+PICKER_ARM_SCRIPT+")("+binding.toString()+")",armed->{try{
        if(web()!=owner||!armed.getBoolean("armed")||armed.getInt("ordinal")!=ordinal||!armed.getString("token").equals(binding.getString("token")))throw new AssertionError("Renderer picker request was not armed");
        prepareArmedPicker(owner,ordinal,binding);
      }catch(Throwable error){fail(error);}});
    }catch(Throwable error){fail(error);}
  }
  void prepareArmedPicker(WebView owner,int ordinal,JSONObject binding){target("upload",()->{
    pickerOpened=false;step("file-picker-"+picker);observePickerInput(owner,ordinal,binding);
    await("actual chooser open and cancellation",()->{if(files.pending!=null)pickerOpened=true;return pickerOpened&&files.pending==null&&foreground;},()->{
      check("Native file chooser "+picker+" returns its callback after user cancellation",pickerOpened&&files.pending==null);
      awaitRendererCancellation(owner,ordinal,binding,()->{
      js("({files:document.getElementById('upload').files.length,draft:document.getElementById('draft').value})",value->{try{
        check("Cancelled chooser "+picker+" preserves the website draft and selects no files",value.getInt("files")==0&&value.getString("draft").equals("first tab exact draft"));
        if(picker++==1)preparePicker();else prepareDownload();
      }catch(Throwable error){fail(error);}});
      });
    });
  });}
  void observePickerInput(WebView owner,int ordinal,JSONObject binding){
    if(finished||destroyed||web()!=owner||!stage.equals("file-picker-"+ordinal))return;
    if(!foreground||files.pending!=null){probe.postDelayed(()->observePickerInput(owner,ordinal,binding),250);return;}
    try{owner.evaluateJavascript("JSON.stringify(("+PICKER_OBSERVE_SCRIPT+")("+binding.toString()+"))",raw->{
      if(finished||destroyed||web()!=owner||!stage.equals("file-picker-"+ordinal))return;
      try{JSONObject value=new JSONObject(String.valueOf(new JSONTokener(raw).nextValue()));if(value.optBoolean("matching")&&!value.toString().equals(pickerBarrierObservation.toString())){pickerBarrierObservation=value;publish(false);}}catch(Exception ignored){}
      probe.postDelayed(()->observePickerInput(owner,ordinal,binding),250);
    });}catch(RuntimeException ignored){}
  }
  void awaitRendererCancellation(WebView owner,int ordinal,JSONObject binding,Step next){
    Runnable timeout=()->fail(new AssertionError("Renderer trusted picker cancellation did not complete: "+ordinal));
    probe.postDelayed(timeout,Math.max(0,deadline-SystemClock.elapsedRealtime()));
    pollRendererCancellation(owner,ordinal,binding,next,timeout);
  }
  void pollRendererCancellation(WebView owner,int ordinal,JSONObject binding,Step next,Runnable timeout){
    if(finished||destroyed)return;
    try{
      if(web()!=owner||picker!=ordinal||!owner.getUrl().equals(binding.getString("url"))||!foreground||files.pending!=null)throw new AssertionError("Renderer cancellation belongs to an old picker document");
      if(SystemClock.elapsedRealtime()>=deadline)throw new AssertionError("Renderer trusted picker cancellation exceeded its original step deadline");
      js("("+PICKER_OBSERVE_SCRIPT+")("+binding.toString()+")",value->{try{
        if(web()!=owner||picker!=ordinal||!value.getBoolean("matching"))throw new AssertionError("Renderer cancellation request differs");
        if(!value.toString().equals(pickerBarrierObservation.toString())){pickerBarrierObservation=value;publish(false);}
        if(value.getBoolean("ready")){
          if(value.getInt("completed")!=ordinal||!value.getBoolean("afterTask")||!value.getBoolean("afterFrame"))throw new AssertionError("Renderer cancellation has no completed event task and frame");
          probe.removeCallbacks(timeout);pickerBarrierHistory.put(value);
          probe.post(()->{try{if(finished||destroyed)return;if(web()!=owner||picker!=ordinal||!foreground||files.pending!=null)throw new AssertionError("Renderer cancellation changed before continuation");next.run();}catch(Throwable error){fail(error);}});
        }else probe.postDelayed(()->pollRendererCancellation(owner,ordinal,binding,next,timeout),125);
      }catch(Throwable error){fail(error);}});
    }catch(Throwable error){fail(error);}
  }
  void prepareDownload()throws Exception{
    baselineDownloads=files.store.rows().length();target("download",()->{step("download-click");
      await("in-flight native download route ownership",()->files.transfer!=null&&ChromiumRouteLease.snapshot().downloads>0,()->{
        check("In-flight native download owns its route lease",observeLease("download-in-flight").downloads==1&&ChromiumRouteLease.held()&&NativeNetwork.get(this).routeBusy());
        fixture.downloadRelease.countDown();step("download-publication");
        await("native download publication",()->files.transfer==null&&files.store.rows().length()>baselineDownloads&&ChromiumRouteLease.snapshot().downloads==0,this::downloaded);
      });
    });
  }
  void downloaded()throws Exception{
    JSONArray rows=files.store.rows();JSONObject saved=rows.getJSONObject(0);
    check("The actual native download publishes one complete file",rows.length()==baselineDownloads+1&&saved.optLong("savedBytes",saved.optLong("bytes",-1))==BODY.getBytes(StandardCharsets.UTF_8).length);
    JSONArray global=DownloadLibrary.get(this).list();boolean indexed=false;for(int i=0;i<global.length();i++){JSONObject row=global.optJSONObject(i);if(row!=null&&saved.optString("uri").equals(row.optString("uri"))&&row.optInt("slot",-1)==Profiles.slot(this))indexed=true;}
    check("The browser file is discoverable in the global download index",indexed);
    try(InputStream stream=getContentResolver().openInputStream(android.net.Uri.parse(saved.getString("uri")))){check("The published Android content URI contains the exact fixture bytes",BODY.equals(J.text(stream,1024)));}
    check("Native downloads use the same controlled proxy",fixture.downloads.get()>0);
    check("Completed native downloads release their own route lease",observeLease("download-complete").downloads==0&&ChromiumRouteLease.snapshot().surfaces==2);
    oldRoute=runtime.routeStamp();step("route-block");getSharedPreferences("chat",0).edit().putBoolean("networkConfigured",false).commit();
    await("unconfigured route closes surfaces",()->!runtime.allowed()&&tabs.stream().allMatch(tab->tab.web==null)&&!ChromiumRouteLease.held(),()->{
      check("A route configuration change retires every live surface",tabs.stream().allMatch(tab->tab.web==null));
      ChromiumRouteLease.Snapshot retired=observeLease("route-blocked");check("Retired surfaces and completed downloads release every route hold",!ChromiumRouteLease.held()&&retired.surfaces==0&&retired.downloads==0);
      check("The old route token is rejected",!runtime.current(oldRoute));
      int observed=fixture.blockedRequests.get();go(ORIGIN+"/blocked");
      probe.postDelayed(()->{try{
        check("Blocked navigation opens no surface or proxy request",web()==null&&fixture.blockedRequests.get()==observed);
        step("route-restore");getSharedPreferences("chat",0).edit().putBoolean("networkConfigured",true).commit();
        await("restored actual route",()->runtime.allowed()&&page("/blocked"),()->{
          check("Explicit route restoration creates a fresh live document",web()!=first&&runtime.current(runtime.routeStamp())&&!runtime.current(oldRoute));
          check("Restored live surface reacquires native route protection",observeLease("route-restored").surfaces==1&&ChromiumRouteLease.held()&&NativeNetwork.get(this).routeBusy());
          check("The controlled proxy has never forwarded an external request",fixture.upstreamConnections==0);
          returnSurface=web();js("({draft:(document.getElementById('draft').value='engine roundtrip exact draft'),marker:(window.__fixtureRoundtrip='same document')})",value->{try{
            orientations(this::switchEngines);
          }catch(Throwable error){fail(error);}});
        });
      }catch(Throwable error){fail(error);}},500);
    });
  }
  ChromiumRouteLease.Snapshot observeLease(String name)throws JSONException{
    ChromiumRouteLease.Snapshot value=ChromiumRouteLease.snapshot();leaseObservations.put(new JSONObject().put("stage",name).put("surfaces",value.surfaces).put("downloads",value.downloads).put("changes",value.changes).put("held",ChromiumRouteLease.held()).put("nativeRouteBusy",NativeNetwork.get(this).routeBusy()));return value;
  }
  boolean controlsVisible()throws JSONException{
    JSONArray controls=new JSONArray();boolean available=true;String[] names={"address","back","forward","tabs","reload"};int at=0;
    for(android.view.View view:new android.view.View[]{address,back,forward,tabCount,reload}){android.graphics.Rect rect=new android.graphics.Rect();boolean shown=view.isShown()&&view.getGlobalVisibleRect(rect);controls.put(new JSONObject().put("name",names[at++]).put("shown",shown).put("visibleWidth",rect.width()).put("visibleHeight",rect.height()).put("minimum",dp(40)));if(!shown||rect.width()<dp(40)||rect.height()<dp(40))available=false;}
    layoutObservations.put(new JSONObject().put("orientation",getResources().getConfiguration().orientation).put("fontScale",getResources().getConfiguration().fontScale).put("rootWidth",root.getWidth()).put("rootHeight",root.getHeight()).put("controls",controls));return available;
  }
  void orientations(Step after)throws Exception{
    step("rotate-landscape");await("landscape at large font",()->getResources().getConfiguration().orientation==android.content.res.Configuration.ORIENTATION_LANDSCAPE&&root.getWidth()>root.getHeight(),()->{
      check("Large-font landscape keeps address and navigation targets visible",controlsVisible());check("Landscape retains the same actual browser surface",web()==returnSurface);
      step("rotate-portrait");await("portrait at large font",()->getResources().getConfiguration().orientation==android.content.res.Configuration.ORIENTATION_PORTRAIT&&root.getHeight()>root.getWidth(),()->{
        check("Large-font portrait keeps address and navigation targets visible",controlsVisible());check("Portrait retains the same actual browser surface",web()==returnSurface);
        js("({draft:document.getElementById('draft').value,marker:window.__fixtureRoundtrip})",value->{try{check("Large-font orientation changes preserve the live website draft and document",value.getString("draft").equals("engine roundtrip exact draft")&&value.getString("marker").equals("same document"));after.run();}catch(Throwable error){fail(error);}});
      });
    });
  }
  void switchEngines()throws Exception{
    step("switch-to-gecko");openChat();await("enhanced activity and browser task roundtrip",()->switchedAway&&foreground,()->{
      check("Returning from the actual enhanced activity retains the browser surface",web()==returnSurface&&runtime.allowed());
      check("Engine task roundtrip retains the live Chromium route lease",observeLease("engine-roundtrip").surfaces==1&&ChromiumRouteLease.held()&&NativeNetwork.get(this).routeBusy());
      js("({draft:document.getElementById('draft').value,marker:window.__fixtureRoundtrip})",returned->{try{
        check("Engine UI roundtrip preserves the exact live browser document and draft",returned.getString("draft").equals("engine roundtrip exact draft")&&returned.getString("marker").equals("same document"));finished=true;stage="complete";publish(true);
      }catch(Throwable error){fail(error);}});
    });
  }
  void fail(Throwable error){if(finished)return;if(targetTimeout!=null)probe.removeCallbacks(targetTimeout);failure=error.getClass().getSimpleName()+": "+String.valueOf(error.getMessage());stage="failed";finished=true;try{publish(true);}catch(Exception ignored){} }
  void publish(boolean terminal)throws Exception{
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).optBoolean("pass"))passed++;
    PackageInfo provider=WebView.getCurrentWebViewPackage();JSONObject value=new JSONObject().put("schema",1).put("status",terminal?(failure.isEmpty()?"passed":"failed"):"running").put("stage",stage).put("runNonce",nonce).put("taskId",getTaskId()).put("buildIdentity",build).put("sourceCommit",build.getString("sourceCommit")).put("checks",checks).put("layoutObservations",layoutObservations).put("leaseObservations",leaseObservations).put("passed",passed).put("total",checks.length()).put("failure",failure).put("tapTarget",target).put("provider",provider==null?JSONObject.NULL:new JSONObject().put("package",provider.packageName).put("version",provider.versionName)).put("proxy",fixture.snapshot()).put("actualAndroidExecution",true).put("actualAndroidWebViewExecution",web()!=null||first!=null).put("actualGeckoExecution",false).put("actualPublicWebsiteExecution",false).put("actualDevicePerformanceMeasurement",false).put("scope","Real production BrowserActivity, ChromiumRuntime, ProxyController, Android WebView and native download store with a loopback synthetic HTTP proxy; no upstream forwarding. Chooser and download actions require trusted shell taps. Not phone, public ChatGPT, camera/microphone or frame-rate acceptance.");
    value.put("foreground",foreground).put("pendingChooser",files!=null&&files.pending!=null).put("routeAllowed",runtime!=null&&runtime.allowed());
    value.put("nativeInputEvents",nativeInputEvents).put("pickerBarrier",pickerBarrierObservation).put("pickerBarrierHistory",pickerBarrierHistory);
    AtomicFile file=new AtomicFile(new File(getFilesDir(),"browser-integration-results.json"));FileOutputStream stream=null;try{stream=file.startWrite();stream.write((value.toString()+"\n").getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);}catch(Exception error){if(stream!=null)file.failWrite(stream);throw error;}
  }
  @Override protected void onPause(){
    if(stage.startsWith("file-picker-")&&files!=null&&files.pending!=null)pickerOpened=true;
    super.onPause();if("switch-to-gecko".equals(stage)){switchedAway=true;try{publish(false);}catch(Exception error){fail(error);}}
  }
  @Override public boolean dispatchTouchEvent(android.view.MotionEvent event){
    boolean handled=super.dispatchTouchEvent(event);
    int action=event.getActionMasked();
    if(!finished&&build!=null&&fixture!=null&&(stage.startsWith("file-picker-")||stage.equals("download-click"))&&(action==android.view.MotionEvent.ACTION_DOWN||action==android.view.MotionEvent.ACTION_UP))try{
      while(nativeInputEvents.length()>=12)nativeInputEvents.remove(0);
      nativeInputEvents.put(new JSONObject().put("stage",stage).put("action",action).put("x",(double)event.getRawX()).put("y",(double)event.getRawY()).put("handled",handled).put("eventTime",event.getEventTime()));publish(false);
    }catch(Exception error){fail(error);}
    return handled;
  }
  @Override protected void onDestroy(){probe.removeCallbacksAndMessages(null);if(fixture!=null)fixture.close();super.onDestroy();}

  static final class FixtureProxy implements AutoCloseable {
    final ServerSocket server;final ExecutorService clients=Executors.newFixedThreadPool(4);final CountDownLatch downloadRelease=new CountDownLatch(1);volatile boolean closed;final AtomicInteger successes=new AtomicInteger(),downloads=new AtomicInteger(),rejected=new AtomicInteger(),blockedRequests=new AtomicInteger();final int upstreamConnections=0;
    FixtureProxy()throws IOException{server=new ServerSocket(0,16,InetAddress.getByName("127.0.0.1"));}
    int port(){return server.getLocalPort();}
    void start(){Thread thread=new Thread(()->{while(!closed)try{Socket socket=server.accept();clients.execute(()->serve(socket));}catch(IOException|RejectedExecutionException done){if(!closed)rejected.incrementAndGet();}},"browser-fixture-proxy");thread.setDaemon(true);thread.start();}
    void serve(Socket socket){try(Socket value=socket){value.setSoTimeout(10000);BufferedReader reader=new BufferedReader(new InputStreamReader(value.getInputStream(),StandardCharsets.ISO_8859_1));String first=reader.readLine();if(first==null)return;String line;int bytes=first.length();while((line=reader.readLine())!=null&&!line.isEmpty()){bytes+=line.length();if(bytes>16384)throw new IOException("Request too large");}
      String[] parts=first.split(" ",3);URI uri=parts.length==3?new URI(parts[1]):null;
      if(parts.length!=3||!parts[0].equals("GET")||uri==null||!"http".equals(uri.getScheme())||!"browser-fixture.example".equals(uri.getHost())||(uri.getPort()!=-1&&uri.getPort()!=80)){rejected.incrementAndGet();respond(value,502,"text/plain","Rejected synthetic target".getBytes(StandardCharsets.UTF_8),false);return;}
      String path=uri.getPath();successes.incrementAndGet();if(path.equals("/blocked"))blockedRequests.incrementAndGet();if(path.equals("/file.txt")){downloads.incrementAndGet();respond(value,200,"text/plain",BODY.getBytes(StandardCharsets.UTF_8),true);}
      else{String html="<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fixture "+path+"</title></head><body><h1>Controlled Chromium "+path+"</h1><textarea id='draft' style='display:block;width:90%;height:80px'>untouched website draft</textarea><input id='upload' type='file' multiple style='display:block;margin:30px 0;height:50px'><a id='download' href='/file.txt' download='fixture.txt' style='display:block;padding:25px'>Download controlled fixture</a></body></html>";respond(value,200,"text/html; charset=UTF-8",html.getBytes(StandardCharsets.UTF_8),false);}
    }catch(Exception ignored){rejected.incrementAndGet();}}
    void respond(Socket socket,int code,String type,byte[] body,boolean attachment)throws IOException{OutputStream stream=socket.getOutputStream();String headers="HTTP/1.1 "+code+" "+(code==200?"OK":"Bad Gateway")+"\r\nContent-Type: "+type+"\r\nContent-Length: "+body.length+"\r\nConnection: close\r\nCache-Control: no-store\r\nSet-Cookie: browser_fixture=preserved; Path=/; SameSite=Lax\r\n"+(attachment?"Content-Disposition: attachment; filename=fixture.txt\r\n":"")+"\r\n";stream.write(headers.getBytes(StandardCharsets.ISO_8859_1));if(attachment&&body.length>0){stream.write(body,0,1);stream.flush();try{if(!downloadRelease.await(45,TimeUnit.SECONDS))throw new IOException("Controlled download gate timed out");}catch(InterruptedException stopped){Thread.currentThread().interrupt();throw new IOException("Controlled download interrupted",stopped);}stream.write(body,1,body.length-1);}else stream.write(body);stream.flush();}
    JSONObject snapshot()throws JSONException{return new JSONObject().put("successfulFixtureRequests",successes.get()).put("downloadRequests",downloads.get()).put("blockedPathRequests",blockedRequests.get()).put("rejectedRequests",rejected.get()).put("upstreamConnections",upstreamConnections).put("forwardingImplemented",false);}
    public void close(){closed=true;downloadRelease.countDown();try{server.close();}catch(IOException ignored){}clients.shutdownNow();}
  }
}
