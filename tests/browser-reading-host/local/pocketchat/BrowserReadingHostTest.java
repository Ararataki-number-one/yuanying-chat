package local.pocketchat;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import android.view.MotionEvent;

public final class BrowserReadingHostTest {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static boolean near(float a,float b){return Math.abs(a-b)<.015;}
  static BrowserReading make(ChatSession s){BrowserReading r=new BrowserReading(s);s.web.reading=r;r.configure(true);r.started(s.web.url);r.visible(s.web.url);s.handler.drain();return r;}
  public static void main(String[] args)throws Exception{
    for(int width:new int[]{960,1080,1170,2400}){float scale=BrowserReadingPolicy.target(width,3,width/3f,1.5f);check("Zoom round trip at pixel width "+width,near(BrowserReadingPolicy.fromScale(width,3,width/3f,scale),1.5f));}
    check("A 360dp phone starts at natural reading size",near(BrowserReadingPolicy.target(1080,3,360,1),3));
    check("Inset-reduced phone width retains natural reading size",near(BrowserReadingPolicy.target(984,3,328,1),3));
    check("Invalid and missing measurements do not invent a fixed desktop width",BrowserReadingPolicy.fit(0,3,360)==0&&BrowserReadingPolicy.fit(1080,Float.NaN,0)==0);
    check("Invalid preferences fall back to fit",BrowserReadingPolicy.bounded(Float.NaN)==1&&BrowserReadingPolicy.bounded(Float.POSITIVE_INFINITY)==1);
    check("Zoom allows smaller reading and bounds corrupt extreme values",BrowserReadingPolicy.bounded(.4f)==.6f&&BrowserReadingPolicy.bounded(.8f)==.8f&&BrowserReadingPolicy.bounded(100)==20);
    check("Shrinking preserves relative CSS and device scale",near(BrowserReadingPolicy.target(1080,3,360,.8f),2.4f)&&near(BrowserReadingPolicy.fromScale(1080,3,360,2.4f),.8f));
    check("Untrusted and login origins cannot save zoom",!BrowserReadingPolicy.chat("https://accounts.google.com/")&&!BrowserReadingPolicy.chat("https://chatgpt.com.evil/")&&!BrowserReadingPolicy.chat("https://user@chatgpt.com/")&&!BrowserReadingPolicy.chat("https://chatgpt.com:444/")&&!BrowserReadingPolicy.chat("http://chatgpt.com/"));
    ChatSession.Prefs store=new ChatSession.Prefs();ChatSession s=new ChatSession(store);BrowserReading r=make(s);Object same=s.web;
    check("A new environment defaults to fitting its view",r.choice()==1&&s.web.zoomCalls==0);
    r.choose(1.5f);s.handler.drain();check("Explicit zoom is applied without replacing the web surface",s.web==same&&near(s.web.scale,BrowserReadingPolicy.target(1080,3,360,1.5f)));
    s.web.scale*=1.2f;r.scaled(s.web.scale);check("Input focus auto zoom cannot replace the chosen value",near(r.choice(),1.5f));
    check("Single finger scrolling is passed through",!s.web.touch.touch(s.web,new MotionEvent(0,1)));
    s.web.touch.touch(s.web,new MotionEvent(MotionEvent.ACTION_POINTER_DOWN,2));s.web.touch.touch(s.web,new MotionEvent(MotionEvent.ACTION_UP,1));s.handler.drain();check("A two-finger tap without zoom cannot save automatic focus magnification",near(r.choice(),1.5f));
    s.web.touch.touch(s.web,new MotionEvent(MotionEvent.ACTION_POINTER_DOWN,2));r.scaled(BrowserReadingPolicy.target(1080,3,360,2f));s.web.scale=BrowserReadingPolicy.target(1080,3,360,2f);s.web.touch.touch(s.web,new MotionEvent(MotionEvent.ACTION_UP,1));s.handler.drain();
    check("Intentional native pinch zoom is retained",near(r.choice(),2f));
    s.web.scale=BrowserReadingPolicy.target(1080,3,360,1.8f);r.scaled(s.web.scale);check("Pinching back to the starting scale stores the final choice",near(r.choice(),1.8f));
    r.choose(4.2f);s.handler.drain();check("A large pinch choice can be retained without a three-times cap",near(r.choice(),4.2f));r.choose(1.8f);s.handler.drain();
    ChatSession restarted=new ChatSession(store);BrowserReading reopened=make(restarted);check("Reopening the same environment restores its saved choice",near(reopened.choice(),1.8f)&&near(restarted.web.scale,BrowserReadingPolicy.target(1080,3,360,1.8f)));
    BrowserReading other=make(new ChatSession(new ChatSession.Prefs()));check("Another environment starts with independent zoom",other.choice()==1);
    restarted.web.size(2400,800);restarted.handler.drain();check("Landscape keeps the chosen natural text size",near(restarted.web.scale,BrowserReadingPolicy.target(2400,3,800,1.8f))&&near(reopened.choice(),1.8f));
    int zooms=restarted.web.zoomCalls;reopened.keyboard(true);restarted.web.size(2400,400);restarted.handler.drain();check("Keyboard height changes do not reset zoom",restarted.web.zoomCalls==zooms&&near(reopened.choice(),1.8f));
    check("Keyboard resize requests focus visibility only",restarted.web.scriptCalls>0&&restarted.web.script.equals(BrowserReadingPolicy.focusScript()));
    reopened.keyboard(false);int scripts=restarted.web.scriptCalls;restarted.web.size(2400,800);restarted.handler.drain();check("Reading a long reply without keyboard never scrolls via helper",restarted.web.scriptCalls==scripts);
    reopened.started("https://accounts.google.com/");restarted.web.url="https://accounts.google.com/";reopened.visible(restarted.web.url);restarted.handler.drain();check("Login pages use their own scale and leave preference intact",restarted.web.initial==0&&!reopened.ready&&near(reopened.choice(),1.8f));
    reopened.configure(false);reopened.scaled(5);check("Phone mode retains but does not apply desktop zoom",restarted.web.initial==0&&near(reopened.choice(),1.8f));
    ChatSession stale=new ChatSession(new ChatSession.Prefs());BrowserReading cancelled=make(stale);stale.web.touch.touch(stale.web,new MotionEvent(MotionEvent.ACTION_POINTER_DOWN,2));stale.web.touch.touch(stale.web,new MotionEvent(MotionEvent.ACTION_UP,1));cancelled.started("https://chatgpt.com/c/new");stale.web.scale=2.5f;stale.handler.drain();check("A gesture from an earlier document cannot save on the next page",cancelled.choice()==1);
    check("Only raw chat temporarily hides navigation for typing",BrowserReadingPolicy.hideNavigation(true,true,true)&&!BrowserReadingPolicy.hideNavigation(false,true,true)&&!BrowserReadingPolicy.hideNavigation(true,false,true)&&!BrowserReadingPolicy.hideNavigation(true,true,false));
    ChatSession measured=new ChatSession(new ChatSession.Prefs());measured.web.measuredViewportRequired=true;measured.web.scale=1;
    BrowserReading nativeReading=make(measured);check("Native zoom waits for the actual page viewport",measured.web.zoomCalls==0);
    measured.web.scale=2.4f;nativeReading.viewportMeasured(450);measured.handler.drain();
    check("Actual CSS viewport sets fit instead of a guessed 1024px width",measured.web.zoomCalls==0&&nativeReading.viewportWidth==450);
    nativeReading.choose(1.25f);measured.handler.drain();check("Measured viewport supports explicit reading magnification",near(measured.web.scale,3));
    measured.web.size(2400,1000);measured.handler.drain();check("Rotation waits for the new document geometry",near(measured.web.scale,3)&&nativeReading.viewportWidth==0);
    measured.web.scale=3.75f;nativeReading.viewportMeasured(800);measured.handler.drain();check("Rotation preserves relative magnification after reflow",near(measured.web.scale,3.75f)&&near(nativeReading.choice(),1.25f));
    nativeReading.started("https://accounts.google.com/");check("Login navigation clears earlier page measurements",nativeReading.viewportWidth==0&&!nativeReading.ready);
    ChatSession.Prefs legacy=new ChatSession.Prefs();legacy.putFloat(BrowserReadingPolicy.LEGACY_ZOOM_KEY,4);
    BrowserReading migrated=make(new ChatSession(legacy));check("Old zoom is converted to natural reading size",near(migrated.choice(),4f*1080/(1024*3)));
    check("Migration retains the earlier setting for rollback",legacy.getFloat(BrowserReadingPolicy.LEGACY_ZOOM_KEY,0)==4&&legacy.contains(BrowserReadingPolicy.ZOOM_KEY));
    legacy.putFloat(BrowserReadingPolicy.LEGACY_ZOOM_KEY,8);check("Legacy conversion runs only once",near(migrated.choice(),4f*1080/(1024*3)));
    check("Old whole-desktop fit becomes readable natural fit",BrowserReadingPolicy.migrate(1080,3,1)==1);
    ChatSession fitSession=new ChatSession(new ChatSession.Prefs());BrowserReading fitted=make(fitSession);fitted.choose(4.2f);fitSession.handler.drain();
    check("Stored large reading choices still restore intentionally",near(fitted.choice(),4.2f)&&near(fitSession.web.scale,12.6f));
    int priorAligned=fitSession.web.alignCalls;fitSession.web.scrollY=320;fitted.fit();fitSession.handler.drain();check("The controlled compositor changes vertical position during pinch",fitSession.web.scrollY!=320);fitSession.handler.drain();
    check("Explicit fit stores one hundred percent and aligns the same surface once",fitted.choice()==1&&near(fitSession.web.scale,3)&&fitSession.web.alignCalls==priorAligned+1);
    check("Fit restores the vertical position captured before shrinking",fitSession.web.scrollY==320&&fitSession.web.lastAlignedY==320);
    int beforeZoom=fitSession.web.zoomCalls;fitSession.web.nativeZoomActive=true;fitted.choose(1.5f);fitSession.handler.drain();
    check("An in flight programmatic pinch does not start an overlapping pinch",fitSession.web.zoomCalls==beforeZoom&&fitted.restoreAttempts==0);
    fitSession.web.nativeZoomActive=false;fitSession.handler.drain();check("The saved choice applies after its native pinch finishes",fitSession.web.zoomCalls==beforeZoom+1&&near(fitSession.web.scale,4.5f));
    ChatSession nativeLate=new ChatSession(new ChatSession.Prefs());nativeLate.web.nativeMeasured=false;BrowserReading waitingNative=make(nativeLate);waitingNative.choose(1.5f);nativeLate.handler.drain();
    check("A page supplied DPR cannot substitute for missing native compositor metrics",nativeLate.web.zoomCalls==0);
    nativeLate.web.nativeMeasured=true;waitingNative.nativeScaleMeasured();nativeLate.handler.drain();check("A native compositor update unlocks restoration without replacing the browser",near(nativeLate.web.scale,4.5f)&&waitingNative.choice()==1.5f);
    ChatSession nextDocument=new ChatSession(new ChatSession.Prefs());nextDocument.web.measuredViewportRequired=true;BrowserReading nativeAcrossDocuments=make(nextDocument);nativeAcrossDocuments.viewportMeasured(360);nextDocument.handler.drain();nativeAcrossDocuments.choose(1.5f);nextDocument.handler.drain();
    Object sameNative=nextDocument.web;int previousDocumentZooms=nextDocument.web.zoomCalls;nextDocument.prefs.putFloat(BrowserReadingPolicy.ZOOM_KEY,4.2f);nextDocument.web.url="https://chatgpt.com/c/next-document";nativeAcrossDocuments.started(nextDocument.web.url);nativeAcrossDocuments.visible(nextDocument.web.url);nextDocument.handler.drain();
    check("An already measured open compositor survives navigation while fresh DOM width is required",nextDocument.web==sameNative&&nextDocument.web.nativeMeasured&&nativeAcrossDocuments.viewportWidth==0&&nextDocument.web.zoomCalls==previousDocumentZooms);
    nativeAcrossDocuments.viewportMeasured(450);nextDocument.handler.drain();check("A new document restores its stored choice without another identical native zoom callback",nativeAcrossDocuments.choice()==4.2f&&near(nextDocument.web.scale,BrowserReadingPolicy.target(1080,3,450,4.2f))&&nextDocument.web.zoomCalls==previousDocumentZooms+1);
    if(args.length>0)Files.write(Paths.get(args[0]),BrowserReadingPolicy.focusScript().getBytes(StandardCharsets.UTF_8));
    StringBuilder out=new StringBuilder("{\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"scope\":\"Production controller with host doubles; no Android renderer\",\"checks\":[");for(int i=0;i<checks.size();i++){if(i>0)out.append(',');out.append("{\"name\":\"").append(checks.get(i)).append("\",\"pass\":true}");}System.out.println(out.append("]}"));
  }
}
