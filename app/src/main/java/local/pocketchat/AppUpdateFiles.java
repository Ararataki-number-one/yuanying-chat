package local.pocketchat;

import android.content.*;
import android.content.pm.*;
import android.os.Build;
import java.io.*;
import java.util.*;

final class AppUpdateFiles {
  static long code(PackageInfo info){return Build.VERSION.SDK_INT>=28?info.getLongVersionCode():info.versionCode;}
  static int flags(){return Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES;}
  static Set<String> signers(PackageInfo info){Set<String> out=new HashSet<>();if(info==null)return out;Signature[] signatures=Build.VERSION.SDK_INT>=28?(info.signingInfo==null?null:info.signingInfo.getApkContentsSigners()):info.signatures;if(signatures!=null)for(Signature signature:signatures)out.add(AppUpdatePolicy.hash(signature.toByteArray()));return out;}
  static long installed(Context c){try{return code(c.getPackageManager().getPackageInfo(c.getPackageName(),0));}catch(Exception e){return Long.MAX_VALUE;}}
  static void archive(Context c,File file,long versionCode,String version)throws IOException {
    PackageManager pm=c.getPackageManager();PackageInfo candidate=pm.getPackageArchiveInfo(file.getAbsolutePath(),flags()),current;
    try{current=pm.getPackageInfo(c.getPackageName(),flags());}catch(Exception e){throw new IOException("无法读取当前安装版本",e);}
    if(candidate==null||!c.getPackageName().equals(candidate.packageName)||code(candidate)!=versionCode||!version.equals(candidate.versionName)||candidate.applicationInfo==null||(candidate.applicationInfo.flags&ApplicationInfo.FLAG_DEBUGGABLE)!=0)throw new IOException("更新文件版本或应用信息不符");
    Set<String> expected=signers(current),actual=signers(candidate);if(expected.isEmpty()||!expected.equals(actual))throw new IOException("更新签名与当前应用不同，已停止安装");
    if(Build.VERSION.SDK_INT>=24&&candidate.applicationInfo.minSdkVersion>Build.VERSION.SDK_INT)throw new IOException("这次更新不支持当前 Android 版本");
  }
}
