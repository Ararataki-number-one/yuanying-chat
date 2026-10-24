package org.mozilla.geckoview;

import java.util.List;

/** Host-only delegate slots. This does not navigate, schedule, or emulate Gecko. */
public class GeckoSession {
  public boolean open=true;
  private ProgressDelegate progress;
  private NavigationDelegate navigation;
  public boolean isOpen(){return open;}
  public ProgressDelegate getProgressDelegate(){return progress;}
  public NavigationDelegate getNavigationDelegate(){return navigation;}
  public void setProgressDelegate(ProgressDelegate value){progress=value;}
  public void setNavigationDelegate(NavigationDelegate value){navigation=value;}
  public static class SessionState {}
  public interface PermissionDelegate {class ContentPermission {}}
  public interface ProgressDelegate {
    class SecurityInformation {}
    default void onPageStart(GeckoSession session,String uri){}
    default void onPageStop(GeckoSession session,boolean success){}
    default void onProgressChange(GeckoSession session,int progress){}
    default void onSecurityChange(GeckoSession session,SecurityInformation value){}
    default void onSessionStateChange(GeckoSession session,SessionState value){}
  }
  public interface NavigationDelegate {
    class LoadRequest {}
    default void onLocationChange(GeckoSession session,String uri,List<PermissionDelegate.ContentPermission> permissions,Boolean gesture){}
    default void onCanGoBack(GeckoSession session,boolean value){}
    default void onCanGoForward(GeckoSession session,boolean value){}
    default GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession session,LoadRequest request){return null;}
    default GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession session,LoadRequest request){return null;}
    default GeckoResult<GeckoSession> onNewSession(GeckoSession session,String uri){return null;}
    default GeckoResult<String> onLoadError(GeckoSession session,String uri,WebRequestError error){return null;}
  }
}
