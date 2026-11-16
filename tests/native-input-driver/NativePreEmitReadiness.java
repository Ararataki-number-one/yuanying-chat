package local.pocketchat.inputdriver;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Test-only, pre-T0 observation of the known NotificationShade competitor. */
public final class NativePreEmitReadiness {
  public static final int MAX_BYTES=2097152, MAX_OBSERVATIONS=101, INTERVAL_MS=200;
  static final String TARGET="local.pocketchat.test", SYSTEM_UI="com.android.systemui";
  public enum State { CLEAR, SHADE_VISIBLE }
  public interface Clock { long now(); void sleep(long millis); }
  public interface Probe {
    void verifyIdentity() throws Exception;
    String window(long latestUptimeMs) throws Exception;
    default String input(long latestUptimeMs) throws Exception {
      throw new IllegalStateException("input-observation-unavailable");
    }
  }
  public static final class Result {
    public boolean passed,shadeObserved;
    public final boolean preEmitOnly=true;
    public int observations;
    public long elapsedMs;
    public String reason="deadline";
    public boolean inputShadeObserved;
    public final ArrayList<Map<String,Object>> inputObservations=new ArrayList<>();
  }
  static IllegalArgumentException invalid(){return new IllegalArgumentException("invalid-observation");}
  static String one(String raw,String expression,int group){
    Matcher m=Pattern.compile(expression,Pattern.MULTILINE).matcher(raw);
    if(!m.find())throw invalid();String value=m.group(group);if(m.find())throw invalid();return value;
  }
  static boolean flag(String raw,String name,boolean line){
    String value=one(raw,line?"^[ \\t]*"+name+"=([^\\r\\n]*)$":"\\b"+name+"=([^\\s]+)",1).trim();
    if(!value.equals("true")&&!value.equals("false"))throw invalid();
    return "true".equals(value);
  }
  public static State parse(String raw,int targetUid,int systemUiUid){
    if(raw==null||raw.isEmpty()||raw.length()>MAX_BYTES||raw.indexOf('\0')>=0
        ||targetUid<10000||targetUid>=100000||systemUiUid<10000||systemUiUid>=100000||targetUid==systemUiUid)throw invalid();
    if(!"0".equals(one(raw,"^[ \\t]*mTopFocusedDisplayId=([^\\r\\n]*)$",1).trim()))throw invalid();
    String focused=one(raw,"^[ \\t]*mCurrentFocus=([^\\r\\n]*)$",1).trim();
    Matcher focusedWindow=Pattern.compile("Window\\{([0-9a-f]+ u0 "+Pattern.quote(TARGET)+"/[^\\s}]+)\\}").matcher(focused);
    if(!focusedWindow.matches())throw invalid();String focus=focusedWindow.group(1);
    String sectionHeader="^WINDOW MANAGER WINDOWS \\(dumpsys window windows\\)[ \\t]*$";
    Matcher section=Pattern.compile(sectionHeader,Pattern.MULTILINE).matcher(raw);
    if(!section.find())throw invalid();int from=section.end();if(section.find())throw invalid();
    Matcher end=Pattern.compile("^WINDOW MANAGER [^\\r\\n]+$",Pattern.MULTILINE).matcher(raw);
    if(!end.find(from))throw invalid();int to=end.start();String windows=raw.substring(from,to);
    Pattern header=Pattern.compile("^  Window #[0-9]+ Window\\{([0-9a-f]+) u([0-9]+) ([^\\r\\n}]+)\\}:[ \\t]*$",Pattern.MULTILINE);
    Matcher m=header.matcher(windows);ArrayList<Integer> starts=new ArrayList<>(),ends=new ArrayList<>();ArrayList<String> identities=new ArrayList<>(),titles=new ArrayList<>();
    while(m.find()){starts.add(m.start());ends.add(m.end());identities.add(m.group(1)+" u"+m.group(2)+" "+m.group(3));titles.add(m.group(3));}
    Matcher any=Pattern.compile("^  Window #[^\\r\\n]*$",Pattern.MULTILINE).matcher(windows);int count=0;while(any.find())count++;
    if(starts.isEmpty()||starts.size()!=count)throw invalid();
    int targetCount=0,shadeCount=0;boolean shade=false;
    for(int i=0;i<starts.size();i++){
      String block=windows.substring(ends.get(i),i+1<starts.size()?starts.get(i+1):windows.length());
      String display=one(block,"\\bmDisplayId=([^\\s]+)",1);if(!display.matches("[0-9]+"))throw invalid();
      if(!"0".equals(display))continue;
      boolean isTarget=identities.get(i).equals(focus),isShade=titles.get(i).equals("NotificationShade");
      if(!isTarget&&!isShade)continue;
      String ownerLine=one(block,"^[ \\t]*mOwnerUid=([^\\r\\n]*)$",1);
      String uid=one("mOwnerUid="+ownerLine,"\\bmOwnerUid=([^\\s]+)",1);
      String owner=one(ownerLine,"\\bpackage=([^\\s]+)",1);
      boolean surface=flag(block,"mHasSurface",false),onScreen=flag(block,"isOnScreen",true),visible=flag(block,"isVisible",true);
      if(isTarget){
        if(!owner.equals(TARGET)||!uid.equals(Integer.toString(targetUid))||!surface||!onScreen||!visible)throw invalid();
        targetCount++;
      }else{
        if(!identities.get(i).contains(" u0 ")||!owner.equals(SYSTEM_UI)||!uid.equals(Integer.toString(systemUiUid)))throw invalid();
        shadeCount++;shade=surface||onScreen||visible;
      }
    }
    if(targetCount!=1||shadeCount!=1)throw invalid();
    return shade?State.SHADE_VISIBLE:State.CLEAR;
  }
  public static Result await(Clock clock,Probe probe,long expires,int duration,int targetUid,int systemUiUid){
    Result result=new Result();long started=clock.now();
    try{
      if(duration<=0||expires<duration)return result;
      long latest=expires-duration;
      while(result.observations<MAX_OBSERVATIONS){
        if(clock.now()>=latest)return result;
        try{probe.verifyIdentity();}catch(Exception failure){result.reason="identity-changed";return result;}
        result.observations++;String raw;
        try{raw=probe.window(latest);}catch(Exception failure){result.reason="observation-failed";return result;}
        State state;
        try{state=parse(raw,targetUid,systemUiUid);}catch(IllegalArgumentException failure){result.reason="invalid-observation";return result;}
        if(state==State.SHADE_VISIBLE)result.shadeObserved=true;
        try{probe.verifyIdentity();}catch(Exception failure){result.reason="identity-changed";return result;}
        if(clock.now()>=latest)return result;
        if(state==State.CLEAR){result.passed=true;result.reason="clear";return result;}
        long remaining=latest-clock.now();if(remaining<=0)return result;
        clock.sleep(Math.min(INTERVAL_MS,remaining));
      }
      result.reason="observation-limit";return result;
    }finally{result.elapsedMs=Math.max(0,clock.now()-started);}
  }
  static String currentInputState(String raw){
    if(raw==null||raw.isEmpty()||raw.length()>MAX_BYTES||raw.indexOf('\0')>=0)throw invalid();
    Matcher start=Pattern.compile("^Input Dispatcher State:[ \\t]*\\r?$",Pattern.MULTILINE).matcher(raw);
    if(!start.find())throw invalid();int from=start.end();if(start.find())throw invalid();
    Matcher history=Pattern.compile("^Input Dispatcher State at time of last ANR:[ \\t]*\\r?$",Pattern.MULTILINE).matcher(raw);
    int to=raw.length();if(history.find()){if(history.start()<from)throw invalid();to=history.start();if(history.find())throw invalid();}
    return raw.substring(from,to);
  }
  static String inputBlock(String raw,String heading){
    Matcher candidates=Pattern.compile("^"+Pattern.quote(heading)+"(?:[ \\t\\r].*)?$",Pattern.MULTILINE).matcher(raw);
    int count=0;while(candidates.find())count++;if(count!=1)throw invalid();
    Matcher start=Pattern.compile("^"+Pattern.quote(heading)+"[ \\t]*\\r?$",Pattern.MULTILINE).matcher(raw);
    if(!start.find())throw invalid();int from=start.end();if(start.find())throw invalid();
    Matcher end=Pattern.compile("^  [^ \\t\\r\\n].*$",Pattern.MULTILINE).matcher(raw);
    if(!end.find(from))throw invalid();
    if(heading.startsWith("  Display: ")&&!end.group().matches(
        "  (?:Display: (?:0|[1-9][0-9]*)|Global monitors on display (?:0|[1-9][0-9]*):|Global Monitors: <none>)[ \\t]*\\r?"))throw invalid();
    return raw.substring(from,end.start());
  }
  static String inputField(String row,String name){
    return one(row,"(?:^|, )"+Pattern.quote(name)+"=([^,\\r\\n]+)(?=, |$)",1);
  }
  static final Set<String> INPUT_FLAGS=new HashSet<>(Arrays.asList(
    "NO_INPUT_CHANNEL","NOT_VISIBLE","NOT_FOCUSABLE","NOT_TOUCHABLE","PREVENT_SPLITTING",
    "DUPLICATE_TOUCH_TO_WALLPAPER","IS_WALLPAPER","PAUSE_DISPATCHING","TRUSTED_OVERLAY",
    "WATCH_OUTSIDE_TOUCH","SLIPPERY","DISABLE_USER_ACTIVITY","DROP_INPUT","DROP_INPUT_IF_OBSCURED",
    "SPY","INTERCEPTS_STYLUS","CLONE","GLOBAL_STYLUS_BLOCKS_TOUCH","SENSITIVE_FOR_PRIVACY"));
  static Set<String> inputFlags(String value){
    Set<String> flags=new HashSet<>();if(value.equals("0x0"))return flags;
    for(String flag:value.split(" \\| ",-1))if(!INPUT_FLAGS.contains(flag)||!flags.add(flag))throw invalid();
    if(flags.isEmpty())throw invalid();return flags;
  }
  /** API35 current active windows only. Channels and the saved ANR dump are not windows. */
  public static Map<String,Object> parseInput(String raw,String window,int targetUid,int systemUiUid,int targetPid){
    if(targetPid<=1||parse(window,targetUid,systemUiUid)!=State.CLEAR)throw invalid();
    String expected=one(window,"^[ \\t]*mCurrentFocus=Window\\{([0-9a-f]+) u0 ("+Pattern.quote(TARGET)+"/[^\\s}]+)\\}[ \\t]*\\r?$",1)
      +" "+one(window,"^[ \\t]*mCurrentFocus=Window\\{([0-9a-f]+) u0 ("+Pattern.quote(TARGET)+"/[^\\s}]+)\\}[ \\t]*\\r?$",2);
    String current=currentInputState(raw);
    if(!one(current,"^  DispatchEnabled: ([^\\r\\n]*)\\r?$",1).equals("true")
        ||!one(current,"^  DispatchFrozen: ([^\\r\\n]*)\\r?$",1).equals("false")
        ||!one(current,"^  InputFilterEnabled: ([^\\r\\n]*)\\r?$",1).equals("false")
        ||!one(current,"^  FocusedDisplayId: ([^\\r\\n]*)\\r?$",1).equals("0"))throw invalid();
    String focused=inputBlock(current,"  FocusedWindows:");int focusCount=0;
    Set<String> focusDisplays=new HashSet<>();
    for(String line:focused.split("\\r?\\n"))if(!line.trim().isEmpty()){
      Matcher f=Pattern.compile("    displayId=(0|[1-9][0-9]*), name='([^'\\r\\n]+)'").matcher(line);
      if(!f.matches()||!focusDisplays.add(f.group(1)))throw invalid();
      if(f.group(1).equals("0")){if(!f.group(2).equals(expected))throw invalid();focusCount++;}
    }
    if(focusCount!=1)throw invalid();
    Matcher displays=Pattern.compile("^  Display: (0|[1-9][0-9]*)[ \\t]*\\r?$",Pattern.MULTILINE).matcher(current);
    Set<String> displayIds=new HashSet<>();while(displays.find())if(!displayIds.add(displays.group(1)))throw invalid();
    Matcher displayHeaders=Pattern.compile("^  Display:[^\\r\\n]*$",Pattern.MULTILINE).matcher(current);
    int displayCount=0;while(displayHeaders.find())displayCount++;if(displayCount!=displayIds.size())throw invalid();
    if(!displayIds.contains("0"))throw invalid();
    String display=inputBlock(current,"  Display: 0");
    one(display,"^    logicalSize=([1-9][0-9]*)x[1-9][0-9]*[ \\t]*\\r?$",1);
    one(display,"^    Windows:[^\\r\\n]*$",0);
    Matcher windows=Pattern.compile("^    Windows:[ \\t]*\\r?$",Pattern.MULTILINE).matcher(display);
    if(!windows.find())throw invalid();int from=windows.end();if(windows.find())throw invalid();
    String active=display.substring(from);
    Matcher row=Pattern.compile("^      ([0-9]+): (name=[^\\r\\n]+)\\r?$",Pattern.MULTILINE).matcher(active);
    Matcher any=Pattern.compile("^      [^ \\t\\r\\n].*$",Pattern.MULTILINE).matcher(active);
    int headers=0;while(any.find())headers++;
    int count=0,targets=0,shades=0;boolean shade=false;String targetConfig=null,shadeConfig=null;
    while(row.find()){
      if(!row.group(1).equals(Integer.toString(count++)))throw invalid();
      String value=row.group(2),name=inputField(value,"name");
      if(!inputField(value,"displayId").equals("0"))throw invalid();
      Set<String> flags=inputFlags(inputField(value,"inputConfig"));
      if(name.equals(expected)){
        if(++targets!=1||!inputField(value,"ownerPid").equals(Integer.toString(targetPid))
            ||!inputField(value,"ownerUid").equals(Integer.toString(targetUid)))throw invalid();
        for(String blocked:Arrays.asList("NO_INPUT_CHANNEL","NOT_VISIBLE","NOT_FOCUSABLE","NOT_TOUCHABLE",
            "IS_WALLPAPER","PAUSE_DISPATCHING","DROP_INPUT","DROP_INPUT_IF_OBSCURED","SPY","GLOBAL_STYLUS_BLOCKS_TOUCH"))
          if(flags.contains(blocked))throw invalid();
        String alpha=inputField(value,"alpha");
        if(!alpha.matches("(?:0(?:\\.[0-9]+)?|1(?:\\.0+)?)")||Double.parseDouble(alpha)<=0)throw invalid();
        // Presence, not a coordinate transform or a claim that a later event was delivered.
        String region=one(value,", touchableRegion=([^\\r\\n]+?), ownerPid=",1);
        if(!region.matches("(?:\\[-?[0-9]+,-?[0-9]+\\]\\[-?[0-9]+,-?[0-9]+\\])(?:\\|\\[-?[0-9]+,-?[0-9]+\\]\\[-?[0-9]+,-?[0-9]+\\])*"))throw invalid();
        targetConfig=inputField(value,"inputConfig");
      }else if(name.contains("NotificationShade")){
        if(!name.matches("[0-9a-f]+ NotificationShade")||++shades!=1
            ||!inputField(value,"ownerUid").equals(Integer.toString(systemUiUid))
            ||!inputField(value,"ownerPid").matches("[1-9][0-9]*"))throw invalid();
        shadeConfig=inputField(value,"inputConfig");
        // DROP_INPUT and NO_INPUT_CHANNEL do not make an intercepting shade safe.
        shade=!flags.contains("NOT_VISIBLE")&&!flags.contains("NOT_TOUCHABLE");
      }
    }
    if(count==0||count!=headers||targets!=1)throw invalid();
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("state",shade?State.SHADE_VISIBLE.name():State.CLEAR.name());result.put("displayId",0);
    result.put("focusedWindow",expected);result.put("targetPid",targetPid);result.put("targetUid",targetUid);
    result.put("targetInputConfig",targetConfig);result.put("targetVisible",true);result.put("targetTouchable",true);
    result.put("activeWindowCount",count);result.put("shadePresent",shades==1);result.put("shadeBlocksTouch",shade);
    result.put("shadeInputConfig",shadeConfig);result.put("systemUiUid",systemUiUid);
    return result;
  }
  static String snapshotSha(String raw){
    try{
      byte[] hash=MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8));
      StringBuilder out=new StringBuilder();for(byte value:hash)out.append(String.format("%02x",value&255));return out.toString();
    }catch(Exception failure){throw new IllegalStateException("snapshot-hash-unavailable");}
  }
  /** Current shell path: the original WM wait and a separately observed input window must agree. */
  public static Result awaitInput(Clock clock,Probe probe,long expires,int duration,int targetUid,int systemUiUid,int targetPid){
    Result result=new Result();long started=clock.now();
    try{
      if(targetPid<=1){result.reason="invalid-observation";return result;}
      if(duration<=0||expires<duration)return result;
      long latest=expires-duration;
      while(result.observations<MAX_OBSERVATIONS){
        if(clock.now()>=latest)return result;
        try{probe.verifyIdentity();}catch(Exception failure){result.reason="identity-changed";return result;}
        result.observations++;String window;long windowStarted=clock.now();
        try{window=probe.window(latest);}catch(Exception failure){result.reason="observation-failed";return result;}
        long windowCompleted=clock.now();State state;
        try{state=parse(window,targetUid,systemUiUid);}catch(IllegalArgumentException failure){result.reason="invalid-observation";return result;}
        if(state==State.SHADE_VISIBLE)result.shadeObserved=true;
        try{probe.verifyIdentity();}catch(Exception failure){result.reason="identity-changed";return result;}
        if(clock.now()>=latest)return result;
        if(state==State.CLEAR){
          Map<String,Object> observation=new LinkedHashMap<>();
          observation.put("windowStartedUptimeMs",windowStarted);observation.put("windowCompletedUptimeMs",windowCompleted);
          observation.put("windowSha256",snapshotSha(window));observation.put("windowObservation",result.observations);
          observation.put("startedUptimeMs",clock.now());observation.put("latestUptimeMs",latest);
          observation.put("state","observation-failed");result.inputObservations.add(observation);
          String input;
          try{input=probe.input(latest);}catch(Exception failure){observation.put("completedUptimeMs",clock.now());result.reason="observation-failed";return result;}
          observation.put("completedUptimeMs",clock.now());
          if(input==null){observation.put("state","invalid-observation");result.reason="invalid-observation";return result;}
          observation.put("sha256",snapshotSha(input));
          observation.put("bytes",input.getBytes(StandardCharsets.UTF_8).length);
          try{observation.putAll(parseInput(input,window,targetUid,systemUiUid,targetPid));}
          catch(IllegalArgumentException failure){observation.put("state","invalid-observation");result.reason="invalid-observation";return result;}
          try{probe.verifyIdentity();}catch(Exception failure){result.reason="identity-changed";return result;}
          if(clock.now()>=latest)return result;
          if(observation.get("state").equals(State.CLEAR.name())){result.passed=true;result.reason="clear";return result;}
          result.inputShadeObserved=true;
        }
        long remaining=latest-clock.now();if(remaining<=0)return result;
        clock.sleep(Math.min(INTERVAL_MS,remaining));
      }
      result.reason="observation-limit";return result;
    }finally{result.elapsedMs=Math.max(0,clock.now()-started);}
  }
  static final class Capture extends Thread {
    final InputStream input;final int maximum;final ByteArrayOutputStream output=new ByteArrayOutputStream();volatile boolean failed;
    Capture(InputStream value,int limit){input=value;maximum=limit;setDaemon(true);}
    public void run(){try{byte[] bytes=new byte[16384];int count;while((count=input.read(bytes))!=-1){if(output.size()+count>maximum){failed=true;return;}output.write(bytes,0,count);}}catch(Exception failure){failed=true;}}
  }
  /** Bounded stdout/stderr drain and child lifetime; no raw dump is retained. */
  public static String capture(Process child,Clock clock,long latest)throws Exception{
    Capture stdout=new Capture(child.getInputStream(),MAX_BYTES),stderr=new Capture(child.getErrorStream(),65536);
    stdout.start();stderr.start();
    try{
      long remaining=latest-clock.now();if(remaining<=0||remaining>20000||!child.waitFor(remaining,TimeUnit.MILLISECONDS))throw new IllegalStateException("observation-failed");
      remaining=latest-clock.now();if(remaining<=0)throw new IllegalStateException("observation-failed");stdout.join(remaining);
      remaining=latest-clock.now();if(remaining<=0)throw new IllegalStateException("observation-failed");stderr.join(remaining);
      if(stdout.isAlive()||stderr.isAlive()||stdout.failed||stderr.failed||child.exitValue()!=0||stderr.output.size()!=0||clock.now()>=latest)throw new IllegalStateException("observation-failed");
      return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(stdout.output.toByteArray())).toString();
    }finally{
      child.destroy();if(child.isAlive())child.destroyForcibly();
      try{child.getInputStream().close();}catch(Exception ignored){}try{child.getErrorStream().close();}catch(Exception ignored){}try{child.getOutputStream().close();}catch(Exception ignored){}
      stdout.interrupt();stderr.interrupt();stdout.join(50);stderr.join(50);
      if(!child.waitFor(100,TimeUnit.MILLISECONDS))throw new IllegalStateException("observation-cleanup-failed");
    }
  }
  private NativePreEmitReadiness(){}
}
