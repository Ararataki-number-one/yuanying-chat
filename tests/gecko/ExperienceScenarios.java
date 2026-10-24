package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Test-only pressure workloads. Never used by the formal package or release gates. */
final class ExperienceScenarios {
  static final String PROGRESS="experience-progress";
  final ExperienceBenchmarkActivity a;
  final JSONObject manifest;
  final String manifestSha;
  boolean recoverySettled=true,backgroundArmed;
  JSONObject start;
  String phase="";
  int nativeStart,choreoStart,lifecycleChanges;
  ExperienceSaveSampling sampling;
  boolean diagnosticFinished;
  ExperienceScenarios(ExperienceBenchmarkActivity activity,Intent intent)throws Exception{
    a=activity;manifest=read(intent);manifestSha=hash(intent.getStringExtra("scenarioManifest"));
    if(manifest.has("downloadHistory")){
      recoverySettled=false;
      // Observe the normal recovery queue's completion; do not bypass it or its save.
      DownloadTasks.recovery.execute(()->a.handler.post(()->recoverySettled=true));
    }
  }
  static JSONObject read(Intent intent)throws Exception{
    String raw=intent.getStringExtra("scenarioManifest");
    if(raw==null||raw.length()>8192||!hash(raw).equals(intent.getStringExtra("scenarioSha256")))throw new IllegalArgumentException("Frozen scenario manifest/hash required");
    JSONObject m=new JSONObject(raw);String name=m.getString("name");
    if(m.getInt("schema")!=1||m.getInt("coreFlowVersion")!=1||!name.matches("core|idle-120|download-history-(0|1000|3000)"))throw new IllegalArgumentException("Unsupported scenario");
    if(name.startsWith("download-history-")){
      JSONObject d=m.getJSONObject("downloadHistory");int n=Integer.parseInt(name.substring("download-history-".length()));
      if(d.getInt("savedRows")!=n||d.getInt("progressRows")!=1||d.getInt("saveSteps")!=8||d.getInt("stepBytes")!=65536||d.getInt("intervalMs")!=2000||d.getLong("baseTimestampMs")!=1700000000000L||d.getInt("recordContractVersion")!=1||!"657870657269656e63652d666978747572650a".equals(d.getString("savedFileBytesHex")))throw new IllegalArgumentException("Download workload differs");
    }else if(m.has("downloadHistory"))throw new IllegalArgumentException("Unexpected history inputs");
    if("idle-120".equals(name)){JSONObject idle=m.getJSONObject("idle");if(idle.getLong("foregroundMs")!=120000||idle.getLong("backgroundMs")!=120000)throw new IllegalArgumentException("Idle duration differs");}
    else if(m.has("idle"))throw new IllegalArgumentException("Unexpected idle inputs");
    return m;
  }
  static String hash(String text)throws Exception{byte[] value=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte b:value)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}
  static JSONObject clocks(){return J.obj("elapsedRealtimeMs",SystemClock.elapsedRealtime(),"uptimeMs",SystemClock.uptimeMillis());}
  static JSONObject seed(Context c,Intent intent)throws Exception{
    JSONObject seedStart=clocks();JSONObject m=read(intent);JSONObject result=J.obj("manifest",m,"manifestSha256",hash(intent.getStringExtra("scenarioManifest")),"timed",false);
    if(!m.has("downloadHistory")){result.put("seedStart",seedStart);result.put("seedEnd",clocks());return result;}
    if(!"local.pocketchat.test".equals(c.getPackageName())||Profiles.slot(c)!=0)throw new SecurityException("Synthetic slot only");
    JSONObject d=m.getJSONObject("downloadHistory");int count=d.getInt("savedRows");long time=d.getLong("baseTimestampMs");
    File folder=new File(c.getFilesDir(),"experience-history");if(!folder.isDirectory()&&!folder.mkdirs())throw new IOException("Fixture directory unavailable");
    JSONArray rows=new JSONArray();rows.put(J.obj("slot",0,"id",PROGRESS,"name","Controlled paused record","mime","application/octet-stream","uri","","location","","state","paused","reason","Synthetic persistence workload","received",0,"total",1048576,"time",time+count+1,"source","","key","","conversation",ExperienceBenchmarkActivity.TARGET));
    byte[] bytes="experience-fixture\n".getBytes(StandardCharsets.UTF_8);
    for(int i=0;i<count;i++){
      File file=new File(folder,String.format(java.util.Locale.ROOT,"saved-%04d.txt",i));try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
      rows.put(J.obj("slot",0,"id","experience-saved-"+i,"name",file.getName(),"mime","text/plain","uri",android.net.Uri.fromFile(file).toString(),"state","saved","location","Integration private fixture","time",time+i,"received",bytes.length,"total",bytes.length));
    }
    // Untimed fixture provisioning writes the current real schema. No fake SQLite,
    // migration, HTTP transfer or user file is substituted inside a measured call.
    DownloadLibrary library=DownloadLibrary.get(c);SQLiteDatabase db=library.getWritableDatabase();db.beginTransaction();
    try{
      db.delete("files",null,null);db.delete("tasks",null,null);db.delete("deleted_files",null,null);
      for(int i=0;i<rows.length();i++){
        JSONObject row=rows.getJSONObject(i);ContentValues task=new ContentValues();task.put("slot",0);task.put("id",row.getString("id"));task.put("row",row.toString());task.put("time",row.getLong("time"));db.insertOrThrow("tasks",null,task);
        if(i>0){JSONObject safe=J.obj("slot",0,"id",row.getString("id"),"name",row.getString("name"),"mime","text/plain","uri",row.getString("uri"),"state","saved","location",row.getString("location"),"time",row.getLong("time"));ContentValues file=new ContentValues();file.put("slot",0);file.put("uri",row.getString("uri"));file.put("row",safe.toString());file.put("time",row.getLong("time"));db.insertOrThrow("files",null,file);}
      }
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    if(!c.getSharedPreferences("download-tasks",0).edit().putString("rows",rows.toString()).commit()||!c.getSharedPreferences("chat",0).edit().putString("downloadHistory","{}").commit())throw new IOException("Fixture prefs commit failed");
    library.list();library.tasks(); // Finish normal legacy migration outside the measured launch.
    return DownloadTasksJson.with(result,"seedStart",seedStart,"seedEnd",clocks(),"seedUsesProductionSave",false,"seedUsesProductionMigration",true,"savedRows",count,"taskRows",rows.length(),"rowsSha256",hash(rows.toString()),"savedFileContentSha256",hash("experience-fixture\n"),"scope","Actual private files and current Android SQLite/SharedPreferences schema, prepared before the measured process-cold launch; not a measured download.");
  }
  boolean ready(){return recoverySettled;}
  boolean downloadsVisible(){
    if(!manifest.has("downloadHistory"))return true;
    int expected=manifest.optJSONObject("downloadHistory").optInt("savedRows")+1;
    return a.hub.downloadController!=null&&a.hub.downloadController.filter==0&&a.hub.downloadController.views.size()==expected&&a.hub.downloadController.list.getChildCount()==expected;
  }
  boolean command(String command,String name)throws Exception{
    if("diagnostic-stop-sampling".equals(command)){
      if(!a.samplingDiagnostic)throw new IllegalStateException("Diagnostic stop is not a formal workload command");
      abortSampling();return true;
    }
    if("diagnostic-history-sampling".equals(command)){
      if(!a.samplingDiagnostic||!a.benchmarkReady||!a.active||!a.armedName.isEmpty()||!a.measurements.isEmpty()||!phase.isEmpty()||sampling!=null||!manifest.has("downloadHistory"))throw new IllegalStateException("Separate untimed history diagnostic required");
      verifyHistory(0);sampling=new ExperienceSaveSampling(a,a.nonce);sampling.start();begin("diagnostic-history-save-sampling");
      a.handler.postDelayed(()->{if(!diagnosticFinished){abortSampling();a.fail(new IllegalStateException("Sampling diagnostic deadline exceeded"));}},90000);
      a.handler.postDelayed(()->saveStep(1),2000);return true;
    }
    if(a.samplingDiagnostic)throw new IllegalStateException("Diagnostic invocation cannot enter the formal workload");
    if(!command.startsWith("scenario-"))return false;
    if(!a.benchmarkReady||!a.armedName.isEmpty()||a.measurements.size()!=13)throw new IllegalStateException("Complete unchanged core flow first");
    if("scenario-history".equals(command)){
      if(!manifest.has("downloadHistory")||!a.active)throw new IllegalStateException("History scenario not configured/foreground");
      verifyHistory(0);begin("history-save");a.handler.postDelayed(()->saveStep(1),2000);
    }else if("scenario-idle-foreground".equals(command)){
      if(!manifest.has("idle")||!a.active||a.hub.page!=AppHub.CHAT)throw new IllegalStateException("Foreground idle requires live chat");begin("idle-foreground");
    }else if("scenario-idle-background".equals(command)){
      if(!manifest.has("idle")||!a.active||!phase.isEmpty()||backgroundArmed)throw new IllegalStateException("Background idle must start with actual HOME pause");backgroundArmed=true;a.emit("scenarioArmed",J.obj("name",name));
    }else throw new IllegalArgumentException("Unknown scenario command");
    return true;
  }
  void lifecycle(boolean resumed){
    try{
      if(!resumed&&backgroundArmed){backgroundArmed=false;begin("idle-background");}
      else if(!phase.isEmpty())lifecycleChanges++;
    }catch(Exception error){a.fail(error);}
  }
  void begin(String name)throws Exception{
    if(!phase.isEmpty())throw new IllegalStateException("Overlapping scenario interval");
    phase=name;start=clocks();nativeStart=a.windowFrameRaw.size();choreoStart=a.choreographerRaw.size();lifecycleChanges=0;
    a.emit("scenarioStarted",J.obj("name",name,"start",start,"manifestSha256",manifestSha,"activityResumed",a.active));
    if(name.startsWith("idle-"))a.handler.postDelayed(this::finishIdle,120000);
  }
  void finishIdle(){try{
    if(!phase.startsWith("idle-"))throw new IllegalStateException("Idle phase missing");
    long remaining=120000-(SystemClock.elapsedRealtime()-start.getLong("elapsedRealtimeMs"));
    if(remaining>0){a.handler.postDelayed(this::finishIdle,remaining);return;}
    if(lifecycleChanges!=0||("idle-foreground".equals(phase)!=a.active))throw new IllegalStateException("Unexpected visibility change during idle");
    end(null);
  }catch(Exception error){a.fail(error);}}
  void saveStep(int number){try{
    if(sampling!=null&&(diagnosticFinished||a.benchmarkClosed))return;
    if(sampling!=null)ExperienceSaveSampling.requireMain();
    DownloadTasks tasks=a.downloads.tasks;JSONObject row=DownloadTaskRevisions.find(tasks.rows,PROGRESS);
    if(row==null||!"paused".equals(row.optString("state")))throw new IllegalStateException("Controlled progress record changed");
    DownloadTasks.put(row,"received",number*65536L);
    long started=SystemClock.elapsedRealtimeNanos(),up=SystemClock.uptimeMillis();
    tasks.save();
    long ended=SystemClock.elapsedRealtimeNanos(),endedUp=SystemClock.uptimeMillis();
    if(tasks.indexFailure!=null||tasks.recoveryFailure!=null||tasks.durability.unconfirmed)throw new IllegalStateException("Actual save/index/recovery failed");
    JSONObject stored=DownloadTaskRevisions.find(tasks.read(),PROGRESS);
    if(stored==null||stored.optLong("received")!=number*65536L)throw new IllegalStateException("Actual saved progress differs");
    a.emit("scenarioSave",J.obj("name","history-save-"+number,"step",number,"startElapsedRealtimeNs",started,"endElapsedRealtimeNs",ended,"startUptimeMs",up,"endUptimeMs",endedUp,"durationMs",(ended-started)/1000000.0,"received",stored.optLong("received"),"method","DownloadTasks.save","thread","Android main","httpTransferMeasured",false));
    if(number<8)a.handler.postDelayed(()->saveStep(number+1),2000);
    else{JSONObject verified=verifyHistory(number);end(verified);if(sampling!=null){JSONObject captured=sampling.stop(verified);diagnosticFinished=true;a.emit("samplingFinished",captured);}}
  }catch(Exception error){a.fail(error);}}
  void abortSampling(){if(sampling!=null&&!diagnosticFinished){diagnosticFinished=true;try{a.emit("samplingAborted",sampling.stop(null));}catch(Exception error){a.emit("samplingStopError",J.obj("error",error.toString()));}}}
  JSONObject verifyHistory(int step)throws Exception{
    DownloadTasks tasks=a.downloads.tasks;int count=manifest.getJSONObject("downloadHistory").getInt("savedRows");
    if(tasks.recovering||tasks.recoveryFailure!=null||tasks.indexFailure!=null||tasks.rows.length()!=count+1)throw new IllegalStateException("History recovery/model differs");
    JSONArray prefs=new JSONArray(tasks.prefs.getString("rows","[]"));
    verifySavedRows(tasks.rows,count,true);verifySavedRows(prefs,count,true);
    if(prefs.length()!=count+1||DownloadTaskRevisions.find(prefs,PROGRESS)==null||DownloadTaskRevisions.find(prefs,PROGRESS).optLong("received")!=step*65536L)throw new IllegalStateException("Actual prefs record differs");
    SQLiteDatabase db=DownloadLibrary.get(a).getReadableDatabase();
    try(Cursor c=db.rawQuery("SELECT (SELECT count(*) FROM files),(SELECT count(*) FROM tasks),(SELECT row FROM tasks WHERE slot=0 AND id=?)",new String[]{PROGRESS})){
      if(!c.moveToFirst()||c.getInt(0)!=count||c.getInt(1)!=count+1||J.parse(c.getString(2)).optLong("received")!=step*65536L)throw new IllegalStateException("Actual SQLite rows differ");
    }
    JSONArray indexed=new JSONArray();try(Cursor c=db.rawQuery("SELECT row FROM files",null)){while(c.moveToNext())indexed.put(J.parse(c.getString(0)));}verifySavedRows(indexed,count,false);
    return J.obj("savedRows",count,"taskRows",count+1,"verifiedProgressBytes",step*65536L,"prefsRowsSha256",hash(prefs.toString()),"actualAndroidSQLite",true,"actualAndroidSharedPreferences",true,"verificationOutsideSaveTiming",true);
  }
  void verifySavedRows(JSONArray rows,int count,boolean includesProgress)throws Exception{
    java.util.Set<String> ids=new java.util.HashSet<>();int progress=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.getJSONObject(i);String id=row.getString("id");
      if(PROGRESS.equals(id)&&includesProgress){progress++;continue;}
      if(!id.matches("experience-saved-[0-9]+")||!ids.add(id))throw new IllegalStateException("History identity changed/duplicated");
      int index=Integer.parseInt(id.substring("experience-saved-".length()));
      File file=new File(new File(a.getFilesDir(),"experience-history"),String.format(java.util.Locale.ROOT,"saved-%04d.txt",index));
      if(index<0||index>=count||!file.isFile()||file.length()!=19||!"saved".equals(row.optString("state"))||row.optInt("slot",-1)!=0||row.optLong("time")!=1700000000000L+index||!file.getName().equals(row.optString("name"))||!android.net.Uri.fromFile(file).toString().equals(row.optString("uri")))throw new IllegalStateException("Saved history identity/file changed");
    }
    if(ids.size()!=count||progress!=(includesProgress?1:0))throw new IllegalStateException("History records missing");
  }
  void end(JSONObject verification)throws Exception{
    JSONObject finish=clocks();JSONArray nativeFrames=new JSONArray(),choreo=new JSONArray();
    long first=start.getLong("uptimeMs"),last=finish.getLong("uptimeMs");
    for(int i=nativeStart;i<a.windowFrameRaw.size();i++){JSONObject f=a.windowFrameRaw.get(i);double at=f.optDouble("intendedVsyncUptimeMs");if(at>=first&&at+f.optDouble("durationMs")<=last)nativeFrames.put(f);}
    for(int i=choreoStart;i<a.choreographerRaw.size();i++){JSONObject f=a.choreographerRaw.get(i);if(f.optDouble("previousFrameUptimeMs")>=first&&f.optDouble("frameUptimeMs")<=last)choreo.put(f);}
    JSONObject result=J.obj("name",phase,"start",start,"end",finish,"elapsedDurationMs",finish.getLong("elapsedRealtimeMs")-start.getLong("elapsedRealtimeMs"),"nativeHwuiFrames",nativeFrames,"choreographerFrames",choreo,"lifecycleChanges",lifecycleChanges,"verification",verification==null?JSONObject.NULL:verification,"frameLimitReached",a.windowFrameRaw.size()>=30000||a.choreographerRaw.size()>=30000,"frameScope","Only delivered, wholly-contained native HWUI and foreground Activity Choreographer records, with device uptime timestamps. Late/missing reports are not invented. Not Gecko compositor or display presentation; an empty background list is unobserved, not zero jank.");
    phase="";start=null;a.emit("scenarioFinished",result);
  }
  /** JSONObject checked-exception adapter confined to the fixture. */
  static final class DownloadTasksJson {static JSONObject with(JSONObject value,Object... pairs)throws Exception{for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);return value;}}
}
