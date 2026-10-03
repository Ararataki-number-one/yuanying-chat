package local.pocketchat;

import android.os.SystemClock;
import android.view.MotionEvent;

/** Presentation only: retains the existing WebView and profile-scoped preferences. */
final class BrowserReading {
  final ChatSession session;boolean desktop,ready,pinching,pinchChanged,keyboard;long document,gestureUntil,gesture;int width;float gestureScale,viewportWidth;
  final Runnable restore=this::restoreScale,focus=this::revealFocus;
  BrowserReading(ChatSession s){session=s;s.web.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
    int next=r-l;if(next<=0)return;boolean changed=next!=width;width=next;
    if(changed){viewportWidth=0;cancelGesture();prepare();scheduleRestore();}if(keyboard&&b-t!=ob-ot)scheduleFocus();
  });s.web.setOnTouchListener((v,event)->{touch(event);return false;});}
  float density(){return session.context.getResources().getDisplayMetrics().density;}
  float choice(){
    try{if(session.prefs.contains(BrowserReadingPolicy.ZOOM_KEY))return BrowserReadingPolicy.bounded(session.prefs.getFloat(BrowserReadingPolicy.ZOOM_KEY,1f));
      if(width<=0)return 1;
      float value=BrowserReadingPolicy.migrate(width,density(),session.prefs.getFloat(BrowserReadingPolicy.LEGACY_ZOOM_KEY,1f));
      session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,value).apply();return value;
    }catch(ClassCastException ignored){return 1;}
  }
  void cancelGesture(){gesture++;pinching=false;pinchChanged=false;gestureUntil=0;}
  void configure(boolean value){desktop=value;ready=false;cancelGesture();session.handler.removeCallbacks(restore);prepare();}
  void prepare(){int available=session.web.getWidth();if(available>0)width=available;session.web.setInitialScale(0);}
  void started(String url){document++;ready=false;viewportWidth=0;cancelGesture();session.handler.removeCallbacks(restore);session.handler.removeCallbacks(focus);session.web.setInitialScale(0);}
  void viewportMeasured(float value){if(!Float.isFinite(value)||value<=0)return;boolean changed=Math.abs(value-viewportWidth)>.5f;viewportWidth=value;if(changed)scheduleRestore();}
  void visible(String url){if(!url.equals(session.web.getUrl()))return;ready=desktop&&BrowserReadingPolicy.chat(url);if(ready)scheduleRestore();}
  void scheduleRestore(){session.handler.removeCallbacks(restore);if(desktop&&ready)session.handler.postDelayed(restore,120);}
  @SuppressWarnings("deprecation") void restoreScale(){
    if(!desktop||!ready||pinching||!BrowserReadingPolicy.chat(session.web.getUrl())||width<=0||session.web.requiresViewportMeasurement()&&viewportWidth<=0)return;
    float current=session.web.getScale(),target=BrowserReadingPolicy.target(width,density(),viewportWidth,choice());
    if(current<=0||target<=0)return;float factor=target/current;
    if(Math.abs(factor-1)>.015f)session.web.zoomBy(Math.max(.01f,Math.min(100f,factor)));
  }
  void choose(float value){cancelGesture();session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,BrowserReadingPolicy.bounded(value)).apply();prepare();scheduleRestore();}
  void scaled(float value){if(value>0&&!Float.isNaN(value)&&!Float.isInfinite(value)&&BrowserReadingPolicy.remember(desktop,ready,pinching||SystemClock.uptimeMillis()<gestureUntil,session.web.getUrl())&&(pinchChanged||Math.abs(value-gestureScale)>.01f)){pinchChanged=true;session.prefs.edit().putFloat(BrowserReadingPolicy.ZOOM_KEY,BrowserReadingPolicy.fromScale(width,density(),viewportWidth,value)).apply();}}
  @SuppressWarnings("deprecation") void touch(MotionEvent event){if(!desktop||!ready)return;int action=event.getActionMasked();if(event.getPointerCount()>1){if(!pinching){gesture++;pinchChanged=false;gestureScale=session.web.getScale();}pinching=true;gestureUntil=SystemClock.uptimeMillis()+400;session.handler.removeCallbacks(restore);}if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL){if(pinching){pinching=false;gestureUntil=SystemClock.uptimeMillis()+400;final long owner=document,token=gesture;final int measured=width;session.handler.postDelayed(()->{if(owner==document&&token==gesture&&measured==width&&ready)capturePinch();},160);}}}
  @SuppressWarnings("deprecation") void capturePinch(){if(!pinchChanged)return;float actual=session.web.getScale();if(actual>0)scaled(actual);}
  void keyboard(boolean value){keyboard=value;if(value)scheduleFocus();else session.handler.removeCallbacks(focus);}
  void scheduleFocus(){session.handler.removeCallbacks(focus);session.handler.postDelayed(focus,160);}
  void revealFocus(){if(keyboard&&desktop&&ready&&BrowserReadingPolicy.chat(session.web.getUrl()))session.web.evaluateJavascript(BrowserReadingPolicy.focusScript(),null);}
}
