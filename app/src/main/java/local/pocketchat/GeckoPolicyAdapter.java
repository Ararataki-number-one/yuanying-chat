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
  static JSONObject capabilityStatus(){return J.obj(
    "engine",GeckoWebView.VERSION,"ua","official-session-mobile-or-desktop","viewport","native-mobile-preserving-v1523-fit",
    "desktopWorkerHttpUa","sdk-default-not-independent-session-desktop-ua","fullDesktopUaConsistency",false,
    "locales","sdk-request-readback-only-language-region-normalization-predicted-page-and-header-observation-required","timezone","system-or-native-rfp-no-independent-override",
    "canvas","no-custom-native-control","webgl","no-custom-native-control","audio","no-custom-native-control","fonts","no-custom-native-control",
    "rfp","extension-native-setting-acknowledgment-not-full-api-proof");}
  static String summary(){return "页面显示：Firefox 手机版 / 电脑版，保留手机自适应布局\n电脑版后台 Worker 请求可能仍使用手机版 UA；不保证完整桌面 UA 一致\n语言：SDK 请求与网页观测分开记录\n时区：系统时区；强化模式采用 Firefox 原生策略\nCanvas / WebGL / 音频 / 字体：没有自定义伪装接口\n强化模式：设置回读不代表网页兼容性或全部 API 已验证";}
}
