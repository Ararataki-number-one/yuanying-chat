package local.pocketchat;

import android.app.DownloadManager;
import android.content.*;

public class AppUpdateReceiver extends BroadcastReceiver {
  @Override public void onReceive(Context c,Intent intent){if(!DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction()))return;AppUpdateManager manager=AppUpdateManager.get(c);if(intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID,-1)!=manager.downloadId())return;PendingResult pending=goAsync();manager.refresh(pending::finish);}
}
