package local.pocketchat.inputdriver;

import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.SystemClock;
import android.util.Base64;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
import java.io.*;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.regex.*;
import java.util.zip.ZipFile;
import org.json.JSONObject;

/** API35 emulator-only shell process. Never attaches instrumentation to the AUT. */
public final class NativeInputShell {
  static final String SELF="local.pocketchat.inputdriver", TARGET="local.pocketchat.test";
  static final String BACKEND="shell-input-manager-global-v1";
  final long created=SystemClock.uptimeMillis();
  JSONObject args,report=new JSONObject(); File directory,output;
  NativeGestureProtocol.Profile profile; NativeGestureProtocol.Trace observed;
  Object input,pm; Method injectMethod,packageInfoMethod,setDisplay;
  int deviceId,targetUid; long expires; String expectedPid;
  public static void main(String[] command){
    NativeInputShell driver=new NativeInputShell();
    boolean success=driver.run(command);System.exit(success?0:1);
  }
  boolean run(String[] command){
    boolean passed=false;long started=SystemClock.uptimeMillis();
    try{
      if(command.length!=1||command[0].length()>16384)throw new IllegalArgumentException("One bounded request required");
      args=new JSONObject(new String(Base64.decode(command[0],Base64.NO_WRAP),StandardCharsets.UTF_8));
      String nonce=required("nonce","[0-9a-f]{32}"),gesture=required("gesture","(?:baseline|current)-scroll|formal-collapse");
      profile=NativeGestureProtocol.profile(required("purpose","qualification|formal-collapse"));
      if(profile.name.equals("qualification")==gesture.equals("formal-collapse"))throw new IllegalArgumentException("Gesture/purpose mismatch");
      String name="pocketchat-input-"+nonce+"-"+gesture;
      directory=new File("/data/local/tmp/"+name);output=new File(directory,"receipt.json");
      if(!directory.isDirectory()||!directory.getCanonicalPath().equals(directory.getPath())||output.exists())throw new IllegalStateException("Fresh shell-owned receipt directory required");
      if(android.os.Process.myUid()!=2000||Build.VERSION.SDK_INT!=35||(!Build.HARDWARE.equals("ranchu")&&!Build.HARDWARE.equals("goldfish")))throw new IllegalStateException("API35 disposable emulator shell UID required");
      String ownPid=Integer.toString(android.os.Process.myPid());JSONObject owner=process(ownPid,2000,name);
      owner.put("nonce",nonce).put("gesture",gesture).put("executionUid",2000);
      write(new File(directory,"owner.json"),owner);
      System.out.println("NATIVE_INPUT_OWNER "+owner.toString());System.out.flush();
      report.put("schema",1).put("status","failed").put("nonce",nonce).put("gesture",gesture).put("purpose",profile.name)
        .put("createdUptimeMs",created).put("startedUptimeMs",started).put("packageName",SELF).put("targetPackage",TARGET)
        .put("executionBackend",BACKEND).put("executionUid",android.os.Process.myUid()).put("driverPid",android.os.Process.myPid())
        .put("driverStartTicks",owner.getString("startTicks")).put("displayId",0).put("tracePersistence","memory-until-terminal");
      write(output,report);
      expires=Long.parseLong(required("expires","[0-9]{1,16}"));expectedPid=required("targetPid","[1-9][0-9]*");
      String source=required("source","[0-9a-f]{40}"),tree=required("tree","[0-9a-f]{40}");
      String driverHash=required("driverApkSha256","[0-9a-f]{64}"),targetHash=required("targetApkSha256","[0-9a-f]{64}");
      pm=Class.forName("android.app.AppGlobals").getMethod("getPackageManager").invoke(null);
      packageInfoMethod=Class.forName("android.content.pm.IPackageManager").getMethod("getPackageInfo",String.class,long.class,int.class);
      PackageInfo own=info(SELF,PackageManager.GET_SIGNING_CERTIFICATES),before=info(TARGET,0);
      String ownPath=own.applicationInfo.sourceDir,targetPath=before.applicationInfo.sourceDir;
      if(!new File(ownPath).getCanonicalPath().equals(System.getenv("CLASSPATH")))throw new IllegalStateException("Loaded shell classpath differs from installed driver APK");
      String actualDriverHash=NativeInputInstrumentation.sha(ownPath);
      if(!actualDriverHash.equals(driverHash))throw new IllegalStateException("Installed driver bytes differ");
      android.content.pm.Signature[] signers=own.signingInfo.getApkContentsSigners();
      if(signers.length!=1||own.signingInfo.hasMultipleSigners()||own.signingInfo.getSigningCertificateHistory().length!=1)throw new IllegalStateException("Fresh single device signer required");
      report.put("signerCertificateSha256",NativeInputInstrumentation.hex(MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray())));
      JSONObject identity=asset(ownPath,"assets/native-input-driver-build.json");
      if(!source.equals(identity.getString("sourceCommit"))||!tree.equals(identity.getString("sourceTree"))
        ||!SELF.equals(identity.getString("instrumentationTargetPackage"))||!BACKEND.equals(identity.getString("executionBackend"))
        ||!NativeInputShell.class.getName().equals(identity.getString("entryPoint"))||identity.getInt("executionUid")!=2000||!identity.getBoolean("inputTargetUidEnforced"))throw new IllegalStateException("Compiled driver source/backend mismatch");
      targetUid=before.applicationInfo.uid;if(targetUid<10000||targetUid>=100000)throw new IllegalStateException("Controlled user-zero AUT required");
      long targetBytes=new File(targetPath).length(),targetModified=new File(targetPath).lastModified();
      if(!targetPath.equals(required("targetApkPath","/data/app/[A-Za-z0-9/._~+=-]+/base\\.apk"))||targetBytes!=Long.parseLong(required("targetApkBytes","[1-9][0-9]*")))throw new IllegalStateException("Target changed since preflight byte read");
      JSONObject target=asset(targetPath,"assets/pocketchat-integration-build.json");
      if(!source.equals(target.getString("sourceCommit"))||!tree.equals(target.getString("sourceTree"))||target.getBoolean("dirtySource"))throw new IllegalStateException("Measured source mismatch");
      report.put("buildIdentity",identity).put("sourceCommit",source).put("sourceTree",tree).put("expiresUptimeMs",expires)
        .put("driverApkSha256",actualDriverHash).put("targetApkSha256",targetHash).put("targetBuildIdentity",target)
        .put("targetByteProofSha256",required("targetByteProofSha256","[0-9a-f]{64}")).put("targetApkHashSource","preflight-installed-byte-proof")
        .put("targetApkPathBefore",targetPath).put("targetApkBytesBefore",targetBytes).put("targetLastModifiedBefore",targetModified)
        .put("targetLastUpdateBefore",before.lastUpdateTime).put("inputTargetUid",targetUid).put("targetUidBefore",targetUid);
      JSONObject targetProcess=process(expectedPid,targetUid,TARGET);
      report.put("targetPidBefore",expectedPid).put("targetStartTicksBefore",targetProcess.getString("startTicks"));
      report.put("focusBefore",focus());
      report.put("connectStartUptimeMs",SystemClock.uptimeMillis());
      Class<?> manager=Class.forName("android.hardware.input.InputManagerGlobal");
      input=manager.getMethod("getInstance").invoke(null);
      injectMethod=manager.getMethod("injectInputEvent",InputEvent.class,int.class,int.class);
      setDisplay=InputEvent.class.getMethod("setDisplayId",int.class);
      for(int id:InputDevice.getDeviceIds()){InputDevice d=InputDevice.getDevice(id);if(d!=null&&d.supportsSource(InputDevice.SOURCE_TOUCHSCREEN)){deviceId=id;break;}}
      report.put("connectEndUptimeMs",SystemClock.uptimeMillis());
      float x=Float.parseFloat(required("x","[0-9]+")),from=Float.parseFloat(required("startY","[0-9]+")),to=Float.parseFloat(required("endY","[0-9]+"));
      if(SystemClock.uptimeMillis()+profile.duration>expires)throw new IllegalStateException("Original deadline expired during setup");
      long ready=SystemClock.uptimeMillis();report.put("readyUptimeMs",ready).put("startupMs",ready-started);
      // Preparation is outside T0; the original AUT/action deadline never moves.
      write(output,report);
      NativeGestureProtocol.Clock clock=new NativeGestureProtocol.Clock(){public long now(){return SystemClock.uptimeMillis();}public void until(long time){long wait=time-now();if(wait>0)SystemClock.sleep(wait);}};
      NativeGestureProtocol.Trace trace=NativeGestureProtocol.run(clock,this::inject,t->observed=t,profile,expires,x,from,to);
      report.put("trace",NativeInputInstrumentation.json(trace));
      JSONObject afterProcess=process(expectedPid,targetUid,TARGET);PackageInfo after=info(TARGET,0);
      report.put("targetPidAfter",expectedPid).put("targetStartTicksAfter",afterProcess.getString("startTicks"))
        .put("targetUidAfter",after.applicationInfo.uid).put("focusAfter",focus());
      if(!trace.passed())throw new IllegalStateException(trace.error);
      if(!targetProcess.getString("startTicks").equals(afterProcess.getString("startTicks")))throw new IllegalStateException("AUT process generation changed");
      String afterPath=after.applicationInfo.sourceDir;
      report.put("targetApkPathAfter",afterPath).put("targetApkBytesAfter",new File(afterPath).length())
        .put("targetLastModifiedAfter",new File(afterPath).lastModified()).put("targetLastUpdateAfter",after.lastUpdateTime);
      if(targetUid!=after.applicationInfo.uid||!targetPath.equals(afterPath)||targetBytes!=new File(afterPath).length()
        ||targetModified!=new File(afterPath).lastModified()||before.lastUpdateTime!=after.lastUpdateTime||!driverHash.equals(NativeInputInstrumentation.sha(ownPath)))throw new IllegalStateException("APK identity fence changed");
      JSONObject afterBuild=asset(afterPath,"assets/pocketchat-integration-build.json");
      if(!target.toString().equals(afterBuild.toString()))throw new IllegalStateException("Target source changed");
      report.put("targetBuildIdentityAfter",afterBuild).put("status","passed");passed=true;
    }catch(Throwable failure){try{report.put("status","failed").put("error",failure.toString());}catch(Exception ignored){}}
    finally{
      try{if(observed!=null)report.put("trace",NativeInputInstrumentation.json(observed));report.put("finishedUptimeMs",SystemClock.uptimeMillis());if(output!=null)write(output,report);}
      catch(Throwable failure){passed=false;System.err.println("Driver receipt unavailable: "+failure);}
    }
    return passed;
  }
  NativeGestureProtocol.Attempt inject(int action,long down,long planned,long deadline,float x,float y,boolean cleanup){
    NativeGestureProtocol.Attempt row=new NativeGestureProtocol.Attempt();row.action=action;row.downTime=down;row.planned=planned;row.x=x;row.y=y;row.cleanup=cleanup;
    row.eventTime=SystemClock.uptimeMillis();
    MotionEvent.PointerProperties p=new MotionEvent.PointerProperties();p.id=0;p.toolType=MotionEvent.TOOL_TYPE_FINGER;
    MotionEvent.PointerCoords c=new MotionEvent.PointerCoords();c.x=x;c.y=y;c.size=1;c.pressure=(action==0||action==2)?1:0;
    MotionEvent motion=MotionEvent.obtain(down,row.eventTime,action,1,new MotionEvent.PointerProperties[]{p},new MotionEvent.PointerCoords[]{c},0,0,1,1,deviceId,0,InputDevice.SOURCE_TOUCHSCREEN,0);
    try{
      setDisplay.invoke(motion,0);row.callStart=SystemClock.uptimeMillis();
      if(!cleanup&&(row.callStart>planned+profile.maxLate||row.callStart>deadline))row.error="Injection call missed fixed slot";
      else{row.injected=true;row.sync=action==1;row.accepted=(Boolean)injectMethod.invoke(input,motion,row.sync?2:0,targetUid);}
    }catch(Throwable failure){row.error=failure.toString();}
    finally{row.callEnd=SystemClock.uptimeMillis();motion.recycle();}
    return row;
  }
  PackageInfo info(String name,long flags)throws Exception{PackageInfo value=(PackageInfo)packageInfoMethod.invoke(pm,name,flags,0);if(value==null||value.applicationInfo==null)throw new IllegalStateException("Missing actual package "+name);return value;}
  static JSONObject process(String pid,int uid,String name)throws Exception{
    String first=readFile("/proc/"+pid+"/stat"),status=readFile("/proc/"+pid+"/status"),command=readFile("/proc/"+pid+"/cmdline"),last=readFile("/proc/"+pid+"/stat");
    String a=first.substring(first.lastIndexOf(')')+2).split(" ")[19],b=last.substring(last.lastIndexOf(')')+2).split(" ")[19];
    Matcher u=Pattern.compile("(?m)^Uid:\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s*$").matcher(status);
    if(!a.matches("[1-9][0-9]*")||!a.equals(b)||!u.find()||Integer.parseInt(u.group(1))!=uid||Integer.parseInt(u.group(2))!=uid||Integer.parseInt(u.group(3))!=uid||Integer.parseInt(u.group(4))!=uid
      ||!command.split("\\x00",-1)[0].equals(name))throw new IllegalStateException("Actual process identity changed");
    return new JSONObject().put("pid",Integer.parseInt(pid)).put("startTicks",a).put("uid",uid).put("processName",name);
  }
  static JSONObject focus()throws Exception{
    java.lang.Process child=new ProcessBuilder("/system/bin/dumpsys","window").start();String raw=bounded(child.getInputStream());
    if(child.waitFor()!=0)throw new IOException("Window observation failed");
    return parseFocus(raw);
  }
  static JSONObject parseFocus(String raw)throws Exception{
    Matcher display=Pattern.compile("(?m)^\\s*mTopFocusedDisplayId=([0-9]+)\\s*$").matcher(raw);
    Matcher current=Pattern.compile("(?m)^\\s*mCurrentFocus=Window\\{[^\\n}]*\\s([^\\s}]+)\\}\\s*$").matcher(raw);
    if(!display.find()||!"0".equals(display.group(1))||!current.find())throw new IllegalStateException("AUT is not focused on the default display");
    String component=current.group(1),selected=current.group()+"\n"+display.group()+"\n";
    if(!component.startsWith(TARGET+"/"))throw new IllegalStateException("Another package is focused");
    if(display.find()||current.find())throw new IllegalStateException("Ambiguous foreground display/window");
    return new JSONObject().put("displayId",0).put("packageName",TARGET).put("component",component).put("raw",selected);
  }
  String required(String name,String pattern)throws Exception{String value=args.getString(name);if(!value.matches(pattern))throw new IllegalArgumentException("Invalid "+name);return value;}
  static JSONObject asset(String path,String name)throws Exception{try(ZipFile zip=new ZipFile(path)){return new JSONObject(bounded(zip.getInputStream(zip.getEntry(name))));}}
  static String readFile(String path)throws Exception{return bounded(new FileInputStream(path));}
  static String bounded(InputStream input)throws IOException{try(InputStream in=input;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[16384];int n;while((n=in.read(b))!=-1){if(out.size()+n>2097152)throw new IOException("Bounded observation exceeded");out.write(b,0,n);}return out.toString("UTF-8");}}
  static void write(File output,JSONObject value)throws Exception{File temp=new File(output.getPath()+".tmp");try(FileOutputStream out=new FileOutputStream(temp)){out.write(value.toString().getBytes(StandardCharsets.UTF_8));}if(!temp.renameTo(output))throw new IOException("Could not retain shell receipt");}
}
