package local.pocketchat;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.view.inspector.WindowInspector;
import android.widget.Button;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.WebResponse;

/** Synthetic Android file lifecycle. Production transfer/publication/retirement methods are inherited. */
public final class DownloadResumeIntegrationActivity extends MainActivity {
  static final String PAGE=ORIGIN+"c/download-resume-fixture",REMOTE="https://download-fixture.example/";
  final JSONArray checks=new JSONArray(),http=new JSONArray(),menus=new JSONArray();
  final JSONObject result=J.obj("schema",1,"status","running","actualAndroidExecution",true,
      "actualAdbTouchExecution",false,"actualDialogPerformClick",true,"processSlot",7,
      "scope","Synthetic profile-7 Android Activity, actual FileDownloads methods, private partials and MediaStore publication. Fixed synthetic HTTPS identity maps only to an in-process loopback HTTP server (no TLS/WAN claim). File-prepare is a controlled callback; no website download click is claimed. SDK WebResponse carries a synthetic barrier stream. Android Dialog buttons use performClick, not ADB touch.");
  final List<FileDownloads> instances=new ArrayList<>();final List<File> ownedFiles=new ArrayList<>();
  final Set<String> ownIds=new HashSet<>();final List<JSONObject> published=new ArrayList<>();
  final List<BlockedBody> blockedBodies=new ArrayList<>();
  final Map<String,Object> oldPrefs=new HashMap<>();
  IntegrationEventStore events;MappedDownloads current;String preparedSource="",preparedUrl="";int prepares;
  JSONObject originalEnvironment;String fixtureEnvironmentId;
  static final class FixtureView extends GeckoWebView {
    FixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override public String getUrl(){return PAGE;}
    @Override protected boolean allowedUrl(String url){return false;}
  }
  @Override void startNetwork(){}
  @Override public void onCreate(Bundle state){
    if(!"local.pocketchat.test".equals(getPackageName())||Profiles.processSlot()!=7)throw new SecurityException("Isolated synthetic profile required");
    try{
      originalEnvironment=ProfileCatalog.get(this).item(7);ProfileCatalog.get(this).created(7);fixtureEnvironmentId=ProfileCatalog.get(this).item(7).optString("environmentId");
      SharedPreferences p=getSharedPreferences("chat",0);
      for(String key:new String[]{"networkMode","proxy","requireExternalVpn","networkConfigured","environmentInitialized"})oldPrefs.put(key,p.getAll().get(key));
      p.edit().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",true).putBoolean("environmentInitialized",true).commit();
      ChatSession.browserFactory=FixtureView::new;ChatSession.get(this).manualAttention=true;
      getIntent().putExtra("openWindowAction","native-smoke");super.onCreate(state);
      handler.removeCallbacks(ticker);session.remove(sessionObserver);session.handler.removeCallbacks(session.tick);
      session.networkReady=true;session.offline=false;session.navigating=false;session.guard.setBlocked(false);conversation=PAGE;session.conversation=PAGE;
      downloads.destroy();
      events=new IntegrationEventStore(this,7,getIntent().getStringExtra("eventNonce"),"downloadResume",1,IntegrationBuildIdentity.read(this));
      result.put("buildIdentity",events.buildIdentity).put("runNonce",getIntent().getStringExtra("eventNonce"));
      new Thread(this::exercise,"android-download-resume-fixture").start();
    }catch(Exception error){throw new IllegalStateException("Download resume fixture setup",error);}
  }
  @Override protected void onResume(){super.onResume();handler.removeCallbacks(ticker);if(session!=null){session.remove(sessionObserver);session.handler.removeCallbacks(session.tick);}}
  @Override void runDriver(String action,JSONObject args,Result callback){
    if("file-prepare".equals(action)){
      if(!preparedSource.equals(args.optString("id"))||!PAGE.equals(args.optString("expectedUrl"))||current==null)throw new IllegalStateException("Unowned file preparation");
      prepares++;MappedDownloads owner=current;String url=preparedUrl;
      callback.accept(J.obj("ok",true,"name","f06-"+UUID.randomUUID()+".bin","kind","file"));
      handler.post(()->owner.accept(url,"controlled-f06","","application/octet-stream",-1));return;
    }
    if("file-point".equals(action)||"file-followup".equals(action)){callback.accept(J.obj("ok",true));return;}
    super.runDriver(action,args,callback);
  }
  <T>T ui(Callable<T> action)throws Exception{
    if(Looper.myLooper()==Looper.getMainLooper())return action.call();
    CompletableFuture<T> future=new CompletableFuture<>();handler.post(()->{try{future.complete(action.call());}catch(Throwable error){future.completeExceptionally(error);}});
    return future.get(10,TimeUnit.SECONDS);
  }
  <T>T visible(Callable<T> observe)throws Exception{
    CompletableFuture<T> future=new CompletableFuture<>();long deadline=SystemClock.elapsedRealtime()+10000;
    handler.post(new Runnable(){public void run(){try{T value=observe.call();if(value!=null){future.complete(value);return;}if(SystemClock.elapsedRealtime()>=deadline)throw new IllegalStateException("Owned Android view did not become visible");android.view.Choreographer.getInstance().postFrameCallback(frame->run());}catch(Throwable error){future.completeExceptionally(error);}}});
    return future.get(12,TimeUnit.SECONDS);
  }
  void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void drain(FileDownloads d)throws Exception{d.worker.submit(()->{}).get(10,TimeUnit.SECONDS);ui(()->null);d.worker.submit(()->{}).get(10,TimeUnit.SECONDS);ui(()->null);}
  void recovery()throws Exception{DownloadTasks.recovery.submit(()->{}).get(10,TimeUnit.SECONDS);ui(()->null);}
  MappedDownloads fresh()throws Exception{
    MappedDownloads d=ui(()->new MappedDownloads(this));instances.add(d);recovery();return d;
  }
  File partial(byte[] bytes)throws Exception{File file=File.createTempFile("download-",".part",getCacheDir());Files.write(file.toPath(),bytes);ownedFiles.add(file);return file;}
  JSONObject row(FileDownloads d,String kind,File file,boolean complete,String source)throws Exception{
    return ui(()->{JSONObject row=d.tasks.add(source,"owned-key",PAGE);ownIds.add(row.optString("id"));DownloadTasks.put(row,"state","paused","name","f06-"+UUID.randomUUID()+".bin","mime","application/octet-stream","complete",complete,"transferKind",kind,"partial",file.getName(),"received",file.length(),"total",-1);d.tasks.save();if(!d.loadTask(row))throw new IllegalStateException("Owned row claim");return row;});
  }
  Button button(View view,String text){
    if(view instanceof Button&&text.contentEquals(((Button)view).getText())&&view.isShown())return (Button)view;
    if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){Button found=button(((ViewGroup)view).getChildAt(i),text);if(found!=null)return found;}
    return null;
  }
  Button visibleButton(String text)throws Exception{return visible(()->{Button found=null;for(View root:WindowInspector.getGlobalWindowViews()){Button b=button(root,text);if(b!=null){if(found!=null)throw new IllegalStateException("Ambiguous real dialog button: "+text);found=b;}}return found;});}
  void click(String text)throws Exception{Button button=visibleButton(text);ui(()->{if(!button.performClick())throw new IllegalStateException("Dialog click rejected");menus.put(J.obj("label",text,"performClick",true));return null;});ui(()->null);}
  void exercise(){
    try{
      check("F06 executes in an attached Android Activity and isolated profile 7",Profiles.slot(this)==7&&visible(()->getWindow().getDecorView().isAttachedToWindow()?Boolean.TRUE:null)&&Looper.myLooper()!=Looper.getMainLooper());
      range(206);range(200);retirement();oldWriter();protectedRows();
      result.put("status","passed");
    }catch(Throwable error){try{result.put("status","failed").put("error",error.toString());}catch(Exception ignored){}}
    finally{
      try{cleanup();result.put("ownedCleanupCompleted",true);}catch(Throwable error){try{result.put("status","failed").put("cleanupError",error.toString());}catch(Exception ignored){}}
      try{result.put("checks",checks).put("checkCount",checks.length()).put("http",http).put("menus",menus).put("filePrepareCallbacks",prepares);events.emit("downloadResume",result);}catch(Exception error){if(events!=null)events.failure(error);}
      handler.post(this::finish);
    }
  }
  void range(int code)throws Exception{
    byte[] prefix={1,2,3,4},tail={5,6,7,8,9},expected=code==206?new byte[]{1,2,3,4,5,6,7,8,9}:tail;
    try(Endpoint endpoint=new Endpoint(code,tail)){
      MappedDownloads d=fresh();File file=partial(prefix);String source=UUID.randomUUID().toString(),url=REMOTE+UUID.randomUUID()+".bin";
      JSONObject row=row(d,"http-range",file,false,source);String id=row.optString("id");
      ui(()->{d.endpoint=endpoint;d.expectedUrl=url;DownloadTasks.put(row,"validator","\"f06-v1\"","resource",DownloadRange.resource(url));d.tasks.save();if(!d.loadTask(row))throw new IllegalStateException("Range row");current=d;preparedSource=source;preparedUrl=url;d.taskActions(row);return null;});
      check("HTTP "+code+" paused task renders the real continue-download action","继续下载".contentEquals(visibleButton("继续下载").getText()));
      click("继续下载");endpoint.done.get(10,TimeUnit.SECONDS);drain(d);
      JSONObject saved=ui(()->new JSONObject(row.toString()).put("slot",7));Uri uri=Uri.parse(saved.optString("uri"));if(!uri.toString().isEmpty())published.add(saved);
      byte[] actual=read(uri);
      JSONObject observation=J.obj("code",code,"mappedFrom",url,"mappedTo",endpoint.address(),"request",endpoint.request,"method",endpoint.method,
          "range",endpoint.range,"ifRange",endpoint.validator,"responseBytes",tail.length,"expectedBytes",expected.length,"savedBytes",actual.length,
          "expectedSha256",sha(expected),"savedSha256",sha(actual),"taskIdBefore",id,"taskIdAfter",saved.optString("id"),"state",saved.optString("state"),"uri",uri.toString(),"sourcePartialExists",file.exists());http.put(observation);
      check("HTTP "+code+" continuation sends exact Range and validator through a real socket","GET".equals(endpoint.method)&&"bytes=4-".equals(endpoint.range)&&"\"f06-v1\"".equals(endpoint.validator));
      check("HTTP "+code+" continuation publishes exact bytes without a duplicate task",Arrays.equals(expected,actual)&&id.equals(saved.optString("id"))&&"saved".equals(saved.optString("state"))&&!file.exists()&&"media".equals(uri.getAuthority()));
      ui(()->{d.discardForRedownload(row);return null;});drain(d);
      byte[] preserved=read(uri);observation.put("afterRetireSha256",sha(preserved)).put("indexedAfterRetire",DownloadLibrary.get(this).indexed(uri));
      check("HTTP "+code+" retired-partial cleanup cannot delete the published destination",Arrays.equals(expected,preserved)&&DownloadLibrary.get(this).indexed(uri));
      ui(()->{d.destroy();return null;});
    }
  }
  void retirement()throws Exception{
    MappedDownloads d=fresh();File selected=partial(new byte[]{10,11,12}),other=partial(new byte[]{21,22});JSONObject row=row(d,"gecko-response",selected,false,"");String oldId=row.optString("id");
    ui(()->{d.taskActions(row);return null;});check("Native web response renders re-download instead of continue-download","重新下载".contentEquals(visibleButton("重新下载").getText()));
    click("重新下载");click("保留副本");
    check("Cancelling re-download preserves the exact selected partial",Arrays.equals(Files.readAllBytes(selected.toPath()),new byte[]{10,11,12})&&row.optString("retiredPartial").isEmpty());
    ui(()->{d.taskActions(row);return null;});click("重新下载");click("清理旧副本并重新下载");drain(d);
    check("Confirmed re-download retires only the selected app-private incomplete bytes",!selected.exists()&&Arrays.equals(Files.readAllBytes(other.toPath()),new byte[]{21,22})&&row.optString("partial").isEmpty()&&row.optString("retiredPartial").isEmpty()&&row.optString("reason").contains("已清理"));
    WebResponse next=new WebResponse.Builder(REMOTE+"next.bin").statusCode(200).header("Content-Type","application/octet-stream").header("Content-Length","3").body(new ByteArrayInputStream(new byte[]{31,32,33})).build();
    ui(()->{d.acceptResponse(next);ownIds.add(d.task.optString("id"));return null;});drain(d);JSONObject fresh=ui(()->new JSONObject(d.task.toString()).put("slot",7));Uri uri=Uri.parse(fresh.optString("uri"));if(!uri.toString().isEmpty())published.add(fresh);
    check("Next SDK response creates a new task rather than guessing a retired URL binding",!oldId.equals(fresh.optString("id"))&&"saved".equals(fresh.optString("state"))&&Arrays.equals(read(uri),new byte[]{31,32,33})&&row.optString("uri").isEmpty());
    result.put("retirement",J.obj("oldTaskId",oldId,"newTaskId",fresh.optString("id"),"selectedAbsent",!selected.exists(),"otherBytesSha256",sha(Files.readAllBytes(other.toPath())),"oldState",row.optString("state"),"oldUri",row.optString("uri"),"retiredMarker",row.optString("retiredPartial"),"nextState",fresh.optString("state")));
    ui(()->{d.destroy();return null;});
  }
  static final class BlockedBody extends InputStream {
    final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);int calls;volatile boolean lateBytesReturned;
    @Override public int read()throws IOException{throw new IOException("Bulk fixture only");}
    @Override public int read(byte[] bytes)throws IOException{
      if(calls++==0){Arrays.fill(bytes,0,4,(byte)7);return 4;}if(calls>2)return -1;
      entered.countDown();try{if(!release.await(30,TimeUnit.SECONDS))throw new IOException("Held SDK read deadline");}catch(InterruptedException error){throw new IOException(error);}
      bytes[0]=99;lateBytesReturned=true;return 1;
    }
    @Override public void close(){/* Fault injection: an already blocked native read completes later. */}
  }
  void oldWriter()throws Exception{
    MappedDownloads old=fresh();BlockedBody body=new BlockedBody();blockedBodies.add(body);
    WebResponse response=new WebResponse.Builder(REMOTE+"held.bin").statusCode(200).header("Content-Type","application/octet-stream").header("Content-Length","5").body(body).build();
    ui(()->{old.acceptResponse(response);ownIds.add(old.task.optString("id"));return null;});
    if(!body.entered.await(10,TimeUnit.SECONDS))throw new IllegalStateException("Actual production writer did not enter held read");ui(()->null);
    File file=old.temp;ownedFiles.add(file);String id=old.task.optString("id");long oldTicket=old.ticket;
    ui(()->{old.destroy();return null;});MappedDownloads newer=fresh();JSONObject selected=ui(()->DownloadTaskRevisions.find(newer.tasks.rows,id));
    File complete=partial(new byte[]{41,42,43});JSONObject completed=row(newer,"gecko-response",complete,true,"");
    ui(()->{newer.taskActions(completed);return null;});Button late=visibleButton("继续保存");click("关闭");
    Thread worker=newer.worker.submit(Thread::currentThread).get(10,TimeUnit.SECONDS);
    ui(()->{if(selected==null||!newer.loadTask(selected))throw new IllegalStateException("Recreated owner claim");newer.discardForRedownload(selected);return null;});
    long deadline=SystemClock.elapsedRealtime()+10000;boolean waiting=false;JSONArray stack=new JSONArray();
    do{boolean lease=false,lock=false;StackTraceElement[] frames=worker.getStackTrace();for(StackTraceElement frame:frames){lease|=frame.getClassName().equals("local.pocketchat.SealedFileIo")&&frame.getMethodName().equals("lease");lock|=frame.getClassName().equals("java.util.concurrent.locks.ReentrantLock")&&frame.getMethodName().equals("lockInterruptibly");}
      waiting=lease&&lock;if(waiting)for(StackTraceElement frame:frames)stack.put(frame.toString());else Thread.yield();
    }while(!waiting&&SystemClock.elapsedRealtime()<deadline);
    String generation=selected.optString("taskGeneration");byte[] before=Files.readAllBytes(file.toPath());
    check("Recreated owner waits inside the real partial lease while the old SDK writer is blocked",waiting&&ui(()->newer.retiringPartial)&&Arrays.equals(before,new byte[]{7,7,7,7}));
    boolean lateClick=ui(late::performClick);
    JSONObject menuAfter=ui(()->J.obj("generation",selected.optString("taskGeneration"),"taskId",newer.task.optString("id")));
    String afterMenuGeneration=menuAfter.optString("generation"),afterMenuTask=menuAfter.optString("taskId");
    check("Late continue-saving menu callback cannot replace the retiring task or its generation",lateClick&&ui(()->newer.task==selected&&newer.retiringPartial&&generation.equals(selected.optString("taskGeneration")))&&complete.isFile()&&file.isFile());
    body.release.countDown();if(!old.worker.awaitTermination(10,TimeUnit.SECONDS))throw new IllegalStateException("Old writer did not terminate");drain(newer);
    check("Old writer late bytes cannot resurrect a retired partial or publish a destination",body.lateBytesReturned&&!file.exists()&&selected.optString("uri").isEmpty()&&selected.optString("retiredPartial").isEmpty()&&ui(()->!newer.retiringPartial));
    String after=ui(selected::toString);ui(()->{old.fail(oldTicket,"controlled old callback");return null;});ui(()->null);
    check("Old failure callback leaves the new task receipt and complete copy unchanged",after.equals(ui(selected::toString))&&Arrays.equals(Files.readAllBytes(complete.toPath()),new byte[]{41,42,43}));
    result.put("writer",J.obj("taskId",id,"generation",generation,"generationAfterLateMenu",afterMenuGeneration,"taskIdAfterLateMenu",afterMenuTask,"lateMenuPerformClick",lateClick,"oldTicket",oldTicket,"oldTicketAfterDestroy",old.ticket,"waitedInsideLease",waiting,"workerStack",stack,"beforeBytesSha256",sha(before),"lateBytesReturned",body.lateBytesReturned,"partialExistsAfter",file.exists(),"uriAfter",selected.optString("uri"),"retiredMarkerAfter",selected.optString("retiredPartial"),"retiringAfter",newer.retiringPartial,"lateCallbackUnchanged",after.equals(ui(selected::toString)),"completeCopySha256",sha(Files.readAllBytes(complete.toPath()))));
    ui(()->{newer.destroy();return null;});
  }
  void protectedRows()throws Exception{
    MappedDownloads d=fresh();File file=partial(new byte[]{51,52});JSONObject row=row(d,"gecko-response",file,true,"");
    check("Completed private copies are not eligible for partial retirement",!ui(()->d.tasks.beginPartialRetirement(row,row.optString("taskGeneration"),file.getName()))&&file.isFile());
    ui(()->{DownloadTasks.put(row,"complete",false,"pendingDestination","content://owned-fixture/pending");d.tasks.save();return null;});
    check("A pending published destination blocks partial retirement",!ui(()->d.tasks.beginPartialRetirement(row,row.optString("taskGeneration"),file.getName()))&&file.isFile());
    ui(()->{row.remove("pendingDestination");DownloadTasks.put(row,"partial","../outside-user-file");d.tasks.save();return null;});
    check("Retirement refuses paths outside the app-private partial directory",ui(()->d.tasks.retirementFile(row)==null)&&file.isFile());
    ui(()->{d.destroy();return null;});
  }
  byte[] read(Uri uri)throws Exception{try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){if(in==null)throw new IOException("Missing published bytes");byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toByteArray();}}
  static String sha(byte[] bytes)throws Exception{StringBuilder out=new StringBuilder();for(byte b:java.security.MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
  void cleanup()throws Exception{
    for(BlockedBody body:blockedBodies)body.release.countDown();
    for(FileDownloads d:instances){ui(()->{if(!d.destroyed)d.destroy();return null;});if(!d.worker.awaitTermination(10,TimeUnit.SECONDS))throw new IllegalStateException("Owned writer did not drain for cleanup");if(d.temp!=null&&d.task!=null&&ownIds.contains(d.task.optString("id")))ownedFiles.add(d.temp);}ui(()->null);
    Set<String> removedUris=new HashSet<>();
    for(FileDownloads d:instances){JSONObject saved=ui(()->d.task!=null?new JSONObject(d.task.toString()).put("slot",7):null);if(saved!=null&&ownIds.contains(saved.optString("id"))&&"saved".equals(saved.optString("state"))&&!saved.optString("uri").isEmpty())published.add(saved);}
    for(JSONObject row:published)if(removedUris.add(row.optString("uri")))SavedFileDeletion.remove(this,row);
    for(File file:ownedFiles)SealedFileIo.lease(file,()->{if(!file.delete()&&file.exists())throw new IOException("Owned fixture partial cleanup");return null;});
    ui(()->{
      SharedPreferences tasks=getSharedPreferences("download-tasks",0);JSONArray rows=new JSONArray(tasks.getString("rows","[]")),kept=new JSONArray();
      for(int i=0;i<rows.length();i++)if(!ownIds.contains(rows.optJSONObject(i).optString("id")))kept.put(rows.optJSONObject(i));
      if(!tasks.edit().putString("rows",kept.toString()).commit())throw new IllegalStateException("Owned fixture metadata cleanup");
      for(String id:ownIds)DownloadLibrary.get(this).getWritableDatabase().delete("tasks","slot=? AND id=?",new String[]{"7",id});
      JSONObject history=J.parse(prefs.getString("downloadHistory","{}"));JSONArray files=history.optJSONArray("files");if(files!=null){JSONArray retained=new JSONArray();for(int i=0;i<files.length();i++)if(!ownIds.contains(files.optJSONObject(i).optString("id")))retained.put(files.optJSONObject(i));history.put("files",retained);if(!prefs.edit().putString("downloadHistory",history.toString()).commit())throw new IllegalStateException("Owned history cleanup");}
      SharedPreferences.Editor restore=prefs.edit();for(Map.Entry<String,Object> item:oldPrefs.entrySet()){Object valueBefore=item.getValue();if(valueBefore==null)restore.remove(item.getKey());else if(valueBefore instanceof Boolean)restore.putBoolean(item.getKey(),(Boolean)valueBefore);else restore.putString(item.getKey(),(String)valueBefore);}if(!restore.commit())throw new IllegalStateException("Fixture preference restore");return null;
    });
    if(!originalEnvironment.optBoolean("created")){
      android.content.ContentValues restore=new android.content.ContentValues();restore.put("created",0);restore.put("environment_id",originalEnvironment.optString("environmentId"));
      if(ProfileCatalog.get(this).getWritableDatabase().update("environments",restore,"slot=7 AND environment_id=? AND generation=?",new String[]{fixtureEnvironmentId,String.valueOf(originalEnvironment.optInt("generation"))})!=1)throw new IllegalStateException("Fixture environment identity changed before cleanup");
    }
  }
  static final class MappedDownloads extends FileDownloads {
    Endpoint endpoint;String expectedUrl="";
    MappedDownloads(MainActivity owner){super(owner);}
    @Override HttpURLConnection connect(String url,Proxy proxy)throws Exception{
      if(endpoint==null||!url.equals(expectedUrl)||proxy!=Proxy.NO_PROXY)throw new SecurityException("Only the owned synthetic HTTP mapping is permitted");
      return (HttpURLConnection)new URL(endpoint.address()).openConnection(Proxy.NO_PROXY);
    }
  }
  static final class Endpoint implements AutoCloseable {
    final ServerSocket socket;final CompletableFuture<Void> done=new CompletableFuture<>();final int code;final byte[] bytes;
    volatile String request="",method="",range="",validator="";
    Endpoint(int code,byte[] bytes)throws Exception{this.code=code;this.bytes=bytes;socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));socket.setSoTimeout(10000);new Thread(this::serve,"f06-owned-http").start();}
    String address(){return "http://127.0.0.1:"+socket.getLocalPort()+"/owned.bin";}
    void serve(){try(Socket client=socket.accept()){
      client.setSoTimeout(10000);BufferedReader reader=new BufferedReader(new InputStreamReader(client.getInputStream(),StandardCharsets.ISO_8859_1));request=reader.readLine();if(request==null)throw new IOException("Missing HTTP request");method=request.split(" ")[0];
      for(String line;(line=reader.readLine())!=null&&!line.isEmpty();){int colon=line.indexOf(':');if(colon<0)throw new IOException("Invalid header");String name=line.substring(0,colon),value=line.substring(colon+1).trim();if("Range".equalsIgnoreCase(name))range=value;if("If-Range".equalsIgnoreCase(name))validator=value;}
      String headers="HTTP/1.1 "+code+(code==206?" Partial Content":" OK")+"\r\nContent-Type: application/octet-stream\r\nContent-Length: "+bytes.length+"\r\nETag: \"f06-v1\"\r\nConnection: close\r\n"+(code==206?"Content-Range: bytes 4-8/9\r\n":"")+"\r\n";
      OutputStream out=client.getOutputStream();out.write(headers.getBytes(StandardCharsets.ISO_8859_1));out.write(bytes);out.flush();done.complete(null);
    }catch(Throwable failure){done.completeExceptionally(failure);}}
    @Override public void close()throws IOException{socket.close();}
  }
}
