package local.pocketchat;

import android.net.Uri;
import org.mozilla.geckoview.*;
import java.io.IOException;
import java.util.List;
import org.json.JSONObject;

/** A temporary display in the existing environment runtime. No chat delegates or bridge. */
final class ExitIpPageSession {
  static final String URL="https://ip123.in/zh/";
  final GeckoWebView web;final ChatSession owner;final GeckoSession original,aux;final GeckoRuntime runtime;
  final GeckoWebView.ExitIpPageListener listener;final String environmentId,route;final int slot,generation;
  final long connection,navigation,policy,protectionToken,protectionGeneration;final Object port;
  final NativeNetwork.ExitRouteReceipt receipt;boolean closed;String location=URL;
  ExitIpPageSession(GeckoWebView web,GeckoWebView.ExitIpPageListener listener){
    this.web=web;owner=web.owner;this.listener=listener;original=web.current;runtime=web.runtime;environmentId=owner.environmentId;slot=Profiles.slot(owner.context);generation=owner.environmentGeneration;
    route=owner.networkIdentity();connection=owner.connectionEpoch;navigation=owner.navigationEpoch;policy=web.identityPolicyRevision;port=web.ports.get(original);
    protectionToken=web.nativeProtection.token();protectionGeneration=web.nativeProtection.generation();receipt=owner.internalNetwork()?NativeNetwork.get(owner.context).verifiedRoute:null;
    aux=new GeckoSession(new GeckoSessionSettings.Builder().userAgentMode(web.desktop?GeckoSessionSettings.USER_AGENT_MODE_DESKTOP:GeckoSessionSettings.USER_AGENT_MODE_MOBILE).viewportMode(GeckoSessionSettings.VIEWPORT_MODE_MOBILE).build());
    GeckoPolicyAdapter.applySession(aux,web.desktop,owner.privacy.level());
    aux.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
      @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){
        boolean allow=fresh()&&target(request.uri);if(!allow)message("当前地址或环境保护已变化，可返回聊天");return GeckoResult.fromValue(allow?AllowOrDeny.ALLOW:AllowOrDeny.DENY);
      }
      @Override public void onLocationChange(GeckoSession s,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){if(!fresh())return;location=url;message("正在打开 ip123.in…");}
      @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){return GeckoResult.fromValue(null);}
      @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){message("IP 查询网站暂不可用，可返回聊天");return GeckoResult.fromValue(null);}
    });
    aux.setProgressDelegate(new GeckoSession.ProgressDelegate(){
      @Override public void onPageStop(GeckoSession s,boolean success){message(success?"ip123.in · 当前环境线路":"IP 查询网站未能加载，可返回聊天");}
    });
    aux.setContentDelegate(new GeckoSession.ContentDelegate(){
      @Override public void onCloseRequest(GeckoSession s){if(web.exitIpPage==ExitIpPageSession.this)web.closeExitIpPage();}
      @Override public void onCrash(GeckoSession s){message("IP 查询页面已退出，可返回聊天");}
      @Override public void onKill(GeckoSession s){message("IP 查询页面已关闭，可返回聊天");}
      @Override public void onExternalResponse(GeckoSession s,WebResponse response){if(response.body!=null)try{response.body.close();}catch(IOException ignored){}message("此查询页不下载文件，可返回聊天");}
    });
    aux.setPromptDelegate(new GeckoSession.PromptDelegate(){
      @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession s,FilePrompt prompt){return GeckoResult.fromValue(prompt.dismiss());}
    });
    aux.setPermissionDelegate(new GeckoSession.PermissionDelegate(){
      @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){return GeckoResult.fromValue(SitePermissions.DENY);}
      @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] permissions,Callback callback){callback.reject();}
      @Override public void onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){callback.reject();}
    });
  }
  static boolean target(String value){try{Uri u=Uri.parse(value);return "https".equalsIgnoreCase(u.getScheme())&&"ip123.in".equalsIgnoreCase(u.getHost())&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443);}catch(Exception invalid){return false;}}
  static String unavailable(GeckoWebView web){
    ChatSession s=web.owner;
    if(web.destroyed||s.deleted||ChatSession.peek()!=s||s.web!=web||!web.ready||web.runtime==null||web.surface==null||web.current==null||!web.current.isOpen()||!web.hasVisibleDocument()||web.ports.get(web.current)==null||web.failed)return "请先显示当前环境的聊天页，再查询 IP。";
    if(!MainActivity.chatUrl(web.getUrl())||LoginPagePolicy.login(web.getUrl())||s.audit.requestIdentityPageSelected())return "请先返回原聊天页，再查询 IP。";
    if(!s.networkReady||s.offline||s.connecting||s.recoveryScheduled||!s.guard.allowed()||s.appliedIdentity.isEmpty()||!s.appliedIdentity.equals(s.networkIdentity()))return "当前环境线路尚未获准，请先恢复连接。";
    if(web.routePort==null||!web.routePrepared||!s.privacy.canNavigate()||!web.protectionAllowsNetwork()||!web.getSettings().policyAcknowledged||!web.nativeProtection.confirmed()||web.nativeProtection.level()!=s.privacy.level())return "当前浏览器保护尚未确认，请稍后再查询。";
    if(!s.internalNetwork()&&s.prefs.getString("proxy","").trim().isEmpty()&&!s.guard.requiresVpn())return "请先为当前环境配置应用代理或受保护的 VPN 线路。";
    try{JSONObject row=ProfileCatalog.get(s.context).item(Profiles.slot(s.context));if(!ProfileCatalog.get(s.context).available(Profiles.slot(s.context))||!s.environmentId.equals(row.optString("environmentId"))||s.environmentGeneration!=row.optInt("generation",-1))return "当前环境已改变，请重新打开。";}catch(Exception unavailable){return "当前环境身份暂不可用。";}
    return "";
  }
  boolean fresh(){
    if(closed||web.exitIpPage!=this||web.runtime!=runtime||web.current!=original||!original.isOpen()||owner.connectionEpoch!=connection||owner.navigationEpoch!=navigation||web.identityPolicyRevision!=policy||web.ports.get(original)!=port
        ||web.nativeProtection.token()!=protectionToken||web.nativeProtection.generation()!=protectionGeneration||!route.equals(owner.networkIdentity())||!unavailable(web).isEmpty())return false;
    if(receipt!=null){NativeNetwork n=NativeNetwork.get(owner.context);return receipt==n.verifiedRoute&&n.transport!=null&&receipt.matches(n,n.transport.state)&&n.connectionAdmission().usable();}
    return !owner.internalNetwork();
  }
  void message(String value){if(fresh())listener.changed(value);}
  final Runnable watch=new Runnable(){public void run(){if(!fresh()){if(web.exitIpPage==ExitIpPageSession.this)web.closeExitIpPage();return;}owner.handler.postDelayed(this,250);}};
}
