package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Shader;
import android.graphics.pdf.PdfDocument;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only local file fixture; the visible screen is DownloadCenterActivity. */
public final class DownloadsWorkspaceVisualActivity extends Activity {
  private static final String RUN="downloadWorkspaceVisualRunV1",MODE="downloadWorkspaceVisualModeV1";
  static final String PAUSED="界面素材与图标资源.zip",FAILED="会议纪要补充资料.pdf";
  static final String[] SAVED={"产品设计说明.pdf","界面参考与配色.png","阅读摘录与笔记.txt"};

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    // Generating local bytes and hashing the installed APK do not block the UI.
    new Thread(()->{
      try{
        if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package required");
        String nonce=getIntent().getStringExtra("visualNonce"),run=getIntent().getStringExtra("visualRunNonce"),mode=getIntent().getStringExtra("visualMode");
        long command=getIntent().getLongExtra("visualCommand",-1);
        if(nonce==null||!nonce.matches("[0-9a-f]{32}")||run==null||!run.matches("[0-9a-f]{32}")||command<=0
            ||!("populated".equals(mode)||"empty".equals(mode)))throw new SecurityException("Owned visual invocation required");
        JSONObject identity=IntegrationBuildIdentity.read(this);
        for(String field:new String[]{"sourceCommit","sourceTree","apkSha256"})
          if(!identity.getString(field).equals(getIntent().getStringExtra("visual"+Character.toUpperCase(field.charAt(0))+field.substring(1))))
            throw new SecurityException("Visual source and installed APK must match");
        seed(run,mode);
        JSONObject fixture=describe(mode).put("status","ready").put("parentRunNonce",run)
          .put("actualProductionActivity","local.pocketchat.test/local.pocketchat.DownloadCenterActivity")
          .put("syntheticFixture",true).put("syntheticTaskMetadata",true).put("actualNetworkTransfer",false);
        IntegrationEventStore events=new IntegrationEventStore(this,0,nonce,"download-workspace",command,identity);
        events.emit("downloadWorkspaceFixture",fixture);
        runOnUiThread(()->{startActivity(new Intent(this,DownloadCenterActivity.class));finish();});
      }catch(Exception error){
        Log.e("PocketDownloadVisual","download workspace fixture setup failed",error);
        runOnUiThread(this::finish);
      }
    },"download-workspace-visual-seed").start();
  }

  private void seed(String run,String mode)throws Exception{
    String previous=AppSettings.get(this,RUN,"");
    if(!previous.isEmpty()){
      if(!run.equals(previous)||!mode.equals(AppSettings.get(this,MODE,"")))throw new SecurityException("A fresh disposable fixture is required");
      return;
    }
    ProfileCatalog catalog=ProfileCatalog.get(this);
    JSONArray existing=catalog.list();
    for(int i=0;i<existing.length();i++){
      JSONObject row=existing.getJSONObject(i);
      if((row.optInt("slot")!=0&&row.optBoolean("created"))||row.optLong("opened")!=0||row.optLong("seen")!=0
          ||!row.optString("problem").isEmpty()||!row.optString("draft").isEmpty())
        throw new IllegalStateException("Unrelated profile data must not be reset by a visual fixture");
    }
    if(DownloadDisplaySnapshot.read(this).length()!=0)throw new IllegalStateException("An empty local download library is required");
    String[] names={"日常会话","资料整理","开发调试","长文阅读","翻译与写作"};
    for(int slot=0;slot<names.length;slot++){
      catalog.created(slot);Profiles.rename(this,slot,names[slot]);catalog.details(slot,slot==0?"个人":"工作","");
      Profiles.context(this,slot).getSharedPreferences("chat",0).edit().putString("browserEngine","gecko")
        .putString("networkMode","external").putBoolean("networkConfigured",false).putBoolean("pageMode",true)
        .putBoolean("environmentInitialized",true).commit();
    }
    Bundle options=new Bundle();options.putBoolean("autoCheck",false);AppUpdates.call(this,"settings",options);
    AppSettings.defaultSlot(this,0);AppSettings.put(this,"brandSeen","true");AppSettings.put(this,"updateAutoCheck","false");
    if("populated".equals(mode)){
      long now=System.currentTimeMillis();
      saveFile(1,SAVED[0],"application/pdf",pdf(),now-30*60*1000L);
      saveFile(3,SAVED[1],"image/png",image(),now-45*60*1000L);
      saveFile(4,SAVED[2],"text/plain",("本地界面预览示例\n\n阅读摘录、重点与想法。\n这些内容只用于下载页面的真实文件展示。\n").getBytes(StandardCharsets.UTF_8),now-60*60*1000L);
      byte[] target=archive();int received=target.length/3;
      Context profile=Profiles.context(this,2);String id=UUID.randomUUID().toString(),partial="download-"+id+".part";
      try(FileOutputStream out=new FileOutputStream(new File(profile.getCacheDir(),partial))){out.write(target,0,received);}
      JSONObject paused=owned(2).put("id",id).put("name",PAUSED).put("mime","application/zip")
        .put("state","paused").put("reason","").put("received",received).put("total",target.length)
        .put("time",now).put("partial",partial);
      storeTask(profile,paused);
      JSONObject failed=owned(0).put("id",UUID.randomUUID().toString()).put("name",FAILED).put("mime","application/pdf")
        .put("state","failed").put("reason","连接中断，请检查网络后重试。")
        .put("received",0).put("total",-1).put("time",now-5*60*1000L);
      storeTask(Profiles.context(this,0),failed);
    }
    AppSettings.put(this,MODE,mode);AppSettings.put(this,RUN,run);
  }

  private JSONObject owned(int slot)throws Exception{
    JSONObject environment=ProfileCatalog.get(this).item(slot);
    return J.obj("slot",slot,"environmentId",environment.getString("environmentId"),
      "environmentGeneration",environment.getInt("generation"),"environmentName",environment.getString("name"));
  }

  private void storeTask(Context profile,JSONObject row)throws Exception{
    DownloadTasks tasks=new DownloadTasks(profile);tasks.rows.put(row);tasks.save(true);
    if(tasks.indexFailure!=null)throw new IllegalStateException("The fixture task was not indexed",tasks.indexFailure);
    tasks.release();
  }

  private void saveFile(int slot,String name,String mime,byte[] bytes,long time)throws Exception{
    String id=UUID.randomUUID().toString();Uri uri=new Uri.Builder().scheme("content")
      .authority(getPackageName()+".saved-downloads").appendPath(String.valueOf(slot)).appendPath(id).appendPath(name).build();
    File file=SavedDownloadProvider.resolve(this,uri),directory=file.getParentFile();
    if(!directory.mkdirs()&&!directory.isDirectory())throw new IllegalStateException("The fixture file directory is unavailable");
    try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
    JSONObject row=owned(slot).put("id",id).put("name",name).put("actualName",name).put("mime",mime).put("actualMime",mime)
      .put("uri",uri.toString()).put("state","saved").put("time",time).put("location","应用内文件 / "+name);
    DownloadMetadataValues.checked(row,file.length(),"owned-stat","known");
    DownloadLibrary library=DownloadLibrary.get(this);library.add(Profiles.context(this,slot),row);
    if(library.saved(row)==null)throw new IllegalStateException("The fixture file was not published to the real library");
  }

  private JSONObject describe(String mode)throws Exception{
    JSONArray rows=DownloadDisplaySnapshot.read(this),files=new JSONArray(),partials=new JSONArray();
    if(rows.length()!=("populated".equals(mode)?5:0))throw new IllegalStateException("Unexpected fixture record count");
    int active=0,paused=0,failed=0;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.getJSONObject(i);String state=row.getString("state");
      JSONObject environment=ProfileCatalog.get(this).item(row.getInt("slot"));
      if(!environment.optBoolean("created")||!row.getString("environmentId").equals(environment.getString("environmentId"))
          ||row.getInt("environmentGeneration")!=environment.getInt("generation"))
        throw new IllegalStateException("Fixture ownership differs from the actual environment");
      if(DownloadListPolicy.busy(state))active++;
      if("saved".equals(state)){
        Uri uri=Uri.parse(row.getString("uri"));JSONObject proof;
        try(InputStream input=getContentResolver().openInputStream(uri)){proof=bytes(input);}
        if(proof.getLong("bytes")!=DownloadMetadataValues.bytes(row))throw new IllegalStateException("Published fixture size differs from readable bytes");
        files.put(proof.put("id",row.getString("id")).put("name",DownloadMetadataValues.name(row))
          .put("uri",uri.toString()).put("slot",row.getInt("slot")).put("readable",true));
      }else if("paused".equals(state)){
        paused++;Context profile=Profiles.context(this,row.getInt("slot"));
        JSONArray stored=new JSONArray(profile.getSharedPreferences("download-tasks",0).getString("rows","[]"));
        JSONObject task=DownloadTaskRevisions.find(stored,row.getString("id"));
        if(task==null||!task.optString("partial").matches("download-[A-Za-z0-9-]+[.]part"))throw new IllegalStateException("The paused fixture lacks its partial file");
        JSONObject proof;try(InputStream input=new FileInputStream(new File(profile.getCacheDir(),task.getString("partial")))){proof=bytes(input);}
        if(proof.getLong("bytes")!=row.getLong("received")||row.getLong("total")<=row.getLong("received"))throw new IllegalStateException("Paused fixture progress differs from its partial bytes");
        partials.put(proof.put("id",row.getString("id")).put("name",row.getString("name")).put("slot",row.getInt("slot")));
      }else if("failed".equals(state))failed++;
      else throw new IllegalStateException("Unexpected fixture task state");
    }
    boolean populated="populated".equals(mode);
    if(active!=0||files.length()!=(populated?3:0)||paused!=(populated?1:0)||failed!=(populated?1:0))throw new IllegalStateException("Unexpected visual state distribution");
    return J.obj("mode",mode,"rows",rows,"savedFiles",files,"partialFiles",partials,"recordCount",rows.length(),
      "activeTransferCount",active,"savedCount",files.length(),"pausedCount",paused,"failedCount",failed,
      "scope","Native production download page with local readable fixture files and synthetic paused/failed metadata; no network transfer or real account claim");
  }

  private static JSONObject bytes(InputStream input)throws Exception{
    if(input==null)throw new IllegalStateException("Fixture content could not be opened");
    MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] block=new byte[8192];long size=0;int count;
    while((count=input.read(block))!=-1){size+=count;if(size>1024*1024)throw new IllegalStateException("Fixture file exceeds the bounded visual payload");digest.update(block,0,count);}
    StringBuilder hex=new StringBuilder();for(byte part:digest.digest())hex.append(String.format(Locale.ROOT,"%02x",part&255));
    return J.obj("bytes",size,"sha256",hex.toString());
  }

  private static byte[] pdf()throws Exception{
    PdfDocument document=new PdfDocument();ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    try{
      PdfDocument.Page page=document.startPage(new PdfDocument.PageInfo.Builder(595,842,1).create());
      Canvas canvas=page.getCanvas();canvas.drawColor(Color.WHITE);Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
      paint.setColor(0xff1d2632);paint.setTextSize(26);canvas.drawText("产品设计说明",48,86,paint);
      paint.setTextSize(14);canvas.drawText("本地界面预览示例",48,124,paint);canvas.drawText("下载、整理与阅读，让每一步都更清晰。",48,160,paint);
      document.finishPage(page);document.writeTo(bytes);return bytes.toByteArray();
    }finally{document.close();bytes.close();}
  }

  private static byte[] image()throws Exception{
    Bitmap bitmap=Bitmap.createBitmap(480,320,Bitmap.Config.ARGB_8888);ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    try{
      Canvas canvas=new Canvas(bitmap);Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
      paint.setShader(new LinearGradient(0,0,480,320,0xffd9e9ff,0xffe5f5ef,Shader.TileMode.CLAMP));canvas.drawRect(0,0,480,320,paint);
      paint.setShader(null);paint.setColor(0xff31465d);paint.setTextSize(24);canvas.drawText("界面参考与配色",32,68,paint);
      paint.setTextSize(15);canvas.drawText("本地界面预览示例",32,104,paint);
      if(!bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes))throw new IllegalStateException("Fixture PNG could not be encoded");return bytes.toByteArray();
    }finally{bitmap.recycle();bytes.close();}
  }

  private static byte[] archive()throws Exception{
    ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    try(ZipOutputStream zip=new ZipOutputStream(bytes)){
      zip.putNextEntry(new ZipEntry("local-visual-fixture.bin"));byte[] body=new byte[384*1024];new java.util.Random(91).nextBytes(body);zip.write(body);zip.closeEntry();
    }
    return bytes.toByteArray();
  }
}
