package local.pocketchat;

import android.os.Looper;
import android.webkit.*;
import android.content.pm.PackageInfo;
import androidx.webkit.*;
import java.util.*;
import java.util.regex.*;
import org.json.*;

/** Installs only documented native settings and frame-start controls, before navigation. */
final class ChromiumFingerprintRuntime {
  static final String TOKEN="__POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__";
  static final WeakHashMap<WebView,Boolean> USED=new WeakHashMap<>();
  static final String[] UNSUPPORTED={"worker","serviceWorker","offscreenCanvas","timezone","hardware","fonts","language","tls","http2","webRtcNative","audioGetChannelData","audioWorklet","webglReadPixels"};
  static Prepared prepare(WebView view,ChromiumFingerprintSpec spec,String seed,String asset){
    if(Looper.myLooper()!=Looper.getMainLooper())throw new IllegalStateException("Chromium 指纹设置必须在界面线程应用");
    if(view==null||spec==null||seed==null||!seed.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Chromium 指纹身份无效");
    if(USED.containsKey(view))throw new IllegalStateException("指纹配置改变后必须创建新的网页实例");
    WebSettings settings=view.getSettings();
    if(!settings.getBlockNetworkLoads())throw new IllegalStateException("应用指纹前必须先阻断网页联网");
    boolean metadata=WebViewFeature.isFeatureSupported(WebViewFeature.USER_AGENT_METADATA),document=WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT);
    if(spec.protectedMode()&&!metadata)throw new IllegalStateException("当前 WebView 不支持原生客户端提示，请更新系统 WebView 或选择兼容模式");
    if(spec.scriptsRequired()&&!document)throw new IllegalStateException("当前 WebView 不支持文档开始保护，请更新系统 WebView");
    String script=spec.scriptsRequired()?script(asset,spec,seed):null;
    String original=settings.getUserAgentString(),version=version(original),ua=userAgent(original,spec.desktop());
    PackageInfo provider=WebViewCompat.getCurrentWebViewPackage(view.getContext());
    if(provider==null||provider.packageName==null||provider.versionName==null)throw new IllegalStateException("无法确认当前 WebView 组件");
    UserAgentMetadata wanted=null,accepted=null;ScriptHandler handler=null;
    // A view is single-policy even after a failed partial native installation.
    USED.put(view,Boolean.TRUE);
    try{
      if(metadata){
        UserAgentMetadata actual=WebSettingsCompat.getUserAgentMetadata(settings);
        UserAgentMetadata.Builder builder=new UserAgentMetadata.Builder(actual);
        if(spec.desktop())builder.setMobile(false).setPlatform("Linux").setPlatformVersion("").setModel("").setArchitecture("x86").setBitness(64).setWow64(false);
        wanted=builder.build();
      }
      settings.setUserAgentString(ua);
      if(!ua.equals(settings.getUserAgentString()))throw new IllegalStateException("Chromium 请求身份未被原生设置接收");
      if(metadata){WebSettingsCompat.setUserAgentMetadata(settings,wanted);accepted=WebSettingsCompat.getUserAgentMetadata(settings);if(!wanted.equals(accepted))throw new IllegalStateException("Chromium 客户端提示原生回读不一致");}
      if(script!=null)handler=WebViewCompat.addDocumentStartJavaScript(view,script,Collections.singleton("*"));
      JSONObject limits=new JSONObject();for(String field:UNSUPPORTED)limits.put(field,"unsupported");
      JSONObject receipt=J.obj("engine","chromium","providerPackage",provider.packageName,"providerVersion",provider.versionName,"chromiumVersion",version,
          "features",J.obj("documentStart",document,"userAgentMetadata",metadata),"requested",spec.json(),"nativeUserAgent",settings.getUserAgentString(),
          "nativeRequested",wanted==null?new JSONObject():metadata(wanted),"nativeReadback",accepted==null?new JSONObject():metadata(accepted),
          "documentStartRegistered",handler!=null,"scope","document-start-frames","unsupported",limits,"fingerprintProtectionVerified",false,
          "workerCoverageVerified",false,"pageObserved",false,"desktopIdentityScope",spec.desktop()?"desktop-request; JavaScript platform and physical hardware unchanged":"actual-provider-mobile");
      return new Prepared(handler,receipt);
    }catch(Exception failure){if(handler!=null)try{handler.remove();}catch(RuntimeException ignored){}throw new IllegalStateException("Chromium 指纹设置失败，网页继续保持断网",failure);}
  }
  static String version(String ua){if(ua==null)throw new IllegalArgumentException("当前 WebView 未提供真实请求身份");Matcher match=Pattern.compile("(?:Chrome|Chromium)/([0-9]+(?:\\.[0-9]+){3})").matcher(ua);if(!match.find())throw new IllegalArgumentException("无法识别真实 Chromium 版本");return match.group(1);}
  static String userAgent(String actual,boolean desktop){version(actual);return desktop?actual.replaceAll("\\(Linux; Android[^)]*\\)","(X11; Linux x86_64)").replace(" Mobile",""):actual;}
  static String script(String asset,ChromiumFingerprintSpec spec,String seed){
    if(asset==null||asset.length()>131072||asset.indexOf(TOKEN)<0||asset.indexOf(TOKEN)!=asset.lastIndexOf(TOKEN))throw new IllegalArgumentException("Chromium 文档开始脚本缺失或无效");
    return asset.replace(TOKEN,J.obj("schema",1,"seed",seed,"canvas",spec.canvas,"webgl",spec.webgl,"audio",spec.audio,"webrtc",spec.webrtc).toString());
  }
  static JSONObject metadata(UserAgentMetadata value){JSONArray brands=new JSONArray();for(UserAgentMetadata.BrandVersion brand:value.getBrandVersionList())brands.put(J.obj("brand",brand.getBrand(),"majorVersion",brand.getMajorVersion(),"fullVersion",brand.getFullVersion()));return J.obj("brands",brands,"fullVersion",value.getFullVersion(),"platform",value.getPlatform(),"platformVersion",value.getPlatformVersion(),"architecture",value.getArchitecture(),"model",value.getModel(),"mobile",value.isMobile(),"bitness",value.getBitness(),"wow64",value.isWow64());}
  static final class Prepared implements AutoCloseable {
    ScriptHandler handler;final JSONObject fields;
    Prepared(ScriptHandler handler,JSONObject receipt){this.handler=handler;fields=receipt;}
    JSONObject receipt(){return J.parse(fields.toString());}
    @Override public void close(){if(Looper.myLooper()!=Looper.getMainLooper())throw new IllegalStateException("Chromium 指纹清理必须在界面线程执行");ScriptHandler current=handler;handler=null;if(current!=null)current.remove();}
  }
}
