package local.pocketchat;

import android.app.Application;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Process;
import android.util.Log;
import com.cefrium.Cefrium;

/** Registers Chromium's Java Activity lifecycle before any Activity is created. */
public final class CefriumSetupProvider extends ContentProvider {
  private static boolean ready;

  static boolean isReady() { return ready; }

  @Override public boolean onCreate() {
    Context context = getContext();
    if (context == null || Build.VERSION.SDK_INT < 29
        || !context.getPackageName().equals(Application.getProcessName())) return true;
    try {
      if (Process.myUid() == context.getApplicationInfo().uid
          && ChromiumEntry.managed(context) && ChromiumModuleInstaller.installed(context)) {
        // The SDK's standard provider also prefetches libcef. Keep native startup
        // and all engine networking behind the selected environment's route grant.
        Cefrium.setupProcess(context);
        ready = true;
      }
    } catch (RuntimeException | LinkageError | AssertionError unavailable) {
      Log.w("PocketChat", "Chromium process setup failed", unavailable);
    }
    return true;
  }

  @Override public Cursor query(Uri uri, String[] projection, String selection,
      String[] selectionArgs, String sortOrder) { throw new UnsupportedOperationException(); }
  @Override public String getType(Uri uri) { throw new UnsupportedOperationException(); }
  @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
  @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
    throw new UnsupportedOperationException();
  }
  @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
    throw new UnsupportedOperationException();
  }
}
