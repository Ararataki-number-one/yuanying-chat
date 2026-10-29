package org.mozilla.geckoview;
import java.util.*;
public class StorageController {
  public List<GeckoSession.PermissionDelegate.ContentPermission> records=new ArrayList<>();
  public String origin,context;public boolean privateMode;public int reads,writes,writtenValue;
  public GeckoSession.PermissionDelegate.ContentPermission written;
  public GeckoResult<List<GeckoSession.PermissionDelegate.ContentPermission>> pending;
  public GeckoResult<List<GeckoSession.PermissionDelegate.ContentPermission>> getPermissions(String origin,String context,boolean privateMode) {
    reads++;this.origin=origin;this.context=context;this.privateMode=privateMode;
    pending=new GeckoResult<>();return pending;
  }
  public void setPermission(GeckoSession.PermissionDelegate.ContentPermission entry,int value){writes++;written=entry;writtenValue=value;}
}
