package local.pocketchat;

import android.content.Context;
import android.net.Uri;
import android.os.Handler;

/** One URI lease covers the pending record, bytes, publication and durable record.
 * The worker may await main-thread callbacks; main never waits for this lease. */
final class SavedFilePublication {
  static void run(Context context,Uri uri,Handler main,Runnable prepare,
      SealedFileIo.Action<Void> writeAndPublish,Runnable commit,Runnable abort)throws Exception {
    if(android.os.Looper.myLooper()==android.os.Looper.getMainLooper())throw new IllegalStateException("Download publication must run off the main thread");
    SavedFileDeletion.lease(context,uri,()->{
      boolean committed=false,bytesPublished=false,preservePending=false;
      try{SavedFileDeletion.onMain(main,prepare);writeAndPublish.run();bytesPublished=true;SavedFileDeletion.onMain(main,commit);committed=true;}
      catch(Exception error){preservePending=bytesPublished&&unconfirmed(error);throw error;}
      finally{if(!committed&&!preservePending)abort.run();}
      return null;
    });
  }
  static boolean unconfirmed(Throwable error){for(Throwable cause=error;cause!=null;cause=cause.getCause())if(cause instanceof DownloadTasks.PersistenceFailure)return true;return false;}
  static boolean complete(DownloadTasks tasks,org.json.JSONObject row,java.io.File source,Runnable notification){
    if(!tasks.published(row,Uri.parse(row.optString("uri"))))return false;
    if(source!=null)source.delete();notification.run();return true;
  }
}
