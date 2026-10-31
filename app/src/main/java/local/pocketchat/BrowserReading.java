package local.pocketchat;

import android.os.SystemClock;
import android.view.MotionEvent;

/** Presentation only: retains the existing WebView and profile-scoped preferences. */
final class BrowserReading {
  final ChatSession session;boolean desktop,ready,pinching,pinchChanged,keyboard,alignLeft,touching,dragged,restoreAllowed,focusAllowed,focusAfterTouch;long document,gestureUntil,gesture,focusRequest,touchDocument,touchEpoch;int width,restoreAttempts;float gestureScale,viewportWidth,fitY=Float.NaN,downX,downY,touchSlop;
  final Runnable restore=this::restoreScale,focus=this::revealFocus;Runnable zoomFocus;boolean precisionAllowed;
  ScaleRestore scaleRestore;boolean displayHidden,displayPageChanged;
  void hideDisplay(){displayHidden=true;displayPageChanged=false;touching=false;cancelGesture();cancelPosition();}
  void showDisplay(){displayHidden=false;if(displayPageChanged){displayPageChanged=false;started(session.web.getUrl());visible(session.web.getUrl());}}
  static final class ScaleRestore {
    final long document,gesture,epoch,started;final int width;final float viewport,choice;final String url;final boolean precision;
    long requestedAt;float requestedScale;double requestedError;boolean fineUsed,invalid,closed;
    ScaleRestore(BrowserReading r,long now){document=r.document;gesture=r.gesture;epoch=r.session.navigationEpoch;started=now;width=r.width;viewport=r.viewportWidth;choice=r.choice();url=r.session.web.getUrl();precision=!r.alignLeft&&choice>1&&r.session.web.requiresViewportMeasurement()&&viewport>0;}
    boolean current(BrowserReading r){return !r.displayHidden&&!invalid&&document==r.document&&gesture==r.gesture&&epoch==r.session.navigationEpoch&&width==r.width&&width==r.session.web.getWidth()&&viewport==r.viewportWidth&&choice==r.choice()&&url.equals(r.session.web.getUrl());}
  }
  BrowserReading(ChatSession s){session=s;s.web.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
    if(displayHidden)return;int next=r-l;if(next<=0)return;boolean changed=next!=width;width=next;
    if(changed){viewportWidth=0;cancelGesture();if(touching)cancelPosition();else{restoreAllowed=true;precisionAllowed=true;}prepare();scheduleRestore();}if(keyboard&&(l!=ol||t!=ot||r!=or||b!=ob))queueFocus();
  });s.web.setOnTouchListener((v,event)->{touch(event);return false;});}
  float density(){return session.context.getResources().getDisplayMetrics().density;}
  float choice(){
    try{if(session.prefs.contains(BrowserReadingPolicy.ZOOM_KEY))return BrowserReadingPolicy.bounded(session.prefs.getFloat(BrowserReadingPolicy.ZOOM_KEY,1f));
      if(width<=0)return 1;
      float value=BrowserReadingPolicy.migrate(width,density(),session.prefs.getFloat(BrowserReadingPolicy.LEGACY_ZOOM_KEY,1f));
      session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,value).apply();return value;
    }catch(ClassCastException ignored){return 1;}
  }
  void cancelGesture(){gesture++;pinching=false;pinchChanged=false;gestureUntil=0;restoreAttempts=0;scaleRestore=null;}
  void cancelPosition(){if(scaleRestore!=null)scaleRestore.invalid=true;precisionAllowed=false;restoreAllowed=false;alignLeft=false;fitY=Float.NaN;focusAllowed=false;focusAfterTouch=false;zoomFocus=null;focusRequest++;session.handler.removeCallbacks(restore);session.handler.removeCallbacks(focus);}
  void configure(boolean value){desktop=value;ready=false;cancelGesture();cancelPosition();restoreAllowed=true;precisionAllowed=true;prepare();}
  void prepare(){int available=session.web.getWidth();if(available>0)width=available;session.web.setInitialScale(0);}
  void started(String url){if(displayHidden){displayPageChanged=true;return;}document++;ready=false;viewportWidth=0;cancelGesture();cancelPosition();restoreAllowed=true;precisionAllowed=true;alignLeft=desktop&&session.web.readingPage(url)&&choice()<=1;session.web.setInitialScale(0);if(!desktop||!session.web.readingPage(url))session.web.setReadingLayout(1);}
  void viewportMeasured(float value){if(displayHidden||!Float.isFinite(value)||value<=0)return;boolean changed=Math.abs(value-viewportWidth)>.5f;if(scaleRestore!=null&&value!=scaleRestore.viewport)scaleRestore.invalid=true;viewportWidth=value;if(changed)scheduleRestore();}
  void nativeScaleMeasured(){if(!displayHidden)scheduleRestore();}
  void visible(String url){if(displayHidden)return;if(!url.equals(session.web.getUrl()))return;ready=desktop&&session.web.readingPage(url);if(ready)scheduleRestore();}
  void scheduleRestore(){
    session.handler.removeCallbacks(restore);
    if(displayHidden||!restoreAllowed||touching||!desktop||!ready)return;
    long now=SystemClock.uptimeMillis(),delay=120;
    if(scaleRestore!=null){
      if(!scaleRestore.current(this))scaleRestore.invalid=true;
      if(scaleRestore.precision&&(!precisionAllowed||scaleRestore.closed||scaleRestore.invalid||now-scaleRestore.started>3000))return;
      if(scaleRestore.precision&&now>=scaleRestore.requestedAt+500&&!session.web.readingZoomActive()){
        float measured=session.web.getScale(),target=BrowserReadingPolicy.target(width,density(),viewportWidth,choice());
        if(BrowserReadingPolicy.restored(width,measured,viewportWidth,choice())&&Math.abs(target/measured-1)<=.015f){precisionAllowed=false;scaleRestore.closed=true;return;}
      }
      if(restoreAttempts>=3){
        if(restoreAttempts!=3||scaleRestore.fineUsed||!scaleRestore.current(this)||now-scaleRestore.started>3000)return;
        // Retain the primary request's existing 500 ms observation. An early
        // native callback neither spends another request nor advances it.
        if(now>=scaleRestore.requestedAt+500&&(session.web.readingZoomActive()||!fineCorrection(now,session.web.getScale())))return;
      }
      delay=Math.max(delay,500-(now-scaleRestore.requestedAt));
    }
    session.handler.postDelayed(restore,delay);
  }
  boolean fineCorrection(long now,float current){
    ScaleRestore own=scaleRestore;
    if(displayHidden||own==null||!precisionAllowed||own.closed||own.fineUsed||!own.current(this)||alignLeft||own.choice<=1||!session.web.requiresViewportMeasurement()||now<own.requestedAt+500||now-own.started>3000)return false;
    float target=BrowserReadingPolicy.target(width,density(),viewportWidth,choice()),factor=target/current;
    double error=BrowserReadingPolicy.zoomError(width,current,viewportWidth,choice());
    return Float.isFinite(current)&&current>0&&Float.isFinite(factor)&&Math.abs(factor-1)<=.03f&&error>.035&&own.requestedError-error>.0001&&Math.abs(current-own.requestedScale)>.00001f;
  }
  @SuppressWarnings("deprecation") void restoreScale(){
    if(displayHidden||!restoreAllowed||touching||!desktop||!ready||pinching||!session.web.readingPage(session.web.getUrl())||width<=0||!session.web.readingScaleMeasured()||session.web.requiresViewportMeasurement()&&viewportWidth<=0)return;
    if(session.web.requiresViewportMeasurement()&&choice()>1&&!precisionAllowed)return;
    if(scaleRestore!=null&&scaleRestore.precision){
      if(scaleRestore.closed)return;
      long now=SystemClock.uptimeMillis();
      if(!scaleRestore.current(this)||now-scaleRestore.started>3000){scaleRestore.invalid=true;return;}
      long remaining=500-(now-scaleRestore.requestedAt);
      if(remaining>0){session.handler.removeCallbacks(restore);session.handler.postDelayed(restore,remaining);return;}
    }
    if(session.web.readingZoomActive()){scheduleRestore();return;}
    if(session.web.setReadingLayout(choice())){if(scaleRestore!=null)scaleRestore.invalid=true;viewportWidth=0;return;}
    boolean nativeFit=alignLeft&&session.web.requiresViewportMeasurement();
    // setReadingLayout may retain a nearby value; fit that applied layout.
    float current=session.web.getScale(),target=BrowserReadingPolicy.target(width,density(),viewportWidth,nativeFit?session.web.readingLayout:choice());
    if(current<=0||target<=0)return;float factor=target/current;
    // Both measurements include readingLayout; undo it once to compare the
    // rendered page width with the native view before consuming a fit anchor.
    boolean atTarget=alignLeft&&(nativeFit?BrowserReadingPolicy.fitted(width,current,viewportWidth,session.web.readingLayout):Math.abs(factor-1)<=.015f);
    boolean measuredChoice=!alignLeft&&choice()>1&&session.web.requiresViewportMeasurement();
    boolean correction=nativeFit?!atTarget:Math.abs(factor-1)>.015f||measuredChoice&&!BrowserReadingPolicy.restored(width,current,viewportWidth,choice());
    if(correction){
      long now=SystemClock.uptimeMillis();boolean primary=restoreAttempts<3;
      if(!primary&&(restoreAttempts!=3||!fineCorrection(now,current)))return;
      if(measuredChoice){
        if(scaleRestore==null)scaleRestore=new ScaleRestore(this,now);
        if(!primary){scaleRestore.fineUsed=true;scaleRestore.closed=true;precisionAllowed=false;}
        scaleRestore.requestedAt=now;scaleRestore.requestedScale=current;scaleRestore.requestedError=BrowserReadingPolicy.zoomError(width,current,viewportWidth,choice());
      }
      restoreAttempts++;
      session.web.zoomBy(Math.max(.01f,Math.min(100f,factor)));
      session.handler.removeCallbacks(restore);if(primary)session.handler.postDelayed(restore,500);
    }
    else if(atTarget){alignLeft=false;session.web.alignReadingLeft(fitY);fitY=Float.NaN;}
    else if(measuredChoice){precisionAllowed=false;if(scaleRestore!=null)scaleRestore.closed=true;}
  }
  void choose(float value){if(displayHidden)return;cancelGesture();restoreAllowed=true;precisionAllowed=true;float selected=BrowserReadingPolicy.bounded(value);alignLeft=selected<=1;fitY=alignLeft?session.web.readingScrollY():Float.NaN;session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,selected).apply();prepare();scheduleRestore();if(keyboard)scheduleFocus();}
  void fit(){choose(1);}
  void scaled(float value){if(displayHidden)return;if(Float.isFinite(value)&&value>0&&scaleRestore!=null&&scaleRestore.precision)scheduleRestore();if(value>0&&!Float.isNaN(value)&&!Float.isInfinite(value)&&BrowserReadingPolicy.remember(desktop,ready,pinching||SystemClock.uptimeMillis()<gestureUntil,session.web.getUrl())&&(pinchChanged||Math.abs(value-gestureScale)>.01f)){pinchChanged=true;session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,BrowserReadingPolicy.fromScale(width,density(),viewportWidth,value)).apply();}}
  @SuppressWarnings("deprecation") void touch(MotionEvent event){
    if(displayHidden)return;int action=event.getActionMasked();
    if(action==MotionEvent.ACTION_DOWN){touching=true;dragged=false;touchDocument=document;touchEpoch=session.navigationEpoch;downX=event.getRawX();downY=event.getRawY();touchSlop=session.web.readingTouchSlop();cancelGesture();cancelPosition();}
    if(touching&&action==MotionEvent.ACTION_MOVE&&!dragged){float x=event.getRawX()-downX,y=event.getRawY()-downY;if(x*x+y*y>touchSlop*touchSlop){dragged=true;cancelPosition();}}
    if(desktop&&ready&&event.getPointerCount()>1){touching=true;dragged=true;if(!pinching){gesture++;pinchChanged=false;gestureScale=session.web.getScale();cancelPosition();}pinching=true;gestureUntil=SystemClock.uptimeMillis()+400;session.handler.removeCallbacks(restore);}
    if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL){
      boolean pinch=pinching,tap=action==MotionEvent.ACTION_UP&&touching&&!dragged&&!pinch&&touchDocument==document&&touchEpoch==session.navigationEpoch;touching=false;
      if(!tap)cancelPosition();
      if(pinch){pinching=false;gestureUntil=SystemClock.uptimeMillis()+400;final long owner=document,token=gesture;final int measured=width;session.handler.postDelayed(()->{if(owner==document&&token==gesture&&measured==width&&ready&&!touching)capturePinch();},160);}
      // A tap permits a future current-editor layout, but UP alone does not
      // pull the page toward an editor that remained focused while reading.
      if(tap){focusAllowed=keyboard;if(restoreAllowed){if(alignLeft)fitY=session.web.readingScrollY();scheduleRestore();}if(focusAfterTouch&&keyboard)queueFocus();}
      focusAfterTouch=false;
    }
  }
  @SuppressWarnings("deprecation") void capturePinch(){if(displayHidden||touching||!pinchChanged)return;float actual=session.web.getScale();if(actual>0)scaled(actual);restoreAttempts=0;restoreAllowed=true;scheduleRestore();}
  void keyboard(boolean value){if(keyboard==value)return;keyboard=value;focusRequest++;zoomFocus=null;if(value)scheduleFocus();else{focusAllowed=false;focusAfterTouch=false;session.handler.removeCallbacks(focus);}}
  /** A new IME or explicit zoom may request reveal; geometry alone cannot revive it. */
  void scheduleFocus(){if(displayHidden)return;focusAllowed=true;focusAfterTouch=touching&&!dragged&&!pinching;queueFocus();}
  void queueFocus(){focusRequest++;zoomFocus=null;session.handler.removeCallbacks(focus);if(!displayHidden&&focusAllowed&&!touching)session.handler.postDelayed(focus,160);}
  void nativeZoomFinished(){Runnable pending=zoomFocus;zoomFocus=null;if(pending!=null)pending.run();}
  void revealFocus(){
    zoomFocus=null;if(displayHidden||!focusAllowed||touching||!keyboard||!desktop||!ready||pinching||!session.web.readingPage(session.web.getUrl()))return;
    final String url=session.web.getUrl();final long owner=document,token=gesture,request=focusRequest,epoch=session.navigationEpoch;final float layout=session.web.readingLayout;
    java.util.function.BooleanSupplier current=()->!displayHidden&&focusAllowed&&!touching&&keyboard&&desktop&&ready&&!pinching&&owner==document&&token==gesture&&request==focusRequest&&epoch==session.navigationEpoch&&layout==session.web.readingLayout&&url.equals(session.web.getUrl())&&session.web.readingPage(url)&&!session.web.readingZoomActive();
    if(session.web.readingZoomActive()){zoomFocus=()->{if(current.getAsBoolean())revealFocus();};return;}
    session.web.revealReadingFocus(url,current);
  }
}
