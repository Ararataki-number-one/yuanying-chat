package org.mozilla.geckoview;
import java.util.List;
public class StorageController {
  public GeckoResult<List<GeckoSession.PermissionDelegate.ContentPermission>> getPermissions(String origin,String context,boolean privateMode){return null;}
  public void setPermission(GeckoSession.PermissionDelegate.ContentPermission entry,int value){}
}
