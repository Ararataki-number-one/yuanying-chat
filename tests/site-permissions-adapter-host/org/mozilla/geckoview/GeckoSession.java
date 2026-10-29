package org.mozilla.geckoview;
public class GeckoSession {
  public boolean open=true;public Settings settings=new Settings();
  public boolean isOpen(){return open;}public Settings getSettings(){return settings;}
  public static class Settings {public String contextId;public boolean privateMode;public String getContextId(){return contextId;}public boolean getUsePrivateMode(){return privateMode;}}
  public interface PermissionDelegate {
    class ContentPermission {
      public String uri,thirdPartyOrigin,contextId;public boolean privateMode;public int permission,value;
      public ContentPermission(String uri,String third,String context,boolean privateMode,int type,int value) {
        this.uri=uri;thirdPartyOrigin=third;contextId=context;this.privateMode=privateMode;permission=type;this.value=value;
      }
    }
  }
}
