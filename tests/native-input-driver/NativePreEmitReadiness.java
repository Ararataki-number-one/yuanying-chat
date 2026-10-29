package local.pocketchat.inputdriver;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
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
  }
  public static final class Result {
    public boolean passed,shadeObserved;
    public final boolean preEmitOnly=true;
    public int observations;
    public long elapsedMs;
    public String reason="deadline";
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
