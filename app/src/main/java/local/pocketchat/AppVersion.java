package local.pocketchat;

import android.content.Context;

/** Display the installed package version, never a manually duplicated label. */
final class AppVersion {
  static String name(Context context){try{String value=context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionName;return value==null?"未知":value;}catch(Exception error){return "未知";}}
  static android.os.Bundle metadata(Context context){try{return context.getPackageManager().getApplicationInfo(context.getPackageName(),android.content.pm.PackageManager.GET_META_DATA).metaData;}catch(Exception unavailable){return null;}}
  static String channel(Context context){android.os.Bundle metadata=metadata(context);String value=metadata==null?"":metadata.getString("local.pocketchat.UPDATE_CHANNEL","");return AppUpdatePolicy.channel(value)?value:AppUpdatePolicy.versionChannel(name(context));}
  static int candidateNumber(Context context){android.os.Bundle metadata=metadata(context);return metadata==null?0:metadata.getInt("local.pocketchat.CANDIDATE_NUMBER",0);}
  static String display(Context context){return AppUpdatePolicy.display(name(context),channel(context),candidateNumber(context));}
}
