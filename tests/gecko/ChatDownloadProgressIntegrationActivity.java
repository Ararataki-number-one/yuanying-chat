package local.pocketchat;

import android.content.*;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.WebResponse;

/** Independent chat-card workload; the original download-resume fixture is unchanged. */
public final class ChatDownloadProgressIntegrationActivity extends MainActivity {
  final JSONObject result=J.obj("status","running","actualAndroidExecution",true,"actualNativeView",true,"actualProductionStream",true,"actualAdbTouchExecution",false);
  final JSONArray checks=new JSONArray(),observations=new JSONArray();final Set<String> ids=new HashSet<>();
  final List<File> partials=new ArrayList<>();final List<DownloadResumeIntegrationActivity.BlockedBody> bodies=new ArrayList<>();
  final Map<String,Object> oldPrefs=new HashMap<>();JSONObject oldEnvironment,published;String environmentId;
  @Override void startNetwork(){}
  @Override void resumeChatUi(){if(session!=null){session.networkReady=true;session.offline=false;session.navigating=false;session.guard.setBlocked(false);if(chatDownloadProgress!=null)chatDownloadProgress.update();handler.removeCallbacks(ticker);handler.post(ticker);}}
  @Override public void onCreate(Bundle state){
    if(!"local.pocketchat.test".equals(getPackageName())||Profiles.processSlot()!=7)throw new SecurityException("Owned integration profile required");
    try{
      oldEnvironment=ProfileCatalog.get(this).item(7);ProfileCatalog.get(this).created(7);environmentId=ProfileCatalog.get(this).item(7).optString("environmentId");
      SharedPreferences preferences=getSharedPreferences("chat",0);for(String key:new String[]{"networkMode","proxy","requireExternalVpn","networkConfigured","environmentInitialized"})oldPrefs.put(key,preferences.getAll().get(key));
      preferences.edit().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",true).putBoolean("environmentInitialized",true).commit();
      ChatSession.browserFactory=(context,owner)->new GeckoWebView(context,owner){@Override public String getUrl(){return ORIGIN+"c/chat-progress-fixture";}@Override protected boolean allowedUrl(String url){return false;}};
      ChatSession.get(this).manualAttention=true;getIntent().putExtra("openWindowAction","native-smoke");super.onCreate(state);
      handler.removeCallbacks(ticker);session.remove(sessionObserver);session.handler.removeCallbacks(session.tick);resumeChatUi();
      new Thread(this::exercise,"chat-download-card-fixture").start();
    }catch(Exception error){throw new IllegalStateException("Chat download card setup",error);}
  }
  <T>T ui(Callable<T> action)throws Exception{CompletableFuture<T> value=new CompletableFuture<>();handler.post(()->{try{value.complete(action.call());}catch(Throwable error){value.completeExceptionally(error);}});return value.get(10,TimeUnit.SECONDS);}
  <T>T visible(Callable<T> observe)throws Exception{long end=SystemClock.elapsedRealtime()+12000;while(SystemClock.elapsedRealtime()<end){T value=ui(observe);if(value!=null)return value;Thread.sleep(40);}throw new AssertionError("Actual chat download card did not update");}
  void check(String name,boolean value)throws Exception{checks.put(J.obj("name",name,"pass",value));if(!value)throw new AssertionError(name);}
  void drain()throws Exception{downloads.worker.submit(()->{}).get(10,TimeUnit.SECONDS);ui(()->null);downloads.worker.submit(()->{}).get(10,TimeUnit.SECONDS);ui(()->null);}
  void exercise(){
    try{
      GeckoWebView browser=remote;visible(()->active&&chatDownloadProgress!=null?Boolean.TRUE:null);
      for(boolean known:new boolean[]{true,false}){
        // Pause deliberately rejects late callbacks for a short interval. Wait
        // for that production guard instead of submitting another response early.
        visible(()->System.currentTimeMillis()>=downloads.ignoreUntil?Boolean.TRUE:null);
        DownloadResumeIntegrationActivity.BlockedBody body=new DownloadResumeIntegrationActivity.BlockedBody();bodies.add(body);
        WebResponse.Builder builder=new WebResponse.Builder("https://download-fixture.example/chat-progress.bin").statusCode(200).header("Content-Type","application/octet-stream").body(body);if(known)builder.header("Content-Length","5");
        ui(()->{downloads.acceptResponse(builder.build());ids.add(downloads.task.optString("id"));return null;});
        if(!body.entered.await(10,TimeUnit.SECONDS))throw new AssertionError("Actual production reader did not enter held body");
        JSONObject observation=visible(()->{
          ChatDownloadProgressUi card=chatDownloadProgress;android.graphics.Rect bounds=new android.graphics.Rect();
          if(!card.card.isShown()||!card.card.getGlobalVisibleRect(bounds)||bounds.isEmpty()||downloads.task.optLong("received")!=4||known&&(card.progress.isIndeterminate()||card.progress.getProgress()!=800)||!known&&!card.progress.isIndeterminate())return null;
          return J.obj("knownTotal",known,"received",downloads.task.optLong("received"),"total",downloads.task.optLong("total"),"progress",card.progress.getProgress(),"indeterminate",card.progress.isIndeterminate(),"width",bounds.width(),"height",bounds.height(),"amount",card.amount.getText().toString());
        });observations.put(observation);
        check("Actual streamed response drives visible "+(known?"known-size":"unknown-size")+" chat progress",observation.getLong("received")==4&&(known?observation.getInt("progress")==800:observation.getBoolean("indeterminate")));
        ui(()->{if(!chatDownloadProgress.primary.isEnabled()||!chatDownloadProgress.primary.performClick())throw new AssertionError("Native pause action unavailable");return null;});
        visible(()->"paused".equals(downloads.task.optString("state"))&&"已暂停".contentEquals(chatDownloadProgress.status.getText())?Boolean.TRUE:null);
        check("Card pause retains partial bytes and the browser "+known,downloads.task.optLong("received")==4&&remote==browser&&!downloads.active);
        body.release.countDown();drain();partials.add(downloads.temp);
      }
      visible(()->System.currentTimeMillis()>=downloads.ignoreUntil?Boolean.TRUE:null);
      byte[] bytes={81,82,83,84,85,86,87};WebResponse response=new WebResponse.Builder("https://download-fixture.example/chat-completed.bin").statusCode(200).header("Content-Type","application/octet-stream").body(new ByteArrayInputStream(bytes)).build();
      ui(()->{downloads.acceptResponse(response);ids.add(downloads.task.optString("id"));return null;});drain();
      visible(()->"saved".equals(downloads.task.optString("state"))&&chatDownloadProgress.card.isShown()&&"已保存".contentEquals(chatDownloadProgress.status.getText())&&chatDownloadProgress.progress.getProgress()==1000?Boolean.TRUE:null);
      published=ui(()->new JSONObject(downloads.task.toString()));byte[] actual;try(InputStream input=getContentResolver().openInputStream(Uri.parse(published.getString("uri")))){actual=J.read(input,1024);}
      check("Card completes only after actual destination publication",Arrays.equals(bytes,actual)&&remote==browser);
      result.put("status","passed").put("actualCardPauseClicks",2).put("browserRetained",true).put("cases",observations).put("savedBytes",bytes.length).put("finalProgress",1000);
    }catch(Throwable error){try{result.put("status","failed").put("error",error.toString());}catch(Exception ignored){}}
    finally{
      try{cleanup();result.put("ownedCleanupCompleted",true);}catch(Throwable error){try{result.put("status","failed").put("cleanupError",error.toString());}catch(Exception ignored){}}
      try{result.put("checks",checks).put("checkCount",checks.length());ui(()->{setResult(RESULT_OK,new Intent().putExtra("chatProgressResult",result.toString()));finish();return null;});}catch(Exception ignored){}
    }
  }
  void cleanup()throws Exception{
    for(DownloadResumeIntegrationActivity.BlockedBody body:bodies)body.release.countDown();
    ui(()->{downloads.destroy();chatDownloadProgress.close();return null;});if(!downloads.worker.awaitTermination(10,TimeUnit.SECONDS))throw new IOException("Owned download worker did not drain");
    if(published!=null)SavedFileDeletion.remove(this,published);for(File file:partials)if(file!=null)SealedFileIo.lease(file,()->{if(!file.delete()&&file.exists())throw new IOException("Owned partial cleanup failed");return null;});
    ui(()->{
      SharedPreferences tasks=getSharedPreferences("download-tasks",0);JSONArray rows=new JSONArray(tasks.getString("rows","[]")),kept=new JSONArray();for(int i=0;i<rows.length();i++)if(!ids.contains(rows.optJSONObject(i).optString("id")))kept.put(rows.optJSONObject(i));if(!tasks.edit().putString("rows",kept.toString()).commit())throw new IOException("Owned task cleanup failed");
      for(String id:ids)DownloadLibrary.get(this).getWritableDatabase().delete("tasks","slot=? AND id=?",new String[]{"7",id});
      JSONObject history=J.parse(prefs.getString("downloadHistory","{}"));JSONArray files=history.optJSONArray("files"),retained=new JSONArray();if(files!=null)for(int i=0;i<files.length();i++)if(!ids.contains(files.optJSONObject(i).optString("id")))retained.put(files.optJSONObject(i));history.put("files",retained);prefs.edit().putString("downloadHistory",history.toString()).commit();
      SharedPreferences.Editor restore=prefs.edit();for(Map.Entry<String,Object> item:oldPrefs.entrySet()){if(item.getValue()==null)restore.remove(item.getKey());else if(item.getValue() instanceof Boolean)restore.putBoolean(item.getKey(),(Boolean)item.getValue());else restore.putString(item.getKey(),(String)item.getValue());}if(!restore.commit())throw new IOException("Fixture settings restore failed");return null;
    });
    if(!oldEnvironment.optBoolean("created")){ContentValues restore=new ContentValues();restore.put("created",0);restore.put("environment_id",oldEnvironment.optString("environmentId"));if(ProfileCatalog.get(this).getWritableDatabase().update("environments",restore,"slot=7 AND environment_id=? AND generation=?",new String[]{environmentId,String.valueOf(oldEnvironment.optInt("generation"))})!=1)throw new IOException("Fixture owner changed during cleanup");}
  }
}
