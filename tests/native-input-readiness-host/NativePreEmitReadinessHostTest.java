package local.pocketchat.inputdriver;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Controlled WM shapes and clocks only; never Android input or a failed-instant capture. */
public final class NativePreEmitReadinessHostTest {
  static final int TARGET_UID=10209, SYSTEM_UI_UID=10181;
  static final String TARGET="local.pocketchat.test", COMPONENT=TARGET+"/local.pocketchat.GeckoPerformanceIntegrationActivity";
  static final String SENTINEL="PRIVATE_HOST_SENTINEL_4912";
  static int checks;
  interface Checked { void run() throws Exception; }
  static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static void invalid(String label,Checked action){
    try{action.run();throw new AssertionError("Accepted "+label);}catch(IllegalArgumentException expected){check("invalid-observation".equals(expected.getMessage()),label+" fixed invalid reason");}catch(Exception other){throw new AssertionError(label,other);}
  }
  static String block(int index,String token,String title,int uid,String owner,boolean surface,boolean onScreen,boolean visible){
    return "  Window #"+index+" Window{"+token+" u0 "+title+"}:\n"
      +"    mDisplayId=0 rootTaskId=1 mSession=Session{abc 123:u0a10181}\n"
      +"    mOwnerUid="+uid+" showForAllUsers=true package="+owner+" appop=NONE\n"
      +"    mHasSurface="+surface+" isReadyForDisplay()="+visible+" mWindowRemovalAllowed=false\n"
      +"    WindowStateAnimator{abc "+title+"}:\n      mDrawState=HAS_DRAWN\n"
      +"    isOnScreen="+onScreen+"\n    isVisible="+visible+"\n\n";
  }
  static String shade(boolean visible){return block(2,"9b057bb","NotificationShade",SYSTEM_UI_UID,"com.android.systemui",visible,visible,visible);}
  static String target(){return block(6,"4491833",COMPONENT,TARGET_UID,TARGET,true,true,true);}
  static String window(boolean visible){
    // Controlled complete windows section based on the separately captured clean
    // API35 shape. Changing its shade flags is a counterexample, not a WM dump
    // obtained at the failed InputDispatcher instant.
    return "WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n"
      +"  mCurrentFocus=Window{4491833 u0 "+COMPONENT+"}\n"
      +"  mFocusedApp=ActivityRecord{3f870cf u0 "+COMPONENT+" t9}\n"
      +"WINDOW MANAGER WINDOWS (dumpsys window windows)\n"
      +block(0,"d5f30c8","ScreenDecorOverlayBottom",SYSTEM_UI_UID,"com.android.systemui",false,false,false)
      +block(1,"80bbc5f","ScreenDecorOverlay",SYSTEM_UI_UID,"com.android.systemui",false,false,false)
      +shade(visible)
      +block(3,"8594b28","StatusBar",SYSTEM_UI_UID,"com.android.systemui",true,true,true)
      +block(4,"2da4739","ShellDropTarget",SYSTEM_UI_UID,"com.android.systemui",false,false,false)
      +block(5,"8a1aa1f","InputMethod",10154,"com.google.android.inputmethod.latin",false,false,false)
      +target()
      +block(7,"4a78834","com.android.settings/com.android.settings.FallbackHome",1000,"com.android.settings",false,false,false)
      +block(8,"9c93ec9","com.android.systemui.wallpapers.ImageWallpaper",SYSTEM_UI_UID,"com.android.systemui",true,false,false)
      +"  mTopFocusedDisplayId=0\n"
      +"WINDOW MANAGER TRACE (dumpsys window trace)\nStatus: Disabled\n";
  }
  static NativePreEmitReadiness.State parse(String value){return NativePreEmitReadiness.parse(value,TARGET_UID,SYSTEM_UI_UID);}
  static void parserControls(){
    String clean=window(false),shown=window(true);
    check(parse(clean)==NativePreEmitReadiness.State.CLEAR,"complete clean WM section allows focused AUT");
    check(parse(shown)==NativePreEmitReadiness.State.SHADE_VISIBLE,"visible shade blocks even when AUT focus remains");
    check(LegacyFocusComparator.accepts(clean),"exact original focus parser accepts clean");
    check(LegacyFocusComparator.accepts(shown),"exact original focus parser also accepts controlled visible-shade counterexample");
    check(parse(clean.replace("\n","\r\n"))==NativePreEmitReadiness.State.CLEAR,"CRLF full WM shape accepted");
    String hidden=block(10,"123abcd",COMPONENT,TARGET_UID,TARGET,false,false,false);
    check(parse(clean.replace("  mTopFocusedDisplayId=0",hidden+"  mTopFocusedDisplayId=0"))==NativePreEmitReadiness.State.CLEAR,"other hidden AUT window is not confused with focused token");
    invalid("null",()->parse(null));invalid("empty",()->parse(""));invalid("NUL",()->parse(clean+'\0'));
    invalid("oversized",()->parse(new String(new char[NativePreEmitReadiness.MAX_BYTES+1]).replace('\0','x')));
    invalid("missing windows section",()->parse(clean.replace("WINDOW MANAGER WINDOWS (dumpsys window windows)","WINDOW MANAGER OTHER (dumpsys window other)")));
    invalid("duplicate windows section",()->parse(clean+"WINDOW MANAGER WINDOWS (dumpsys window windows)\nWINDOW MANAGER TRACE (dumpsys window trace)\n"));
    invalid("truncated without section terminator",()->parse(clean.substring(0,clean.indexOf("WINDOW MANAGER TRACE"))));
    invalid("missing shade",()->parse(clean.replace(shade(false),"")));
    invalid("duplicate shade",()->parse(clean.replace(shade(false),shade(false)+shade(false))));
    invalid("missing focused AUT",()->parse(clean.replace(target(),"")));
    invalid("duplicate focused AUT",()->parse(clean.replace(target(),target()+target())));
    invalid("foreign target package",()->parse(clean.replace("package="+TARGET+" appop", "package=other.application appop")));
    invalid("foreign shade package",()->parse(clean.replace("package=com.android.systemui appop", "package=other.systemui appop")));
    invalid("wrong target UID",()->NativePreEmitReadiness.parse(clean,TARGET_UID+1,SYSTEM_UI_UID));
    invalid("wrong systemUI UID",()->NativePreEmitReadiness.parse(clean,TARGET_UID,SYSTEM_UI_UID+1));
    invalid("equal UID arguments",()->NativePreEmitReadiness.parse(clean,TARGET_UID,TARGET_UID));
    invalid("non-app target UID",()->NativePreEmitReadiness.parse(clean,2000,SYSTEM_UI_UID));
    invalid("other-user systemUI UID",()->NativePreEmitReadiness.parse(clean,TARGET_UID,110181));
    invalid("focused display not0",()->parse(clean.replace("mTopFocusedDisplayId=0","mTopFocusedDisplayId=1")));
    invalid("duplicate focused display",()->parse(clean.replace("mTopFocusedDisplayId=0","mTopFocusedDisplayId=0\n  mTopFocusedDisplayId=0")));
    invalid("duplicate current focus",()->parse(clean.replace("  mFocusedApp=", "  mCurrentFocus=Window{4491833 u0 "+COMPONENT+"}\n  mFocusedApp=")));
    invalid("foreign focus",()->parse(clean.replace("mCurrentFocus=Window{4491833 u0 "+COMPONENT+"}","mCurrentFocus=Window{4491833 u0 other.application/.Main}")));
    invalid("non-user0 focused AUT",()->parse(clean.replace("4491833 u0 ","4491833 u10 ")));
    invalid("different focused token",()->parse(clean.replace("mCurrentFocus=Window{4491833","mCurrentFocus=Window{1234567")));
    invalid("shade on wrong display",()->parse(clean.replace(shade(false),shade(false).replace("mDisplayId=0","mDisplayId=1"))));
    invalid("focused AUT on wrong display",()->parse(clean.replace(target(),target().replace("mDisplayId=0","mDisplayId=1"))));
    invalid("malformed window header",()->parse(clean.replace("Window #2 Window{","Window #2 Broken{")));
    invalid("malformed display value",()->parse(clean.replace("mDisplayId=0 rootTaskId=1","mDisplayId=zero rootTaskId=1")));
    invalid("duplicate block display",()->parse(clean.replace(shade(false),shade(false).replace("mDisplayId=0","mDisplayId=0 mDisplayId=0"))));
    invalid("duplicate owner UID",()->parse(clean.replace(shade(false),shade(false).replace("mOwnerUid=10181","mOwnerUid=10181 mOwnerUid=10181"))));
    invalid("duplicate owner package",()->parse(clean.replace(shade(false),shade(false).replace("package=com.android.systemui","package=com.android.systemui package=com.android.systemui"))));
    invalid("missing surface flag",()->parse(clean.replace(shade(false),shade(false).replace("mHasSurface=false ",""))));
    invalid("duplicate surface flag",()->parse(clean.replace(shade(false),shade(false).replace("mHasSurface=false","mHasSurface=false mHasSurface=false"))));
    invalid("invalid surface flag",()->parse(clean.replace(shade(false),shade(false).replace("mHasSurface=false","mHasSurface=unknown"))));
    invalid("duplicate screen flag",()->parse(clean.replace(shade(false),shade(false).replace("isOnScreen=false","isOnScreen=false\n    isOnScreen=false"))));
    invalid("unknown visibility flag",()->parse(clean.replace(shade(false),shade(false).replace("isVisible=false","isVisible=unknown"))));
    invalid("duplicate visibility flag",()->parse(clean.replace(shade(false),shade(false).replace("isVisible=false","isVisible=false\n    isVisible=false"))));
    invalid("focused AUT not visible",()->parse(clean.replace(target(),target().replace("isVisible=true","isVisible=false"))));
    invalid("focused AUT no surface",()->parse(clean.replace(target(),target().replace("mHasSurface=true","mHasSurface=false"))));
    invalid("focused AUT offscreen",()->parse(clean.replace(target(),target().replace("isOnScreen=true","isOnScreen=false"))));
    check(parse(clean.replace(shade(false),shade(false).replace("mHasSurface=false","mHasSurface=true")))==NativePreEmitReadiness.State.SHADE_VISIBLE,"shade surface alone is conservatively not-clear");
    check(parse(clean.replace(shade(false),shade(false).replace("isOnScreen=false","isOnScreen=true")))==NativePreEmitReadiness.State.SHADE_VISIBLE,"shade onscreen alone is not-clear");
    check(parse(clean.replace(shade(false),shade(false).replace("isVisible=false","isVisible=true")))==NativePreEmitReadiness.State.SHADE_VISIBLE,"shade visible alone is not-clear");
  }
  static final class Clock implements NativePreEmitReadiness.Clock {
    long value=1000;boolean frozen;final List<Long> sleeps=new ArrayList<>();
    public long now(){return value;}
    public void sleep(long millis){check(millis>0&&millis<=200,"only bounded <=200ms sleep");sleeps.add(millis);if(!frozen)value+=millis;}
  }
  static final class Probe implements NativePreEmitReadiness.Probe {
    final Clock clock;final List<String> values;final List<Long> limits=new ArrayList<>();int identities,windows,failIdentityAt;boolean snapshotFails;long snapshotFinishesAt=-1;
    Probe(Clock clock,String... values){this.clock=clock;this.values=Arrays.asList(values);}
    public void verifyIdentity()throws Exception{identities++;if(identities==failIdentityAt)throw new Exception(SENTINEL);}
    public String window(long latest)throws Exception{limits.add(latest);windows++;if(snapshotFails)throw new Exception(SENTINEL);if(snapshotFinishesAt>=0)clock.value=snapshotFinishesAt;return values.get(Math.min(windows-1,values.size()-1));}
  }
  static NativePreEmitReadiness.Result await(Clock c,Probe p,long expires){return NativePreEmitReadiness.await(c,p,expires,300,TARGET_UID,SYSTEM_UI_UID);}
  static void result(NativePreEmitReadiness.Result r,boolean passed,String reason,int observations){
    check(r.passed==passed,"exact readiness outcome");check(reason.equals(r.reason),"exact fixed reason "+reason);check(r.observations==observations,"truthful window observation count");check(r.preEmitOnly,"always pre-emission-only");check(!r.reason.contains(SENTINEL),"private probe exception never enters result");
  }
  static void waitControls(){
    Clock c=new Clock();Probe p=new Probe(c,window(false));NativePreEmitReadiness.Result r=await(c,p,5000);result(r,true,"clear",1);
    check(c.sleeps.isEmpty()&&r.elapsedMs==0&&!r.shadeObserved,"clear snapshot has no arbitrary settle wait");check(p.identities==2&&p.windows==1,"identity before and after one snapshot");check(p.limits.equals(Arrays.asList(4700L)),"same original deadline reserves300ms gesture");
    c=new Clock();p=new Probe(c,window(true),window(false));r=await(c,p,5000);result(r,true,"clear",2);check(r.shadeObserved&&r.elapsedMs==200,"shade-to-clear reports truthful wait");check(c.sleeps.equals(Arrays.asList(200L)),"one200ms observation wait");check(p.identities==4&&p.windows==2,"both snapshots identity-fenced");check(p.limits.equals(Arrays.asList(4700L,4700L)),"never extends snapshot deadline");
    c=new Clock();p=new Probe(c,window(true));r=await(c,p,1450);result(r,false,"deadline",1);check(c.value==1150&&r.elapsedMs==150,"stuck shade ends at original latest allowed prep time");check(c.sleeps.equals(Arrays.asList(150L))&&r.shadeObserved,"last wait capped by remaining original budget");check(p.limits.equals(Arrays.asList(1150L)),"no probe after deadline");
    c=new Clock();p=new Probe(c,window(false));r=await(c,p,1300);result(r,false,"deadline",0);check(p.identities==0&&p.windows==0&&c.sleeps.isEmpty(),"expired cannot observe or emit");
    c=new Clock();p=new Probe(c,window(false));r=NativePreEmitReadiness.await(c,p,5000,0,TARGET_UID,SYSTEM_UI_UID);result(r,false,"deadline",0);check(p.windows==0,"invalid duration cannot prepare");
    c=new Clock();p=new Probe(c,window(false));p.failIdentityAt=1;r=await(c,p,5000);result(r,false,"identity-changed",0);check(p.windows==0&&c.sleeps.isEmpty(),"changed initial identity has no snapshot or retry");
    c=new Clock();p=new Probe(c,window(false));p.failIdentityAt=2;r=await(c,p,5000);result(r,false,"identity-changed",1);check(c.sleeps.isEmpty()&&p.windows==1,"identity changed during snapshot cannot pass");
    c=new Clock();p=new Probe(c,window(true),window(false));p.failIdentityAt=3;r=await(c,p,5000);result(r,false,"identity-changed",1);check(p.windows==1&&c.sleeps.equals(Arrays.asList(200L)),"owner change while waiting prevents next snapshot");
    c=new Clock();p=new Probe(c,window(false));p.snapshotFails=true;r=await(c,p,5000);result(r,false,"observation-failed",1);check(p.identities==1&&c.sleeps.isEmpty(),"snapshot failure is not polled");
    c=new Clock();p=new Probe(c,"malformed WM observation");r=await(c,p,5000);result(r,false,"invalid-observation",1);check(p.identities==1&&c.sleeps.isEmpty(),"parser failure is not polled");
    c=new Clock();p=new Probe(c,window(false));p.snapshotFinishesAt=4700;r=await(c,p,5000);result(r,false,"deadline",1);check(r.elapsedMs==3700&&c.sleeps.isEmpty(),"apparently clear late snapshot cannot pass");
    c=new Clock();c.frozen=true;p=new Probe(c,window(true));r=await(c,p,21000);result(r,false,"observation-limit",101);check(p.windows==101&&p.identities==202,"stuck synthetic clock still capped at101observations");check(p.limits.stream().allMatch(x->x==20700L),"max-count control keeps original snapshot deadline");
  }
  static final class Child extends Process {
    final InputStream stdout,stderr;final OutputStream stdin=new ByteArrayOutputStream();final int code;final boolean finishes;boolean alive=true;int destroyed,forced;final List<Long> waits=new ArrayList<>();
    Child(byte[] out,byte[] err,int code,boolean finishes){stdout=new ByteArrayInputStream(out);stderr=new ByteArrayInputStream(err);this.code=code;this.finishes=finishes;}
    public InputStream getInputStream(){return stdout;}public InputStream getErrorStream(){return stderr;}public OutputStream getOutputStream(){return stdin;}
    public int waitFor(){alive=false;return code;}public boolean waitFor(long duration,TimeUnit unit){waits.add(unit.toMillis(duration));if(!alive)return true;if(finishes)alive=false;return finishes;}
    public int exitValue(){if(alive)throw new IllegalThreadStateException();return code;}public boolean isAlive(){return alive;}
    public void destroy(){destroyed++;}public Process destroyForcibly(){forced++;alive=false;return this;}
  }
  static void captureFails(String label,Child child,Clock clock,long latest){
    try{NativePreEmitReadiness.capture(child,clock,latest);throw new AssertionError("Accepted "+label);}catch(Exception expected){check(child.destroyed==1,label+" exact child cleanup");check(!child.alive,label+" child is not left alive");}
  }
  static void captureControls()throws Exception{
    Clock c=new Clock();byte[] clean=window(false).getBytes(StandardCharsets.UTF_8);Child child=new Child(clean,new byte[0],0,true);
    check(NativePreEmitReadiness.capture(child,c,5000).equals(window(false)),"exact bounded UTF8 stdout returned");check(child.waits.equals(Arrays.asList(4000L,100L))&&child.destroyed==1&&child.forced==0,"bounded wait and cleanup only existing child");
    captureFails("nonzero shell exit",new Child(clean,new byte[0],1,true),new Clock(),5000);
    captureFails("shell stderr",new Child(clean,new byte[]{'x'},0,true),new Clock(),5000);
    captureFails("invalid UTF8",new Child(new byte[]{(byte)0xc3},new byte[0],0,true),new Clock(),5000);
    captureFails("stdout byte bound",new Child(new byte[NativePreEmitReadiness.MAX_BYTES+1],new byte[0],0,true),new Clock(),5000);
    captureFails("stderr byte bound",new Child(clean,new byte[65537],0,true),new Clock(),5000);
    Child hung=new Child(clean,new byte[0],0,false);captureFails("child timeout",hung,new Clock(),5000);check(hung.forced==1&&hung.waits.equals(Arrays.asList(4000L,100L)),"timed-out child destroyed without replay");
    Child expired=new Child(clean,new byte[0],0,false);captureFails("already expired child budget",expired,new Clock(),1000);check(expired.waits.equals(Arrays.asList(100L)),"expired snapshot only gets bounded cleanup wait");
    Child excessive=new Child(clean,new byte[0],0,false);captureFails("child budget larger than original20s",excessive,new Clock(),22000);check(excessive.waits.equals(Arrays.asList(100L)),"oversized snapshot budget never enters child wait");
  }
  public static void main(String[] args)throws Exception{
    parserControls();waitControls();captureControls();
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"passed\":"+checks+",\"actualAndroidExecution\":false,\"nativeInputEmitted\":false,\"releaseAcceptance\":false,\"failedInstantWindowCapture\":false}");
  }
  private NativePreEmitReadinessHostTest(){}
}
