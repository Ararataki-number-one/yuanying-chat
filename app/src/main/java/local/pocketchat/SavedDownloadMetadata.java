package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

/** Bounded, worker-only legacy metadata. Failure is cached, never reported as zero. */
final class SavedDownloadMetadata {
  static final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"saved-file-metadata");t.setDaemon(true);return t;});
  static final Handler main=new Handler(Looper.getMainLooper());
  static final AtomicInteger watchers=new AtomicInteger();static final AtomicBoolean scanning=new AtomicBoolean();
  static final AtomicLong discoveryRevision=new AtomicLong();
  static final AtomicReference<CancellationSignal> query=new AtomicReference<>();
  static volatile boolean discovered;
  static final class Watch implements AutoCloseable {
    boolean closed;Watch(Context c){watchers.incrementAndGet();discoveryRevision.incrementAndGet();discovered=false;discover(c);}
    public void close(){if(closed)return;closed=true;if(watchers.decrementAndGet()==0){CancellationSignal signal=query.get();if(signal!=null)workerCancel(signal);}}
  }
  static void workerCancel(CancellationSignal signal){new Thread(()->{try{signal.cancel();}catch(RuntimeException ignored){}},"metadata-cancel").start();}
  static Watch watch(Context context){return new Watch(Profiles.global(context));}
  static void added(Context context,JSONObject row){if(row==null||DownloadMetadataValues.checked(row))return;discoveryRevision.incrementAndGet();discovered=false;if(watchers.get()>0)discover(context);}
  static void discover(Context context){
    if(discovered||!scanning.compareAndSet(false,true))return;Context app=Profiles.global(context);
    final long request=discoveryRevision.get();worker.execute(()->{boolean complete=false;try{DownloadLibrary library=DownloadLibrary.get(app);long cursor=0;
      while(watchers.get()>0){JSONArray page=library.metadataPage(cursor,16);if(page.length()==0){complete=true;break;}boolean changed=false;
        for(int i=0;i<page.length()&&watchers.get()>0;i++){JSONObject candidate=page.optJSONObject(i);cursor=candidate.optLong("metadataRowId");candidate.remove("metadataRowId");if(!DownloadMetadataValues.checked(candidate))changed|=load(app,candidate,false);}
        if(changed)DownloadLibrary.changed(app);
      }
    }catch(Exception ignored){/* A later explicit entry or retry may resume discovery. */}finally{discovered=complete&&request==discoveryRevision.get();scanning.set(false);if(request!=discoveryRevision.get()&&watchers.get()>0)discover(app);}});
  }
  static void retry(Context context,JSONObject selected,BooleanSupplier current,Consumer<JSONObject> result){
    JSONObject snapshot=J.parse(selected.toString());if(!snapshot.has("slot"))DownloadTasks.put(snapshot,"slot",Profiles.slot(context));Context app=Profiles.global(context);
    worker.execute(()->{JSONObject updated=null;try{if(current.getAsBoolean()){boolean changed=load(app,snapshot,true);if(changed)DownloadLibrary.changed(app);updated=DownloadLibrary.get(app).saved(snapshot);}}catch(Exception ignored){}
      JSONObject finalRow=updated;main.post(()->{if(current.getAsBoolean())result.accept(finalRow);});});
  }
  static String ownerStamp(Context context,int slot){JSONObject item=ProfileCatalog.get(context).item(slot),stamp=new JSONObject();for(String key:new String[]{"environmentId","generation","created","deleting","resetting"})DownloadTasks.put(stamp,key,item.opt(key));return DownloadTaskRevisions.value(stamp);}
  static boolean load(Context context,JSONObject candidate,boolean force)throws Exception{
    if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("Saved metadata must run off main");
    DownloadLibrary library=DownloadLibrary.get(context);String owner=ownerStamp(context,candidate.optInt("slot"));
    return SavedFileDeletion.lease(context,Uri.parse(candidate.optString("uri")),()->{
      JSONObject row=library.saved(candidate);if(row==null||!force&&DownloadMetadataValues.checked(row))return false;
      if(!owner.equals(ownerStamp(context,row.optInt("slot"))))return false;
      JSONObject result=J.parse(row.toString());Uri uri=Uri.parse(row.optString("uri"));long known=DownloadMetadataValues.bytes(row);
      JSONObject facts=describe(context,uri,true);long bytes=DownloadMetadataValues.bytes(facts);
      if("cancelled".equals(facts.optString("metadataResult")))return false;
      if(known>=0&&"published-copy".equals(row.optString("sizeSource")))bytes=known;
      for(String key:new String[]{"actualName","actualMime"})if(facts.has(key))DownloadTasks.put(result,key,facts.opt(key));
      DownloadMetadataValues.checked(result,bytes,known>=0&&"published-copy".equals(row.optString("sizeSource"))?"published-copy":facts.optString("sizeSource","provider-size"),bytes>=0?"known":facts.optString("metadataResult","unknown"));
      if(!owner.equals(ownerStamp(context,row.optInt("slot"))))return false;
      return library.metadataUpdate(row,result);
    });
  }
  /** Runs inside publication's worker/URI lease too; no content scan or guessed path. */
  static JSONObject describe(Context context,Uri uri){return describe(context,uri,false);}
  static JSONObject describe(Context context,Uri uri,boolean cancellable){
    if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("Saved metadata must run off main");
    JSONObject facts=new JSONObject();long bytes=-1;String source="provider-size",outcome="unknown";
    try{
      if((context.getPackageName()+".saved-downloads").equals(uri.getAuthority())){
        File file=SavedDownloadProvider.resolve(context,uri);if(!file.isFile())throw new FileNotFoundException();bytes=file.length();source="owned-stat";DownloadTasks.put(facts,"actualName",file.getName());
      }else{
        CancellationSignal signal=new CancellationSignal();if(cancellable)query.set(signal);
        try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null,signal)){
          if(cursor!=null&&cursor.moveToFirst()){
            int size=cursor.getColumnIndex(OpenableColumns.SIZE),name=cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
            if(size>=0&&!cursor.isNull(size)&&cursor.getType(size)==Cursor.FIELD_TYPE_INTEGER){long value=cursor.getLong(size);if(value>=0)bytes=value;}
            if(name>=0&&!cursor.isNull(name)){String value=cursor.getString(name);if(value!=null&&!value.isEmpty()&&value.length()<=16384)DownloadTasks.put(facts,"actualName",value);}
          }
        }finally{if(cancellable)query.compareAndSet(signal,null);if(signal.isCanceled())DownloadTasks.put(facts,"metadataResult","cancelled");}
        if(signal.isCanceled())return facts;
        // Some providers expose SIZE=0 for a missing file. Confirm the zero-byte
        // object can actually be opened; never read its contents to measure it.
        if(bytes==0)try(ParcelFileDescriptor descriptor=context.getContentResolver().openFileDescriptor(uri,"r")){if(descriptor==null)throw new FileNotFoundException();}
      }
      try{String mime=context.getContentResolver().getType(uri);if(mime!=null&&!mime.isEmpty())DownloadTasks.put(facts,"actualMime",mime);}catch(RuntimeException ignored){}
    }catch(Exception unavailable){bytes=-1;outcome="unavailable";}
    if("cancelled".equals(facts.optString("metadataResult")))return facts;
    if(bytes>=0)DownloadTasks.put(facts,"savedBytes",bytes,"sizeSource",source);DownloadTasks.put(facts,"metadataResult",bytes>=0?"known":outcome);return facts;
  }
}
