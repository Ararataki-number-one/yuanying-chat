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
  // Synthetic records follow the pinned API35 FocusResolver/WindowInfo dump
  // format. They are not a captured input snapshot from the failed T0.
  static String inputRow(int index,String name,int uid,int pid,String flags){
    return "      "+index+": name="+name+", id="+(100+index)+", displayId=0, inputConfig="+flags
      +", alpha=1, frame=[0,36][320,604], globalScale=1, applicationInfo.name=controlled"
      +", applicationInfo.token=0x123, touchableRegion=[0,36][320,604], ownerPid="+pid
      +", ownerUid="+uid+", dispatchingTimeout=5000ms, token=0x456, touchOcclusionMode=BLOCK_UNTRUSTED\n"
      +"    transform (ROT_0) (IDENTITY)\n";
  }
  static String input(boolean shade){
    return "Input Reader State:\n  controlled unrelated reader state\nInput Dispatcher State:\n"
      +"  DispatchEnabled: true\n  DispatchFrozen: false\n  InputFilterEnabled: false\n  FocusedDisplayId: 0\n"
      +"  FocusedApplications:\n    displayId=0, name='controlled', dispatchingTimeout=5000ms\n"
      +"  FocusedWindows:\n    displayId=0, name='4491833 "+COMPONENT+"'\n"
      +"  FocusRequests:\n    displayId=0, name='old request is not focus' result='OK'\n"
      +"  Pointer Capture Requested: false\n  Current Window with Pointer Capture: None\n"
      +"  TouchStates: <no displays touched>\n  Display: 0\n    logicalSize=1080x1920\n"
      +"        transform (ROT_0) (IDENTITY)\n    Windows:\n"
      +inputRow(0,"8594b28 StatusBar",SYSTEM_UI_UID,991,"NOT_FOCUSABLE | TRUSTED_OVERLAY")
      +inputRow(1,"4491833 "+COMPONENT,TARGET_UID,1234,"0x0")
      +(shade?inputRow(2,"9b057bb NotificationShade",SYSTEM_UI_UID,991,"NOT_FOCUSABLE | TRUSTED_OVERLAY"):"")
      +"  Global Monitors: <none>\n  RecentQueue: <empty>\n  PendingEvent: <none>\n"
      +"  InboundQueue: <empty>\n  CommandQueue: <empty>\n  Connections:\n"
      +"    461: channelName='9b057bb NotificationShade (server)', status=NORMAL, monitor=false, responsive=true\n"
      +"      OutboundQueue: <empty>\n      WaitQueue: <empty>\n"
      +"  Configuration:\n    KeyRepeatDelay: 50ms\n";
  }
  static java.util.Map<String,Object> parseInput(String raw){
    return NativePreEmitReadiness.parseInput(raw,window(false),TARGET_UID,SYSTEM_UI_UID,1234);
  }
  static String oldAnr(String raw){return "\nInput Dispatcher State at time of last ANR:\n"+raw.substring(raw.indexOf("Input Dispatcher State:\n")+"Input Dispatcher State:\n".length());}
  static void inputParserControls(){
    String clean=input(false),shown=input(true),target=inputRow(1,"4491833 "+COMPONENT,TARGET_UID,1234,"0x0");
    check(parseInput(clean).get("state").equals("CLEAR"),"residual Connections shade channel is not an active window");
    check(parseInput(clean.replace("\n","\r\n")).get("state").equals("CLEAR"),"complete CRLF input dump");
    check(parseInput(shown).get("state").equals("SHADE_VISIBLE"),"WM clear cannot override actual input shade");
    check(parseInput(clean+oldAnr(shown)).get("state").equals("CLEAR"),"old ANR shade cannot block a current clear window");
    check(parseInput(shown+oldAnr(clean)).get("state").equals("SHADE_VISIBLE"),"old ANR clear cannot override current shade");
    invalid("current missing target cannot borrow old ANR",()->parseInput(clean.replace(target,"")+oldAnr(clean)));
    invalid("null input",()->parseInput(null));invalid("empty input",()->parseInput(""));
    invalid("NUL input",()->parseInput(clean+'\0'));
    invalid("oversized input",()->parseInput(new String(new char[NativePreEmitReadiness.MAX_BYTES+1]).replace('\0','x')));
    invalid("missing current header",()->parseInput(clean.replace("Input Dispatcher State:\n","")));
    invalid("duplicate current header",()->parseInput(clean+clean));
    invalid("historical-only section",()->parseInput(oldAnr(clean)));
    invalid("duplicate historical section",()->parseInput(clean+oldAnr(clean)+oldAnr(clean)));
    invalid("disabled dispatch",()->parseInput(clean.replace("DispatchEnabled: true","DispatchEnabled: false")));
    invalid("frozen dispatch",()->parseInput(clean.replace("DispatchFrozen: false","DispatchFrozen: true")));
    invalid("input filter active",()->parseInput(clean.replace("InputFilterEnabled: false","InputFilterEnabled: true")));
    invalid("unknown dispatch flag",()->parseInput(clean.replace("DispatchEnabled: true","DispatchEnabled: unknown")));
    invalid("duplicate unknown dispatch flag",()->parseInput(clean.replace("DispatchEnabled: true","DispatchEnabled: true\n  DispatchEnabled: unknown")));
    invalid("wrong focused display",()->parseInput(clean.replace("FocusedDisplayId: 0","FocusedDisplayId: 1")));
    invalid("duplicate focused display",()->parseInput(clean.replace("FocusedDisplayId: 0","FocusedDisplayId: 0\n  FocusedDisplayId: 0")));
    invalid("missing current focus",()->parseInput(clean.replace("  FocusedWindows:\n    displayId=0, name='4491833 "+COMPONENT+"'\n","  FocusedWindows: <none>\n")));
    invalid("wrong current focus token",()->parseInput(clean.replace("name='4491833 "+COMPONENT+"'","name='abcd "+COMPONENT+"'")));
    invalid("duplicate focus",()->parseInput(clean.replace("  FocusRequests:","    displayId=0, name='4491833 "+COMPONENT+"'\n  FocusRequests:")));
    invalid("missing active display0",()->parseInput(clean.replace("  Display: 0","  Display: 1")));
    invalid("duplicate active display0",()->parseInput(clean.replace("  Global Monitors:","  Display: 0\n    Windows: <none>\n  Global Monitors:")));
    invalid("unknown active display",()->parseInput(clean.replace("  Global Monitors:","  Display: unknown\n    Windows: <none>\n  Global Monitors:")));
    invalid("missing display geometry",()->parseInput(clean.replace("    logicalSize=1080x1920\n","")));
    invalid("empty active windows",()->parseInput(clean.replace("    Windows:\n","    Windows: <none>\n")));
    invalid("unknown display boundary cannot hide active shade",()->parseInput(shown.replace("      2: name=","  UnknownSection: unexpected\n      2: name=")));
    invalid("duplicate active windows heading with none",()->parseInput(clean.replace("    Windows:\n","    Windows:\n    Windows: <none>\n")));
    invalid("wrong target uid",()->parseInput(clean.replace(target,target.replace("ownerUid=10209","ownerUid=10210"))));
    invalid("wrong target pid",()->parseInput(clean.replace(target,target.replace("ownerPid=1234","ownerPid=1235"))));
    invalid("duplicate target uid",()->parseInput(clean.replace(target,target.replace("ownerUid=10209","ownerUid=10209, ownerUid=10209"))));
    invalid("null target pid",()->parseInput(clean.replace(target,target.replace("ownerPid=1234","ownerPid=null"))));
    invalid("row display differs",()->parseInput(clean.replace(target,target.replace("displayId=0","displayId=1"))));
    invalid("duplicate target window",()->parseInput(clean.replace(target,target+target.replace("      1:","      2:"))));
    invalid("malformed row",()->parseInput(clean.replace("      1: name=","      1: broken=")));
    invalid("nonsequential rows",()->parseInput(clean.replace("      1: name=","      3: name=")));
    invalid("unknown target flag",()->parseInput(clean.replace(target,target.replace("inputConfig=0x0","inputConfig=FUTURE_UNKNOWN"))));
    invalid("nonzero unknown bits",()->parseInput(clean.replace(target,target.replace("inputConfig=0x0","inputConfig=0x200000"))));
    invalid("duplicate target flags",()->parseInput(clean.replace(target,target.replace("inputConfig=0x0","inputConfig=WATCH_OUTSIDE_TOUCH | WATCH_OUTSIDE_TOUCH"))));
    for(String flag:Arrays.asList("NO_INPUT_CHANNEL","NOT_VISIBLE","NOT_FOCUSABLE","NOT_TOUCHABLE","IS_WALLPAPER",
        "PAUSE_DISPATCHING","DROP_INPUT","DROP_INPUT_IF_OBSCURED","SPY","GLOBAL_STYLUS_BLOCKS_TOUCH"))
      invalid("blocked target "+flag,()->parseInput(clean.replace(target,target.replace("inputConfig=0x0","inputConfig="+flag))));
    invalid("transparent target",()->parseInput(clean.replace(target,target.replace("alpha=1","alpha=0"))));
    invalid("unknown target alpha",()->parseInput(clean.replace(target,target.replace("alpha=1","alpha=NaN"))));
    invalid("empty target region",()->parseInput(clean.replace(target,target.replace("touchableRegion=[0,36][320,604]","touchableRegion=<empty>"))));
    String shade=inputRow(2,"9b057bb NotificationShade",SYSTEM_UI_UID,991,"NOT_FOCUSABLE | TRUSTED_OVERLAY");
    invalid("wrong shade owner",()->parseInput(shown.replace(shade,shade.replace("ownerUid=10181","ownerUid=10209"))));
    invalid("malformed shade name",()->parseInput(shown.replace(shade,shade.replace("9b057bb NotificationShade","NotificationShade"))));
    invalid("unknown shade flag",()->parseInput(shown.replace(shade,shade.replace("TRUSTED_OVERLAY","UNKNOWN_FLAG"))));
    for(String flag:Arrays.asList("DROP_INPUT","NO_INPUT_CHANNEL","PAUSE_DISPATCHING"))
      check(parseInput(shown.replace(shade,shade.replace("TRUSTED_OVERLAY",flag))).get("state").equals("SHADE_VISIBLE"),"shade "+flag+" cannot declare a safe route");
    for(String flag:Arrays.asList("NOT_VISIBLE","NOT_TOUCHABLE"))
      check(parseInput(shown.replace(shade,shade.replace("TRUSTED_OVERLAY",flag))).get("state").equals("CLEAR"),"non-targetable shade "+flag+" is observed explicitly");
    invalid("truncated display block",()->parseInput(clean.substring(0,clean.indexOf("  Global Monitors:"))));
  }
  static final class DispatchProbe implements NativePreEmitReadiness.Probe {
    final Probe wm;final List<String> values;final List<Long> inputLimits=new ArrayList<>();int reads;boolean fails;long finishesAt=-1;
    DispatchProbe(Clock clock,String[] windows,String... input){wm=new Probe(clock,windows);values=Arrays.asList(input);}
    public void verifyIdentity()throws Exception{wm.verifyIdentity();}
    public String window(long latest)throws Exception{return wm.window(latest);}
    public String input(long latest)throws Exception{inputLimits.add(latest);reads++;if(fails)throw new Exception(SENTINEL);if(finishesAt>=0)wm.clock.value=finishesAt;return values.get(Math.min(reads-1,values.size()-1));}
  }
  static NativePreEmitReadiness.Result currentWait(Clock c,NativePreEmitReadiness.Probe p,long expires){
    return NativePreEmitReadiness.awaitInput(c,p,expires,300,TARGET_UID,SYSTEM_UI_UID,1234);
  }
  static void inputWaitControls(){
    Clock c=new Clock();DispatchProbe p=new DispatchProbe(c,new String[]{window(false)},input(false));
    NativePreEmitReadiness.Result r=currentWait(c,p,5000);result(r,true,"clear",1);
    check(p.reads==1&&p.wm.windows==1&&p.wm.identities==3&&c.sleeps.isEmpty(),"one actual input observation between stable owner checks, no extra settle sleep");
    check(p.inputLimits.equals(Arrays.asList(4700L))&&p.wm.limits.equals(Arrays.asList(4700L)),"both processes share original latest deadline");
    java.util.Map<String,Object> proof=r.inputObservations.get(0);
    check(proof.get("targetPid").equals(1234)&&proof.get("targetUid").equals(TARGET_UID)&&proof.get("state").equals("CLEAR"),"receipt includes actual parsed target state");
    check(proof.get("sha256").equals(NativePreEmitReadiness.snapshotSha(input(false)))&&proof.get("bytes").equals(input(false).getBytes(StandardCharsets.UTF_8).length),"receipt binds exact input dump bytes without retaining private text");
    check(proof.get("startedUptimeMs").equals(1000L)&&proof.get("completedUptimeMs").equals(1000L)&&proof.get("latestUptimeMs").equals(4700L),"truthful original snapshot times");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(true),window(false)},input(false));r=currentWait(c,p,5000);result(r,true,"clear",2);
    check(p.reads==1&&p.wm.identities==5&&r.shadeObserved&&c.sleeps.equals(Arrays.asList(200L)),"WMS shade still waits before querying input");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(true),input(false));r=currentWait(c,p,5000);result(r,true,"clear",2);
    check(p.reads==2&&p.wm.identities==6&&r.inputShadeObserved&&!r.shadeObserved&&c.sleeps.equals(Arrays.asList(200L)),"WM-clear/input-shade counterexample must wait in original loop");
    check(r.inputObservations.get(0).get("state").equals("SHADE_VISIBLE")&&r.inputObservations.get(1).get("state").equals("CLEAR"),"receipt preserves both differing actual states");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(true));r=currentWait(c,p,1450);result(r,false,"deadline",1);
    check(p.reads==1&&c.value==1150&&c.sleeps.equals(Arrays.asList(150L)),"stuck input shade never extends original budget");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));r=currentWait(c,p,1300);result(r,false,"deadline",0);check(p.reads==0&&p.wm.windows==0,"expired current path does not observe or emit");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));p.wm.snapshotFinishesAt=4700;r=currentWait(c,p,5000);result(r,false,"deadline",1);check(p.reads==0,"late WMS never starts input read");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));p.finishesAt=4700;r=currentWait(c,p,5000);result(r,false,"deadline",1);check(p.reads==1&&c.sleeps.isEmpty(),"late input clear cannot pass");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));p.wm.failIdentityAt=2;r=currentWait(c,p,5000);result(r,false,"identity-changed",1);check(p.reads==0,"owner change before input prevents read");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));p.wm.failIdentityAt=3;r=currentWait(c,p,5000);result(r,false,"identity-changed",1);check(p.reads==1&&c.sleeps.isEmpty(),"owner change after input prevents admission");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},input(false));p.fails=true;r=currentWait(c,p,5000);result(r,false,"observation-failed",1);check(p.reads==1&&c.sleeps.isEmpty(),"failed input command is not retried");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},"unknown input state");r=currentWait(c,p,5000);result(r,false,"invalid-observation",1);check(p.reads==1&&c.sleeps.isEmpty(),"malformed input is not retried");
    c=new Clock();p=new DispatchProbe(c,new String[]{window(false)},(String)null);r=currentWait(c,p,5000);result(r,false,"invalid-observation",1);
    c=new Clock();Probe legacy=new Probe(c,window(false));r=currentWait(c,legacy,5000);result(r,false,"observation-failed",1);check(c.sleeps.isEmpty(),"legacy WM-only probe cannot satisfy current readiness");
    c=new Clock();c.frozen=true;p=new DispatchProbe(c,new String[]{window(false)},input(true));r=currentWait(c,p,21000);result(r,false,"observation-limit",101);
    check(p.reads==101&&p.wm.windows==101&&p.wm.identities==303&&p.inputLimits.stream().allMatch(x->x==20700L),"new input reads share the original101-loop/absolute deadline limit");
  }
  public static void main(String[] args)throws Exception{
    parserControls();waitControls();captureControls();inputParserControls();inputWaitControls();
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"passed\":"+checks+",\"actualAndroidExecution\":false,\"nativeInputEmitted\":false,\"releaseAcceptance\":false,\"failedInstantWindowCapture\":false}");
  }
  private NativePreEmitReadinessHostTest(){}
}
