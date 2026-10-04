package local.pocketchat;

import android.content.Context;

/** Display the installed package version, never a manually duplicated label. */
final class AppVersion {
  static String name(Context context){try{String value=context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionName;return value==null?"未知":value;}catch(Exception error){return "未知";}}
}
