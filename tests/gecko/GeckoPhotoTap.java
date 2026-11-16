package local.pocketchat;

import android.graphics.Matrix;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;

/** Test-only preparation of one real Android photo-input tap. Page DPR is not
 * a coordinate authority: Firefox deliberately masks it in protected mode. */
final class GeckoPhotoTap {
  final GeckoIntegrationTestActivity activity;
  final ChatSession session;
  final GeckoWebView web;
  final GeckoSession nativeSession;
  final GeckoView surface;
  final Object port;
  final long serial,deadline,load,navigation,connection;
  final String target,nonce;
  boolean pending,emitted,retired;
  int samples;
  Native previousNative;
  JSONObject previousRect;
  long previousAt;

  static void begin(GeckoIntegrationTestActivity activity,long serial,String target,long deadline){
    new GeckoPhotoTap(activity,serial,target,deadline).poll();
  }
  GeckoPhotoTap(GeckoIntegrationTestActivity activity,long serial,String target,long deadline){
    this.activity=activity;this.serial=serial;this.target=target;this.deadline=deadline;
    session=activity.session;web=session.web;nativeSession=web.current;surface=web.surface;
    port=web.ports.get(nativeSession);load=web.appearanceLoads.getOrDefault(nativeSession,0L);
    navigation=session.navigationEpoch;connection=session.connectionEpoch;nonce=activity.eventStore.nonce;
  }
  boolean owned(){
    boolean same=!retired&&activity.run==serial&&activity.session==session&&session.web==web
        &&("desktopImage".equals(activity.action)||"desktopOwnImage".equals(activity.action))
        &&!activity.isDestroyed()&&!activity.isFinishing()&&!session.deleted&&!web.destroyed&&!web.failed
        &&nativeSession!=null&&nativeSession==web.current&&nativeSession.isOpen()
        &&surface!=null&&surface==web.surface&&surface.getSession()==nativeSession
        &&port!=null&&web.ports.get(nativeSession)==port&&load>0&&web.appearanceLoads.getOrDefault(nativeSession,0L)==load
        &&session.navigationEpoch==navigation&&session.connectionEpoch==connection
        &&target.equals(web.getUrl())&&target.equals(web.locations.get(nativeSession))
        &&activity.eventStore!=null&&nonce.equals(activity.eventStore.nonce)
        &&SystemClock.elapsedRealtime()<deadline;
    if(!same)retired=true;return same;
  }
  boolean ready(){
    return owned()&&!session.navigating&&!session.browserPaused&&!web.pendingLoads.contains(nativeSession)
        &&web.painted.contains(nativeSession)&&web.hasVisibleDocument()&&web.measuredCompositors.contains(nativeSession)
        &&activity.hasWindowFocus()&&web.hasWindowFocus()&&web.isShown()&&web.isAttachedToWindow()
        &&surface.hasWindowFocus()&&surface.isShown()&&surface.isAttachedToWindow();
  }
  void later(){
    if(!owned()||emitted)return;
    session.handler.postDelayed(this::poll,Math.min(100,deadline-SystemClock.elapsedRealtime()));
  }
  void reset(){previousNative=null;previousRect=null;previousAt=0;}
  void poll(){
    if(pending||emitted||!owned())return;
    if(!ready()){reset();later();return;}
    Native before=Native.read(web,nativeSession,surface);
    if(before==null){reset();later();return;}
    pending=true;
    web.evaluateJavascript(script(target),raw->{
      if(!pending||emitted||!owned())return;pending=false;
      if(!ready()){reset();later();return;}
      Native after=Native.read(web,nativeSession,surface);JSONObject rect=J.parse(raw);
      if(!before.same(after)||!validRect(rect,target,nonce,serial)||after.point(rect)==null){reset();later();return;}
      samples++;long now=SystemClock.elapsedRealtime();
      // A first paint can still expose the previous compositor transform.
      // Require the current viewport to fit the actual native surface and two
      // unchanged measurements across separate polls, using the original budget.
      if(previousNative==null||!previousNative.same(after)||!sameRect(previousRect,rect)){
        previousNative=after;previousRect=rect;previousAt=now;later();return;
      }
      if(now-previousAt<100){later();return;}
      Native last=Native.read(web,nativeSession,surface);
      if(!ready()||!after.same(last)){reset();later();return;}
      float[] point=last.point(rect);if(point==null){reset();later();return;}
      emitted=true;
      JSONObject evidence=J.obj("schema",1,"target",target,"runNonce",nonce,"command",serial,
          "nativeSession",System.identityHashCode(nativeSession),"nativePort",System.identityHashCode(port),
          "load",load,"navigation",navigation,"connection",connection,"client",rect,
          "geometry",last.json(),"stableSamples",samples,"stableMillis",now-previousAt,
          "screenX",Math.round(point[0]),"screenY",Math.round(point[1]),"nativeMatrix",true,
          "activityFocused",activity.hasWindowFocus(),"surfaceFocused",surface.hasWindowFocus(),
          "preEmitOnly",true,"injectionFocusGuaranteed",false,"originalBudgetMs",25000);
      activity.event(serial,"tapNeeded",J.obj("id","upload-"+serial,"x",Math.round(point[0]),"y",Math.round(point[1]),
          "nativeMatrix",true,"photoTap",evidence));
    });
  }
  static String script(String target){
    return "(()=>{if(location.href!=="+JSONObject.quote(target)+")return null;const e=document.getElementById('upload'),v=visualViewport,p=document.getElementById('photo-evidence');if(!e||!v||!p)return null;const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,a=JSON.parse(p.textContent);return {url:location.href,runNonce:a?.runNonce,command:a?.command,mode:a?.mode,document:performance.timeOrigin,ready:document.documentElement.dataset.photoReady==='true',ownedTarget:e===document.elementFromPoint(x,y)&&e.type==='file'&&!e.disabled,visible:document.visibilityState==='visible',left:r.left,top:r.top,right:r.right,bottom:r.bottom,viewportLeft:v.offsetLeft,viewportTop:v.offsetTop,viewportWidth:v.width,viewportHeight:v.height,scrollX,scrollY,pageDpr:devicePixelRatio,pageScale:v.scale}})()";
  }
  static boolean validRect(JSONObject r,String target,String nonce,long serial){
    if(!target.equals(r.optString("url"))||!nonce.equals(r.optString("runNonce"))||r.optLong("command",-1)!=serial
        ||!"select".equals(r.optString("mode"))||!r.optBoolean("ready")||!r.optBoolean("ownedTarget")||!r.optBoolean("visible"))return false;
    for(String key:new String[]{"document","left","top","right","bottom","viewportLeft","viewportTop","viewportWidth","viewportHeight"})
      if(!Double.isFinite(r.optDouble(key,Double.NaN)))return false;
    return r.optDouble("document")>0&&r.optDouble("right")>r.optDouble("left")&&r.optDouble("bottom")>r.optDouble("top")
        &&r.optDouble("viewportWidth")>0&&r.optDouble("viewportHeight")>0;
  }
  static boolean sameRect(JSONObject a,JSONObject b){
    if(a==null)return false;
    for(String key:new String[]{"document","left","top","right","bottom","viewportLeft","viewportTop","viewportWidth","viewportHeight"})
      if(a.optDouble(key,Double.NaN)!=b.optDouble(key,Double.NaN))return false;
    return true;
  }
  static final class Native {
    final Matrix matrix;final float[] values=new float[9];final int[] origin=new int[2];
    final int width,height,webWidth,webHeight;final float layout;
    Native(GeckoWebView web,GeckoSession session,GeckoView surface){
      matrix=new Matrix();session.getClientToSurfaceMatrix(matrix);matrix.getValues(values);
      surface.getLocationOnScreen(origin);width=surface.getWidth();height=surface.getHeight();
      webWidth=web.getWidth();webHeight=web.getHeight();layout=web.readingLayout;
    }
    static Native read(GeckoWebView web,GeckoSession session,GeckoView surface){
      Native n=new Native(web,session,surface);
      if(n.width<=0||n.height<=0||n.webWidth<=0||n.webHeight<=0||!Float.isFinite(n.layout)||n.layout<=0)return null;
      for(float value:n.values)if(!Float.isFinite(value))return null;
      // The SDK client transform has positive uniform scale and translation.
      // Reject singular, reflected, skewed or perspective matrices explicitly.
      float[] m=n.values;if(m[0]<=0||m[4]!=m[0]||m[1]!=0||m[3]!=0||m[6]!=0||m[7]!=0||m[8]!=1)return null;
      if(Math.abs(n.width*n.layout-n.webWidth)>2)return null;
      return n;
    }
    boolean same(Native n){return n!=null&&width==n.width&&height==n.height&&webWidth==n.webWidth&&webHeight==n.webHeight
        &&layout==n.layout&&java.util.Arrays.equals(values,n.values)&&java.util.Arrays.equals(origin,n.origin);}
    float[] point(JSONObject r){
      // Gecko's client matrix is zoom plus native client-top translation; it
      // does not include the visual viewport's offset in the layout viewport.
      // getBoundingClientRect is already relative to that layout viewport, so
      // subtract its visual offset once and do not add page scroll coordinates.
      double left=r.optDouble("left")-r.optDouble("viewportLeft"),right=r.optDouble("right")-r.optDouble("viewportLeft");
      double top=r.optDouble("top")-r.optDouble("viewportTop"),bottom=r.optDouble("bottom")-r.optDouble("viewportTop");
      double vw=r.optDouble("viewportWidth"),vh=r.optDouble("viewportHeight");
      if(left<0||top<0||right>vw||bottom>vh)return null;
      // Unlike DPR, the CSS layout viewport and native surface must agree.
      // A cached previous-document zoom cannot pass this independent check.
      if(Math.abs(vw*values[0]-width)>2)return null;
      float[] bounds={(float)left,(float)top,(float)right,(float)bottom};matrix.mapPoints(bounds);
      for(float value:bounds)if(!Float.isFinite(value))return null;
      if(bounds[0]<0||bounds[1]<0||bounds[2]>width||bounds[3]>height||bounds[2]-bounds[0]<2||bounds[3]-bounds[1]<2)return null;
      float x=origin[0]+(bounds[0]+bounds[2])*.5f*layout,y=origin[1]+(bounds[1]+bounds[3])*.5f*layout;
      int px=Math.round(x),py=Math.round(y);
      if(!Float.isFinite(x)||!Float.isFinite(y)||px<=origin[0]+bounds[0]*layout||px>=origin[0]+bounds[2]*layout
          ||py<=origin[1]+bounds[1]*layout||py>=origin[1]+bounds[3]*layout)return null;
      return new float[]{x,y};
    }
    JSONObject json(){JSONArray matrixValues=new JSONArray();for(float value:values)matrixValues.put(Float.valueOf(value));
      return J.obj("clientToSurface",matrixValues,"originX",origin[0],"originY",origin[1],"surfaceWidth",width,"surfaceHeight",height,
          "webWidth",webWidth,"webHeight",webHeight,"readingLayout",layout);}
  }
}
