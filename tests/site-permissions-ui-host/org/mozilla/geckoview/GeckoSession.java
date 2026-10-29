package org.mozilla.geckoview;
public class GeckoSession {
  public boolean isOpen(){return false;}
  public Settings getSettings(){return null;}
  public static class Settings {public String getContextId(){return null;}public boolean getUsePrivateMode(){return false;}}
  public interface PermissionDelegate {
    class ContentPermission {public String uri,thirdPartyOrigin,contextId;public boolean privateMode;public int permission,value;}
  }
}
