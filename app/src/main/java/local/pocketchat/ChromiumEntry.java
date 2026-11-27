package local.pocketchat;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import java.io.IOException;

/** The base app depends on a verified Android split, never on a Cefrium class. */
final class ChromiumEntry {
  static final String FEATURE_ACTIVITY="local.pocketchat.CefriumBrowserActivity";
  private static final String NETWORK_CONFIGURATION_REQUIRED="请先检查此环境的网络配置，再打开 Chromium。";
  private static final String DELIVERY="local.pocketchat.CHROMIUM_DELIVERY";
  private static final String SLOT="local.pocketchat.chromium.slot";
  private static final String GENERATION="local.pocketchat.chromium.generation";
  private static final String ENVIRONMENT="local.pocketchat.chromium.environment";
  private ChromiumEntry() {}

  static boolean managed(Context context){
    try{
      Bundle metadata=context.getPackageManager().getApplicationInfo(context.getPackageName(),PackageManager.GET_META_DATA).metaData;
      return metadata!=null&&Boolean.TRUE.equals(metadata.get(DELIVERY));
    }catch(PackageManager.NameNotFoundException unavailable){return false;}
  }
  static String networkIssue(Context context){
    try{
      CefriumRoutePolicy.Selection configured=CefriumRoutePolicy.selection(context.getSharedPreferences("chat",Context.MODE_PRIVATE).getAll());
      if(configured==null)return NETWORK_CONFIGURATION_REQUIRED;
      if(configured.mode==CefriumRoutePolicy.Mode.VPN&&Build.VERSION.SDK_INT<33)
        return "强制 VPN 的线路核验需要 Android 13 或更新版本。";
      return "";
    }catch(RuntimeException unavailable){return NETWORK_CONFIGURATION_REQUIRED;}
  }
  static boolean open(Activity host,String url,Intent request){
    if(!ChromiumModuleInstaller.installed(host))return false;
    try{
      EnvironmentSpec.Identity expected=ProfileCatalog.get(host).identity(Profiles.slot(host));
      if(request!=null&&request.getBooleanExtra(EnvironmentOverviewUi.DIRECT,false)
          &&(expected.slot!=request.getIntExtra(EnvironmentOverviewUi.SLOT,-1)
             ||expected.generation!=request.getIntExtra(EnvironmentOverviewUi.GENERATION,-1)
             ||!expected.environmentId.equals(request.getStringExtra(EnvironmentOverviewUi.ID))))return false;
      Intent next=new Intent().setClassName(host,FEATURE_ACTIVITY);
      next.putExtra(SLOT,expected.slot).putExtra(GENERATION,expected.generation).putExtra(ENVIRONMENT,expected.environmentId);
      if(BrowserAddressPolicy.allowed(url))next.putExtra("url",url);
      host.startActivity(next);
      return true;
    }catch(IOException|ActivityNotFoundException|SecurityException unavailable){return false;}
  }
  static String profileName(EnvironmentSpec.Identity identity){
    return "env-"+identity.environmentId+"-"+identity.generation;
  }
  static EnvironmentSpec.Identity identity(Context context,Intent intent)throws IOException{
    if(intent==null)throw new IOException("没有可打开的环境");
    int slot=intent.getIntExtra(SLOT,-1);
    if(slot<0||slot>=Profiles.MAX)throw new IOException("浏览器环境无效");
    EnvironmentSpec.Identity actual=ProfileCatalog.get(context).identity(slot);
    if(actual.generation!=intent.getIntExtra(GENERATION,-1)||!actual.environmentId.equals(intent.getStringExtra(ENVIRONMENT)))
      throw new IOException("环境已变化，请重新打开");
    if(!BrowserPreferences.startBrowser(Profiles.context(context,slot)))throw new IOException("此环境未绑定 Chromium，请返回环境列表");
    return actual;
  }
}
