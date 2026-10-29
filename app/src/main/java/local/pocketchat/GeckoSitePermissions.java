package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.StorageController;

/** Handler-confined SDK boundary. Native permission objects never leave this process or become JSON. */
final class GeckoSitePermissions implements SitePermissions.Backend {
  private final GeckoWebView web;
  private final MainActivity host;
  GeckoSitePermissions(GeckoWebView web,MainActivity host) {this.web=web;this.host=host;}

  @Override public SitePermissions.Scope current() {
    ChatSession owner=web.owner;GeckoSession session=web.current;
    if(ChatSession.peek()!=owner||!host.active||!owner.uiVisible||!EnvironmentIdentityUi.current(host,owner)||host.remote!=web
        ||web.displayContext.getBaseContext()!=host||web.destroyed||owner.deleted||!web.ready||web.runtime==null||session==null||!session.isOpen()
        ||web.crashed.contains(session)||web.pendingLoads.contains(session)||owner.navigating||!web.isShown()||!web.hasVisibleDocument())return null;
    String origin=SitePermissions.origin(web.locations.get(session));
    if(origin.isEmpty())return null;
    // Slot reuse/reset/deletion can precede this process receiving its shutdown signal.
    try {
      EnvironmentSpec.Identity identity=ProfileCatalog.get(owner.context).identity(Profiles.slot(owner.context));
      if(identity.generation!=owner.environmentGeneration||!identity.environmentId.equals(owner.environmentId))return null;
    }catch(Exception unavailable){return null;}
    // configure() advances identityPolicyRevision on activation and close/open of the same session.
    // appearanceLoads advances even on a same-URL reload; the full location also fences SPA changes.
    return new SitePermissions.Scope(owner.environmentId,owner.environmentGeneration,Profiles.slot(owner.context),web,
        web.runtime,session,web.ports.get(session),web.identityPolicyRevision,
        web.appearanceLoads.getOrDefault(session,0L),owner.navigationEpoch,owner.lastDocumentId+"\n"+web.locations.get(session),
        origin,session.getSettings().getContextId(),session.getSettings().getUsePrivateMode());
  }
  @Override public void read(SitePermissions.Scope scope,Consumer<List<SitePermissions.Entry>> success,Consumer<String> failure) {
    if(scope==null||!scope.matches(current())){failure.accept("stale");return;}
    // StorageController requires a Looper/Handler thread, not a bare executor thread.
    web.runtime.getStorageController().getPermissions(scope.origin,scope.contextId,scope.privateMode)
        .withHandler(web.owner.handler).accept(records->{
          if(!scope.matches(current())){failure.accept("stale");return;}
          if(records==null||records.size()>SitePermissions.MAX_ROWS){failure.accept("invalid");return;}
          ArrayList<SitePermissions.Entry> rows=new ArrayList<>();
          for(GeckoSession.PermissionDelegate.ContentPermission record:records) {
            if(record==null){failure.accept("invalid");return;}
            SitePermissions.Entry row=new SitePermissions.Entry(record,record.uri,record.thirdPartyOrigin,record.contextId,
                record.privateMode,record.permission,record.value);
            // The SDK may return inherited permissions. Do not edit a parent/other-context record.
            if(!row.origin.equals(scope.origin)||!Objects.equals(row.contextId,scope.contextId)||row.privateMode!=scope.privateMode)continue;
            if(!row.belongs(scope)){failure.accept("invalid");return;}
            rows.add(row);
          }
          success.accept(rows);
        },error->failure.accept("unavailable"));
  }
  @Override public void write(SitePermissions.Scope scope,SitePermissions.Entry entry,int value) {
    if(scope==null||!scope.matches(current())||!entry.belongs(scope)||!entry.permits(value)
        ||!(entry.nativePermission instanceof GeckoSession.PermissionDelegate.ContentPermission))throw new IllegalStateException("stale-permission");
    GeckoSession.PermissionDelegate.ContentPermission nativeRecord=(GeckoSession.PermissionDelegate.ContentPermission)entry.nativePermission;
    SitePermissions.Entry nativeFields=new SitePermissions.Entry(nativeRecord,nativeRecord.uri,nativeRecord.thirdPartyOrigin,
        nativeRecord.contextId,nativeRecord.privateMode,nativeRecord.permission,nativeRecord.value);
    if(!nativeFields.belongs(scope)||!entry.sameKey(nativeFields)||entry.value!=nativeFields.value)throw new IllegalStateException("permission-object-mismatch");
    try {
      ProfileCatalog.get(web.owner.context).withIdentity(new EnvironmentSpec.Identity(scope.slot,scope.generation,scope.environmentId),()->{
        if(!scope.matches(current()))throw new IllegalStateException("stale-permission");
        StorageController storage=web.runtime.getStorageController();
        // Dispatch while deletion/reset cannot change this catalog identity. The existing maintenance
        // protocol still owns stopping the old runtime; this dispatch is not a durable success receipt.
        storage.setPermission(nativeRecord,value);
        return null;
      });
    }catch(Exception unavailable){throw new IllegalStateException("permission-write-unavailable");}
  }
  @Override public void later(Runnable action,long delay) {web.owner.handler.postDelayed(action,delay);}
  @Override public void cancel(Runnable action) {web.owner.handler.removeCallbacks(action);}
}
