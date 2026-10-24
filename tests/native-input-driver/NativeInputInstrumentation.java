package local.pocketchat.inputdriver;

import android.app.Instrumentation;
import android.app.UiAutomation;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.MotionEvent;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.zip.ZipFile;

/** Isolated self-targeting test process: it never instruments the measured app. */
public final class NativeInputInstrumentation extends Instrumentation {
  static final String SELF="local.pocketchat.inputdriver", TARGET="local.pocketchat.test";
  Bundle args; UiAutomation automation; JSONObject report=new JSONObject(); File output;
  long expires,created; String expectedPid; int deviceId; NativeGestureProtocol.Profile profile;
  @Override public void onCreate(Bundle arguments){super.onCreate(arguments);created=SystemClock.uptimeMillis();args=arguments;start();}
  @Override public void onStart(){
    long started=SystemClock.uptimeMillis(); Bundle result=new Bundle(); boolean passed=false;
    try{
      profile=NativeGestureProtocol.profile(required("purpose","qualification|formal-collapse"));
      String nonce=required("nonce","[0-9a-f]{32}"),gesture=required("gesture","(?:baseline|current)-scroll|formal-collapse");
      if((profile.name.equals("qualification"))==gesture.equals("formal-collapse"))throw new IllegalArgumentException("Gesture/purpose mismatch");
      File candidate=new File(getTargetContext().getFilesDir(),"native-input-"+nonce+"-"+gesture+".json");
      if(candidate.exists())throw new IllegalStateException("Invocation receipt already exists");
      output=candidate;
      report.put("schema",1).put("status","failed").put("nonce",nonce).put("gesture",gesture)
        .put("purpose",profile.name).put("createdUptimeMs",created).put("startedUptimeMs",started).put("packageName",SELF).put("targetPackage",TARGET);
      write();
      if(!SELF.equals(getTargetContext().getPackageName())||android.os.Build.VERSION.SDK_INT!=35)
        throw new IllegalStateException("Self-target API35 driver required");
      String hardware=android.os.Build.HARDWARE;
      if(!hardware.equals("ranchu")&&!hardware.equals("goldfish"))throw new IllegalStateException("Disposable emulator only");
      expires=Long.parseLong(required("expires","[0-9]{1,16}")); expectedPid=required("targetPid","[1-9][0-9]*");
      String source=required("source","[0-9a-f]{40}"),tree=required("tree","[0-9a-f]{40}");
      String driverHash=required("driverApkSha256","[0-9a-f]{64}"),targetHash=required("targetApkSha256","[0-9a-f]{64}");
      JSONObject identity=new JSONObject(read(getContext().getAssets().open("native-input-driver-build.json")));
      if(!source.equals(identity.getString("sourceCommit"))||!tree.equals(identity.getString("sourceTree"))
          ||!SELF.equals(identity.getString("instrumentationTargetPackage")))throw new IllegalStateException("Driver source mismatch");
      report.put("buildIdentity",identity).put("sourceCommit",source).put("sourceTree",tree).put("expiresUptimeMs",expires);
      android.content.pm.PackageInfo targetPackageBefore=getContext().getPackageManager().getPackageInfo(TARGET,0);
      String targetPath=targetPackageBefore.applicationInfo.sourceDir;
      long targetBytes=new File(targetPath).length(),targetModified=new File(targetPath).lastModified();
      String proof=required("targetByteProofSha256","[0-9a-f]{64}");
      if(!targetPath.equals(required("targetApkPath","/data/app/[A-Za-z0-9/._~+=-]+/base\\.apk"))
          ||targetBytes!=Long.parseLong(required("targetApkBytes","[1-9][0-9]*")))throw new IllegalStateException("Target path/size changed since preflight bytes");
      report.put("targetByteProofSha256",proof).put("targetApkHashSource","preflight-installed-byte-proof")
        .put("targetApkPathBefore",targetPath).put("targetApkBytesBefore",targetBytes)
        .put("targetLastModifiedBefore",targetModified).put("targetLastUpdateBefore",targetPackageBefore.lastUpdateTime);
      String ownPath=getContext().getApplicationInfo().sourceDir;
      String actualDriverHash=sha(ownPath);
      if(!driverHash.equals(actualDriverHash))throw new IllegalStateException("Installed APK mismatch");
      try(ZipFile zip=new ZipFile(targetPath)){
        JSONObject target=new JSONObject(read(zip.getInputStream(zip.getEntry("assets/pocketchat-integration-build.json"))));
        if(!source.equals(target.getString("sourceCommit"))||!tree.equals(target.getString("sourceTree"))||target.getBoolean("dirtySource"))
          throw new IllegalStateException("Measured APK source mismatch");
        report.put("targetBuildIdentity",target);
      }
      android.content.pm.Signature[] signers=getContext().getPackageManager().getPackageInfo(SELF,android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES).signingInfo.getApkContentsSigners();
      if(signers.length!=1)throw new IllegalStateException("Exactly one driver signer required");
      report.put("signerCertificateSha256",hex(MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray())));
      report.put("driverApkSha256",actualDriverHash).put("targetApkSha256",targetHash);
      if(SystemClock.uptimeMillis()+profile.duration>expires)throw new IllegalStateException("Expired before automation connect");
      report.put("connectStartUptimeMs",SystemClock.uptimeMillis());
      automation=getUiAutomation(UiAutomation.FLAG_DONT_USE_ACCESSIBILITY);
      report.put("connectEndUptimeMs",SystemClock.uptimeMillis());
      if(automation==null)throw new IllegalStateException("Automation connection unavailable");
      String pid=targetPid();report.put("targetPidBefore",pid);
      if(!expectedPid.equals(pid))throw new IllegalStateException("Measured process changed before injection");
      long ready=SystemClock.uptimeMillis();report.put("readyUptimeMs",ready).put("startupMs",ready-started);
      write();
      float x=Float.parseFloat(required("x","[0-9]+")),from=Float.parseFloat(required("startY","[0-9]+")),to=Float.parseFloat(required("endY","[0-9]+"));
      for(int id:InputDevice.getDeviceIds()){InputDevice d=InputDevice.getDevice(id);if(d!=null&&d.supportsSource(InputDevice.SOURCE_TOUCHSCREEN)){deviceId=id;break;}}
      NativeGestureProtocol.Clock clock=new NativeGestureProtocol.Clock(){public long now(){return SystemClock.uptimeMillis();} public void until(long time){long wait=time-now();if(wait>0)SystemClock.sleep(wait);}};
      NativeGestureProtocol.Trace trace=NativeGestureProtocol.run(clock,this::inject,t->{try{report.put("trace",json(t));write();}catch(Exception failure){throw new IllegalStateException(failure);}},profile,expires,x,from,to);
      report.put("trace",json(trace));
      String after=targetPid();report.put("targetPidAfter",after);
      if(!trace.passed())throw new IllegalStateException(trace.error);
      if(!expectedPid.equals(after))throw new IllegalStateException("Measured process changed during injection");
      android.content.pm.PackageInfo targetPackageAfter=getContext().getPackageManager().getPackageInfo(TARGET,0);
      String targetPathAfter=targetPackageAfter.applicationInfo.sourceDir;
      report.put("targetApkPathAfter",targetPathAfter).put("targetApkBytesAfter",new File(targetPathAfter).length())
        .put("targetLastModifiedAfter",new File(targetPathAfter).lastModified()).put("targetLastUpdateAfter",targetPackageAfter.lastUpdateTime);
      if(!targetPath.equals(targetPathAfter)||targetBytes!=new File(targetPathAfter).length()
          ||targetModified!=new File(targetPathAfter).lastModified()||targetPackageBefore.lastUpdateTime!=targetPackageAfter.lastUpdateTime
          ||!driverHash.equals(sha(ownPath)))throw new IllegalStateException("APK identity fence changed during injection");
      try(ZipFile zip=new ZipFile(targetPathAfter)){
        JSONObject targetAfter=new JSONObject(read(zip.getInputStream(zip.getEntry("assets/pocketchat-integration-build.json"))));
        if(!targetAfter.toString().equals(report.getJSONObject("targetBuildIdentity").toString()))throw new IllegalStateException("Target source changed after injection");
        report.put("targetBuildIdentityAfter",targetAfter);
      }
      report.put("status","passed");passed=true;
    }catch(Throwable failure){try{report.put("status","failed").put("error",failure.toString());}catch(Exception ignored){}}
    finally{
      try{report.put("finishedUptimeMs",SystemClock.uptimeMillis());write();result.putString("receipt",output==null?"":output.getName());}
      catch(Exception failure){passed=false;result.putString("error",failure.toString());}
      // Instrumentation.finish disconnects only this driver's UiAutomation.
      finish(passed?-1:0,result);
    }
  }
  NativeGestureProtocol.Attempt inject(int action,long down,long planned,long deadline,float x,float y,boolean cleanup){
    NativeGestureProtocol.Attempt row=new NativeGestureProtocol.Attempt();row.action=action;row.downTime=down;row.planned=planned;row.x=x;row.y=y;row.cleanup=cleanup;
    row.eventTime=SystemClock.uptimeMillis();
    MotionEvent.PointerProperties p=new MotionEvent.PointerProperties();p.id=0;p.toolType=MotionEvent.TOOL_TYPE_FINGER;
    MotionEvent.PointerCoords c=new MotionEvent.PointerCoords();c.x=x;c.y=y;c.size=1;c.pressure=(action==0||action==2)?1:0;
    MotionEvent motion=MotionEvent.obtain(down,row.eventTime,action,1,new MotionEvent.PointerProperties[]{p},new MotionEvent.PointerCoords[]{c},0,0,1,1,deviceId,0,InputDevice.SOURCE_TOUCHSCREEN,0);
    try{
      row.callStart=SystemClock.uptimeMillis();
      if(!cleanup&&(row.callStart>planned+profile.maxLate||row.callStart>deadline))row.error="Injection call missed fixed slot";
      else{row.injected=true;row.sync=action==1;row.accepted=automation.injectInputEvent(motion,row.sync);}
    }catch(Throwable failure){row.error=failure.toString();}
    finally{row.callEnd=SystemClock.uptimeMillis();motion.recycle();}
    return row;
  }
  String targetPid()throws Exception{try(ParcelFileDescriptor fd=automation.executeShellCommand("pidof "+TARGET)){return read(new ParcelFileDescriptor.AutoCloseInputStream(fd)).trim();}}
  String required(String name,String pattern){String value=args.getString(name,"");if(!value.matches(pattern))throw new IllegalArgumentException("Invalid "+name);return value;}
  static String read(InputStream stream)throws IOException{try(InputStream in=stream;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[16384];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toString("UTF-8");}}
  static String sha(String path)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(path)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}return hex(d.digest());}
  static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format("%02x",b&255));return s.toString();}
  void write()throws Exception{if(output==null)return;File temp=new File(output.getPath()+".tmp");try(FileOutputStream stream=new FileOutputStream(temp)){stream.write(report.toString().getBytes(StandardCharsets.UTF_8));}if(!temp.renameTo(output))throw new IOException("Could not retain driver receipt");}
  static JSONObject json(NativeGestureProtocol.Attempt row)throws Exception{return new JSONObject().put("action",row.action).put("downTime",row.downTime).put("plannedUptimeMs",row.planned).put("eventTime",row.eventTime).put("callStartUptimeMs",row.callStart).put("callEndUptimeMs",row.callEnd).put("x",row.x).put("y",row.y).put("injected",row.injected).put("accepted",row.accepted).put("cleanup",row.cleanup).put("sync",row.sync).put("error",row.error);}
  static JSONObject json(NativeGestureProtocol.Trace trace)throws Exception{JSONArray rows=new JSONArray();for(NativeGestureProtocol.Attempt row:trace.events)rows.put(json(row));return new JSONObject().put("startUptimeMs",trace.start).put("expiresUptimeMs",trace.expires).put("durationMs",trace.profile.duration).put("moveCount",19).put("intervalMs",trace.profile.interval).put("maxLateMs",trace.profile.maxLate).put("upSynchronous",true).put("events",rows).put("cleanup",trace.cleanup==null?JSONObject.NULL:json(trace.cleanup)).put("error",trace.error);}
}
