package local.pocketchat;

import org.json.*;
import org.mozilla.geckoview.*;
import java.util.Arrays;

/** Only controls already present in the shipped official GeckoView 157 API. */
final class GeckoPolicyAdapter {
  static void applyRuntime(GeckoRuntime runtime,int level){
    if(runtime==null)return;
    ContentBlocking.Settings policy=runtime.getSettings().getContentBlocking();
    policy.setAntiTracking(level>0?ContentBlocking.AntiTracking.DEFAULT|ContentBlocking.AntiTracking.FINGERPRINTING|ContentBlocking.AntiTracking.CRYPTOMINING:ContentBlocking.AntiTracking.NONE);
  }
  static void applySession(GeckoSession session,boolean desktop,int level){
    GeckoSessionSettings settings=session.getSettings();
    settings.setUserAgentMode(desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE);
    // Preserve v1.5.23 phone-fit layout even when requesting the desktop UA.
    settings.setViewportMode(GeckoSessionSettings.VIEWPORT_MODE_MOBILE);
    settings.setUseTrackingProtection(level>0);
  }
  static boolean applyLocales(GeckoRuntime runtime,String[] locales){
    if(runtime==null)return false;
    runtime.getSettings().setLocales(locales.clone());
    return Arrays.equals(locales,runtime.getSettings().getLocales());
  }
  /** Public SDK setting objects are not renderer, UID or partition observations. */
  static JSONObject runtimeCapabilityStatus(GeckoRuntime runtime,int androidApi){
    JSONObject values=new JSONObject();
    JSONObject result=J.obj("schema",1,"source","sdk-runtime-settings-object",
      "isolatedRenderingRequested",androidApi>=29,"appZygoteRequested",false,
      "runtimeAvailable",runtime!=null,"settings",values,
      "processEvidence","not-collected","siteIsolationEvidence","not-collected",
      "statePartitionEvidence","not-collected","sandboxEvidence","not-collected",
      "processUidVerified",false,"siteIsolationVerified",false,"statePartitionVerified",false,"fullSandboxVerified",false);
    String[] names={"isolatedProcessEnabled","fissionEnabled","webContentIsolationStrategy","cookieBehavior","cookieBehaviorPrivateMode","cookieOptInPartitioning","cookieOptInPartitioningPrivateMode"};
    for(String name:names)try{values.put(name,J.obj("status","unavailable","value",JSONObject.NULL));}catch(JSONException ignored){}
    if(runtime==null)return result;
    final GeckoRuntimeSettings settings;
    try{settings=runtime.getSettings();if(settings==null)return result;}catch(Exception|LinkageError ignored){return result;}
    runtimeSetting(values,names[0],()->settings.getIsolatedProcessEnabled(),false);
    runtimeSetting(values,names[1],()->settings.getFissionEnabled(),true);
    runtimeSetting(values,names[2],()->settings.getWebContentIsolationStrategy(),true);
    runtimeSetting(values,names[3],()->settings.getContentBlocking().getCookieBehavior(),false);
    runtimeSetting(values,names[4],()->settings.getContentBlocking().getCookieBehaviorPrivateMode(),false);
    runtimeSetting(values,names[5],()->settings.getCookieBehaviorOptInPartitioning(),false);
    runtimeSetting(values,names[6],()->settings.getCookieBehaviorOptInPartitioningPBM(),false);
    return result;
  }
  private static void runtimeSetting(JSONObject values,String name,java.util.function.Supplier<Object> read,boolean nullable){
    try{Object value=read.get();values.put(name,J.obj("status",value==null&&nullable?"sdk-default-unobserved":value==null?"unavailable":"sdk-value","value",value==null?JSONObject.NULL:value));}
    catch(Exception|LinkageError ignored){/* Fixed unavailable state; do not export exception text. */}
  }
  static String runtimeCapabilitySummary(JSONObject status){
    JSONObject values=status.optJSONObject("settings");
    StringBuilder out=new StringBuilder("原生运行配置（SDK 设置对象）\n隔离渲染请求：").append(status.optBoolean("isolatedRenderingRequested")?"Android 10 及以上请求启用":"当前 Android 版本未请求启用");
    String[] keys={"isolatedProcessEnabled","fissionEnabled","webContentIsolationStrategy","cookieBehavior","cookieBehaviorPrivateMode","cookieOptInPartitioning","cookieOptInPartitioningPrivateMode"};
    String[] labels={"隔离进程 SDK 值","站点隔离 Fission SDK 值","网页隔离策略 SDK 值","Cookie 策略 SDK 值","隐私窗口 Cookie 策略 SDK 值","Cookie 自选分区 SDK 值","隐私窗口 Cookie 自选分区 SDK 值"};
    for(int i=0;i<keys.length;i++){JSONObject item=values==null?null:values.optJSONObject(keys[i]);String state=item==null?"unavailable":item.optString("status");out.append("\n").append(labels[i]).append("：");
      if("sdk-default-unobserved".equals(state))out.append("沿用 SDK 默认；实际值未观测");
      else if("sdk-value".equals(state))out.append(String.valueOf(item.opt("value")));
      else out.append("未取得");
    }
    return out.append("\n这些值仅来自当前 SDK 设置对象；没有采集当前渲染进程 UID、跨站进程或存储分区证据，不代表完整沙箱已验证。").toString();
  }
  static JSONObject capabilityStatus(){return J.obj(
    "engine",GeckoWebView.VERSION,"ua","official-session-mobile-or-desktop","viewport","native-mobile-preserving-v1523-fit",
    "desktopWorkerHttpUa","sdk-default-not-independent-session-desktop-ua","fullDesktopUaConsistency",false,
    "locales","sdk-request-readback-only-language-region-normalization-predicted-page-and-header-observation-required","timezone","system-or-native-rfp-no-independent-override",
    "canvas","no-custom-native-control","webgl","no-custom-native-control","audio","no-custom-native-control","fonts","no-custom-native-control",
    "rfp","extension-native-setting-acknowledgment-not-full-api-proof");}
  static String summary(){return "页面显示：Firefox 手机版 / 电脑版，保留手机自适应布局\n电脑版后台 Worker 请求可能仍使用手机版 UA；不保证完整桌面 UA 一致\n语言：SDK 请求与网页观测分开记录\n时区：系统时区；强化模式采用 Firefox 原生策略\nCanvas / WebGL / 音频 / 字体：没有自定义伪装接口\n强化模式：设置回读不代表网页兼容性或全部 API 已验证";}
}
