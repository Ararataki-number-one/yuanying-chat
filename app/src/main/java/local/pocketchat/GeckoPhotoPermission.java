package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.*;

/** One real picker request, captured before selection and never shared with page messages. */
final class GeckoPhotoPermission {
  private final GeckoWebView web;private final GeckoSession session;private final WebExtension.Port port;
  private final String token=UUID.randomUUID().toString(),sessionId,origin,location;
  private final long navigation,load;private final boolean requested;
  private String documentId="";private boolean closed,handed,capturing;
  private Consumer<AttachmentIssue> afterCapture;
  GeckoPhotoPermission(GeckoWebView web,GeckoSession session){
    this.web=web;this.session=session;port=web.routePort;sessionId=AppSessionIdentity.id(session);
    origin=web.photoUploadOrigin(session);location=web.locations.get(session);navigation=web.owner.navigationEpoch;
    load=web.appearanceLoads.getOrDefault(session,0L);requested=web.owner.privacy.level()>=2;
  }
  boolean current(){return !closed&&!web.destroyed&&!web.owner.deleted&&web.owner.web==web&&web.current==session&&session.isOpen()
    &&navigation==web.owner.navigationEpoch&&load==web.appearanceLoads.getOrDefault(session,0L)
    &&Objects.equals(location,web.locations.get(session))&&!web.pendingLoads.contains(session);}
  private boolean connected(){return current()&&port!=null&&web.routePort==port&&!origin.isEmpty();}
  private boolean bound(JSONObject value){return value.optInt("schema")==1&&sessionId.equals(value.optString("sessionId"))
    &&token.equals(value.optString("requestToken"))&&origin.equals(value.optString("origin"))
    &&"origin-and-origin-attributes".equals(value.optString("scope"))&&value.optString("documentId").matches("[1-9][0-9]{0,23}");}
  private void send(String kind,Consumer<JSONObject> complete){
    if(!connected()){complete.accept(new JSONObject());return;}
    int id=web.cookieCallbacks.add(port,value->complete.accept(J.parse(value)),6000);
    try{JSONObject message=J.obj("kind",kind,"id",id,"sessionId",sessionId,"requestToken",token);
      if("photoCanvasCapture".equals(kind))message.put("origin",origin);port.postMessage(message);
    }catch(Exception unavailable){web.cookieCallbacks.complete(port,id,null);}
  }
  void capture(Runnable ready){
    if(!requested){ready.run();return;}
    capturing=true;
    send("photoCanvasCapture",value->{
      capturing=false;
      if(closed||handed)return;
      boolean captured=connected()&&bound(value)&&"captured".equals(value.optString("status"));
      if(captured)documentId=value.optString("documentId");
      Consumer<AttachmentIssue> selectedImage=afterCapture;afterCapture=null;
      if(selectedImage!=null)allow(true,selectedImage);
      else if(!captured)releaseNative();
    });
    // The chooser may open while the image-only document lease is captured.
    ready.run();
  }
  void allow(boolean containsImage,Consumer<AttachmentIssue> complete){
    if(!current()){cancel();complete.accept(AttachmentIssue.PAGE_CHANGED);return;}
    if(!containsImage||web.owner.privacy.level()<2){releaseNative();complete.accept(null);return;}
    if(capturing){afterCapture=complete;return;}
    if(!connected()||documentId.isEmpty()){cancel();complete.accept(AttachmentIssue.PHOTO_UNCONFIRMED);return;}
    send("photoCanvasGrant",value->{
      String status=value.optString("status");long expires=value.optLong("expiresAt",-1),now=System.currentTimeMillis();
      boolean granted="granted".equals(status)&&expires>now&&expires<=now+125000;
      boolean existing=("existing".equals(status)||"not-required".equals(status)&&web.owner.privacy.level()<2)&&expires==0;
      if(connected()&&bound(value)&&documentId.equals(value.optString("documentId"))&&(granted||existing))complete.accept(null);
      else{cancel();complete.accept("denied".equals(status)?AttachmentIssue.PHOTO_DENIED:AttachmentIssue.PHOTO_UNCONFIRMED);}
    });
  }
  void handedOff(){handed=true;}
  void cancel(){
    if(handed||closed)return;
    closed=true;releaseNative();
    Consumer<AttachmentIssue> selectedImage=afterCapture;afterCapture=null;
    if(selectedImage!=null)selectedImage.accept(AttachmentIssue.PAGE_CHANGED);
  }
  private void releaseNative(){
    if(!requested||port==null||web.routePort!=port)return;
    int id=web.cookieCallbacks.add(port,ignored->{},1500);
    try{port.postMessage(J.obj("kind","photoCanvasRelease","id",id,"sessionId",sessionId,"requestToken",token));}
    catch(RuntimeException unavailable){web.cookieCallbacks.complete(port,id,null);}
  }
}
