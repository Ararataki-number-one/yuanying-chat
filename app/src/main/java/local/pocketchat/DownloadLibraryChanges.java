package local.pocketchat;

import android.content.Context;
import android.net.Uri;
import android.os.*;
import java.util.concurrent.atomic.AtomicLong;

/** A coalesced invalidation, never a file permission or publication receipt. */
final class DownloadLibraryChanges {
  static final AtomicLong revision=new AtomicLong();
  static final Handler main=new Handler(Looper.getMainLooper());
  static Runnable pending;
  static Uri uri(Context context){return Uri.parse("content://"+context.getPackageName()+".saved-downloads/library-changed");}
  static synchronized void changed(Context context){
    revision.incrementAndGet();if(pending!=null)return;Context app=Profiles.global(context);
    pending=()->{synchronized(DownloadLibraryChanges.class){pending=null;}try{app.getContentResolver().notifyChange(uri(app),null);}catch(RuntimeException ignored){}};
    main.postDelayed(pending,180);
  }
}
