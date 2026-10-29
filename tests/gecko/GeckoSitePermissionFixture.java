package local.pocketchat;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Additive SDK-only evidence on the already loaded, controlled pool document.
 * It does not impersonate the production MainActivity permission adapter or UI.
 */
final class GeckoSitePermissionFixture {
  final GeckoConnectionPoolIntegrationActivity test;
  final String nonce=UUID.randomUUID().toString().replace("-","");
  final JSONArray checks=new JSONArray(),callbacks=new JSONArray(),snapshots=new JSONArray(),requests=new JSONArray(),mutations=new JSONArray();
  final ArrayList<GeckoSession.PermissionDelegate.ContentPermission> nativeCallbacks=new ArrayList<>();
  final JSONObject evidence=J.obj("schema",1,"status","not-started","scope","controlled-gecko-sdk-only",
      "productionUiAdapter",false,"actualAndroidExecution",true,"actualGeckoExecution",true,"physicalPhoneAcceptance",false,
      "publicNetworkTraffic",false,"testOnlyCertificateException",true,"origin",GeckoConnectionPoolIntegrationActivity.ORIGIN,
      "checks",checks,"callbacks",callbacks,"snapshots",snapshots,"requests",requests,"mutations",mutations);
  volatile boolean active;
  GeckoSession bound;String context;boolean privateMode;
  GeckoSitePermissionFixture(GeckoConnectionPoolIntegrationActivity test){this.test=test;}

  GeckoSession.PermissionDelegate observe(GeckoSession session,GeckoSession.PermissionDelegate original) {
    return new GeckoSession.PermissionDelegate(){
      @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] names,Callback callback){original.onAndroidPermissionsRequest(s,names,callback);}
      @Override public void onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){original.onMediaPermissionRequest(s,origin,video,audio,callback);}
      @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){
        if(active&&s==bound&&s==test.view.current&&permission.permission==PERMISSION_DESKTOP_NOTIFICATION) {
          if(nativeCallbacks.size()>=8)throw new IllegalStateException("Permission callback bound exceeded");
          nativeCallbacks.add(permission);callbacks.put(J.obj("sequence",nativeCallbacks.size(),"type",permission.permission,
              "value",permission.value,"origin",SitePermissions.origin(permission.uri),"privateMode",permission.privateMode,
              "contextMatches",Objects.equals(context,permission.contextId),"thirdPartyAbsent",permission.thirdPartyOrigin==null,"sameSession",true));
        }
        // Observe the original response. No synthetic grant, prompt response or Android permission.
        return original.onContentPermissionRequest(s,permission);
      }
    };
  }
  void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  int count()throws Exception{return test.ui(()->nativeCallbacks.size());}
  void samePage()throws Exception{
    check("Owned native session and exact pool URL remain current",test.ui(()->test.view.current==bound&&bound.isOpen()
        &&test.view.getUrl().equals(GeckoConnectionPoolIntegrationActivity.ORIGIN+"/pool")));
  }
  JSONObject dom()throws Exception{return test.eval("JSON.parse(document.getElementById('pool-permission-state')?.dataset.value||'{}')");}
  void inject()throws Exception{
    String script="(()=>{'use strict';const b=document.createElement('button'),o=document.createElement('output');"
      +"b.id='pool-permission-request';b.textContent='Check site permission';b.style.cssText='position:fixed;left:16px;bottom:16px;height:52px;z-index:10000';"
      +"o.id='pool-permission-state';b.dataset.nonce="+JSONObject.quote(nonce)+";"
      +"const save=v=>{o.dataset.value=JSON.stringify(v)};save({realm:'page-main-world',nonce:b.dataset.nonce,url:location.href,secureContext:isSecureContext,notificationApi:typeof Notification!=='undefined'&&typeof Notification.requestPermission==='function'});"
      +"b.addEventListener('click',e=>{const v={realm:'page-main-world',nonce:b.dataset.nonce,stage:b.dataset.stage,url:location.href,secureContext:isSecureContext,isTrusted:e.isTrusted,userActivation:navigator.userActivation?.isActive===true,requestCalled:false,done:false,before:Notification.permission};save(v);"
      +"if(!e.isTrusted){v.error='untrusted-click';v.done=true;save(v);return;}let p;try{v.requestCalled=true;p=Notification.requestPermission();}catch(error){v.error=error.name;v.done=true;save(v);return;}"
      +"Promise.resolve(p).then(value=>{v.result=value;v.after=Notification.permission;v.done=true;save(v)},error=>{v.error=error.name;v.done=true;save(v)});});"
      +"document.body.append(b,o);})();";
    JSONObject result=test.eval("(()=>{if(document.getElementById('pool-permission-request'))return {injected:false};const s=document.createElement('script');s.textContent="+JSONObject.quote(script)+";document.documentElement.appendChild(s);s.remove();return {injected:true}})()");
    check("One main-world fixture script is inserted into the existing document",result.optBoolean("injected"));
  }
  JSONObject request(String stage)throws Exception{
    samePage();int before=count();
    JSONObject bounds=test.eval("(()=>{const b=document.getElementById('pool-permission-request');b.dataset.stage="+JSONObject.quote(stage)+";const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,width:innerWidth,height:innerHeight}})()");
    JSONObject nativeBounds=test.ui(()->{int[] p=new int[2];test.view.surface.getLocationOnScreen(p);return J.obj("x",p[0],"y",p[1],"width",test.view.surface.getWidth(),"height",test.view.surface.getHeight());});
    test.event("permissionTapNeeded",J.obj("nonce",nonce,"stage",stage,"css",bounds,"native",nativeBounds));
    final JSONObject[] observed={null};
    test.await("Actual trusted permission request "+stage,()->{JSONObject value=dom();if(!stage.equals(value.optString("stage"))||!value.optBoolean("done"))return false;observed[0]=value;return true;},10000);
    JSONObject value=observed[0];
    check("Request "+stage+" comes from the same secure page and one trusted activated click",nonce.equals(value.optString("nonce"))
        &&"page-main-world".equals(value.optString("realm"))&&(GeckoConnectionPoolIntegrationActivity.ORIGIN+"/pool").equals(value.optString("url"))
        &&value.optBoolean("secureContext")&&value.optBoolean("isTrusted")&&value.optBoolean("userActivation")&&value.optBoolean("requestCalled")&&!value.has("error"));
    NetworkCatalog.put(value,"callbacksBefore",before);NetworkCatalog.put(value,"callbacksAfter",count());requests.put(value);return value;
  }
  boolean key(GeckoSession.PermissionDelegate.ContentPermission p){return p.permission==GeckoSession.PermissionDelegate.PERMISSION_DESKTOP_NOTIFICATION
      &&GeckoConnectionPoolIntegrationActivity.ORIGIN.equals(SitePermissions.origin(p.uri))&&Objects.equals(context,p.contextId)
      &&p.privateMode==privateMode&&p.thirdPartyOrigin==null;}
  GeckoSession.PermissionDelegate.ContentPermission query()throws Exception{
    CompletableFuture<List<GeckoSession.PermissionDelegate.ContentPermission>> result=new CompletableFuture<>();
    test.ui(()->{test.view.runtime.getStorageController().getPermissions(GeckoConnectionPoolIntegrationActivity.ORIGIN,context,privateMode)
        .withHandler(test.session.handler).accept(result::complete,result::completeExceptionally);return null;});
    List<GeckoSession.PermissionDelegate.ContentPermission> rows=result.get(3,TimeUnit.SECONDS);
    if(rows==null||rows.size()>128)throw new IOException("Native permission list unavailable or exceeds bound");
    GeckoSession.PermissionDelegate.ContentPermission found=null;
    for(GeckoSession.PermissionDelegate.ContentPermission row:rows)if(key(row)){if(found!=null)throw new IOException("Duplicate native permission key");found=row;}
    return found;
  }
  GeckoSession.PermissionDelegate.ContentPermission readback(String stage,int expected)throws Exception{
    for(int attempt=1;attempt<=3;attempt++){
      samePage();GeckoSession.PermissionDelegate.ContentPermission row=query();
      snapshots.put(J.obj("stage",stage,"attempt",attempt,"present",row!=null,"value",row==null?0:row.value,
          "type",GeckoSession.PermissionDelegate.PERMISSION_DESKTOP_NOTIFICATION,"origin",GeckoConnectionPoolIntegrationActivity.ORIGIN,
          "contextMatches",row==null||Objects.equals(context,row.contextId),"privateMode",privateMode,"thirdPartyAbsent",row==null||row.thirdPartyOrigin==null));
      if(row!=null&&row.value==expected||row==null&&expected==GeckoSession.PermissionDelegate.ContentPermission.VALUE_PROMPT)return row;
      if(attempt<3)Thread.sleep(attempt==1?150:350);
    }
    throw new IOException("Native permission readback did not reach "+stage);
  }
  void write(String stage,GeckoSession.PermissionDelegate.ContentPermission permission,int value)throws Exception{
    samePage();check("Only a genuine notification permission object is dispatched for "+stage,permission!=null&&key(permission)
        &&(value==GeckoSession.PermissionDelegate.ContentPermission.VALUE_DENY||value==GeckoSession.PermissionDelegate.ContentPermission.VALUE_PROMPT));
    test.ui(()->{test.view.runtime.getStorageController().setPermission(permission,value);return null;});
    mutations.put(J.obj("stage",stage,"value",value,"originalNativeObject",true,"source",stage.equals("deny")?"content-permission-callback":"getPermissions-readback"));
  }
  void run()throws Exception{
    NetworkCatalog.put(evidence,"status","running");
    try{
      test.ui(()->{bound=test.view.current;context=bound.getSettings().getContextId();privateMode=bound.getSettings().getUsePrivateMode();active=true;return null;});
      check("The native fixture uses the default normal-browsing namespace",context==null&&!privateMode);
      samePage();inject();JSONObject preflight=dom();NetworkCatalog.put(evidence,"preflight",preflight);
      check("Preflight is an actual main-world record for this one controlled document",nonce.equals(preflight.optString("nonce"))
          &&"page-main-world".equals(preflight.optString("realm"))&&(GeckoConnectionPoolIntegrationActivity.ORIGIN+"/pool").equals(preflight.optString("url")));
      if(!preflight.optBoolean("secureContext")||!preflight.optBoolean("notificationApi")){
        NetworkCatalog.put(evidence,"status","uncovered");NetworkCatalog.put(evidence,"reason",!preflight.optBoolean("secureContext")?"secure-context-unavailable":"notification-api-unavailable");return;
      }
      readback("baseline-default",GeckoSession.PermissionDelegate.ContentPermission.VALUE_PROMPT);
      JSONObject initial=request("initial");
      if(count()==0){NetworkCatalog.put(evidence,"status","uncovered");NetworkCatalog.put(evidence,"reason","content-callback-not-observed");return;}
      check("Initial notification request did not silently grant permission",Arrays.asList("default","denied").contains(initial.optString("result")));
      GeckoSession.PermissionDelegate.ContentPermission original=test.ui(()->nativeCallbacks.get(0));
      write("deny",original,GeckoSession.PermissionDelegate.ContentPermission.VALUE_DENY);
      GeckoSession.PermissionDelegate.ContentPermission denied=readback("deny",GeckoSession.PermissionDelegate.ContentPermission.VALUE_DENY);
      JSONObject deniedPage=request("after-deny");
      check("Stored denial is observed by the next actual page request without another prompt callback","denied".equals(deniedPage.optString("before"))
          &&"denied".equals(deniedPage.optString("result"))&&"denied".equals(deniedPage.optString("after"))&&deniedPage.optInt("callbacksBefore")==deniedPage.optInt("callbacksAfter"));
      write("default",denied,GeckoSession.PermissionDelegate.ContentPermission.VALUE_PROMPT);
      readback("default",GeckoSession.PermissionDelegate.ContentPermission.VALUE_PROMPT);
      JSONObject resetPage=request("after-default");
      check("Default record allows a new native content-permission callback without granting","default".equals(resetPage.optString("before"))
          &&Arrays.asList("default","denied").contains(resetPage.optString("result"))&&resetPage.optInt("callbacksAfter")>resetPage.optInt("callbacksBefore"));
      JSONObject retained=test.eval("({draft:document.getElementById('prompt-textarea').value,sends:Number(document.getElementById('send-count').textContent)})");
      check("Permission checks retain the original unsent draft and send nothing","unsent pool draft".equals(retained.optString("draft"))&&retained.optInt("sends")==0);
      NetworkCatalog.put(evidence,"sameDocument",true);NetworkCatalog.put(evidence,"draftPreserved",true);NetworkCatalog.put(evidence,"sendCount",0);
      NetworkCatalog.put(evidence,"status","passed");
    }catch(Exception|AssertionError error){NetworkCatalog.put(evidence,"status","failed");NetworkCatalog.put(evidence,"error",error.getClass().getSimpleName());throw error;}
    finally{test.ui(()->{active=false;return null;});}
  }
}
