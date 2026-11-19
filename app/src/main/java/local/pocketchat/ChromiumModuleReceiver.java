package local.pocketchat;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Unexported receiver for Android package installation status. */
public final class ChromiumModuleReceiver extends BroadcastReceiver {
  @Override public void onReceive(Context context, Intent status) {
    ChromiumModuleInstaller.receive(context, status);
  }
}
