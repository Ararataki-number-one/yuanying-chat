package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;
import org.mozilla.geckoview.*;

/** Handler-confined reader of the existing SDK store. It never dispatches setPermission. */
final class GeckoContentPermissions implements ContentPermissionDecisions.Backend {
  final GeckoWebView web;final ContentPermissionDecisions decisions;private boolean nativeReadPending;
  GeckoContentPermissions(GeckoWebView web){this.web=web;decisions=new ContentPermissionDecisions(this);}
  GeckoResult<Integer> request(GeckoSession session,GeckoSession.PermissionDelegate.ContentPermission permission){
    GeckoResult<Integer> result=new GeckoResult<>();
    ContentPermissionDecisions.Request request=permission==null?null:new ContentPermissionDecisions.Request(session,permission,
      permission.uri,permission.thirdPartyOrigin,permission.contextId,permission.privateMode,permission.permission,permission.value);
    decisions.request(request,value->{try{result.complete(value);}catch(RuntimeException ignored){}});return result;
  }
  void close(){decisions.close();}
  @Override public SitePermissions.Scope current(Object source){
    ChatSession owner=web.owner;GeckoSession session=web.current;
    if(source!=session||session==null||ChatSession.peek()!=owner||owner.web!=web||web.destroyed||owner.deleted||!web.enabled||!web.ready
        ||web.runtime==null||!session.isOpen()||web.crashed.contains(session)||web.pendingLoads.contains(session)||owner.navigating||!web.hasVisibleDocument())return null;
    String location=web.locations.get(session),origin=SitePermissions.origin(location);if(origin.isEmpty())return null;
    int slot=Profiles.slot(owner.context);
    try{EnvironmentSpec.Identity identity=ProfileCatalog.get(owner.context).identity(slot);
      if(identity.generation!=owner.environmentGeneration||!identity.environmentId.equals(owner.environmentId))return null;
    }catch(Exception unavailable){return null;}
    return new SitePermissions.Scope(owner.environmentId,owner.environmentGeneration,slot,web,web.runtime,session,web.ports.get(session),
      web.identityPolicyRevision,web.appearanceLoads.getOrDefault(session,0L),owner.navigationEpoch,
      owner.lastDocumentId+"\n"+location+"\n"+owner.identityAuditAppliedRevision()+"\n"+owner.connectionEpoch,
      origin,session.getSettings().getContextId(),session.getSettings().getUsePrivateMode());
  }
  @Override public void read(SitePermissions.Scope scope,Consumer<List<SitePermissions.Entry>> success,Consumer<String> failure){
    if(scope==null||!scope.matches(current(scope.session))){failure.accept("stale");return;}
    // A deadline cannot cancel the SDK read. Keep the actual native slot until its callback.
    if(nativeReadPending){failure.accept("busy");return;}nativeReadPending=true;
    try{web.runtime.getStorageController().getPermissions(scope.origin,scope.contextId,scope.privateMode).withHandler(web.owner.handler).accept(records->{
      nativeReadPending=false;
      if(!scope.matches(current(scope.session))){failure.accept("stale");return;}
      if(records==null||records.size()>SitePermissions.MAX_ROWS){failure.accept("invalid");return;}
      ArrayList<SitePermissions.Entry> rows=new ArrayList<>();
      for(GeckoSession.PermissionDelegate.ContentPermission record:records){
        if(record==null){failure.accept("invalid");return;}
        rows.add(new SitePermissions.Entry(record,record.uri,record.thirdPartyOrigin,record.contextId,record.privateMode,record.permission,record.value));
      }
      success.accept(rows);
    },error->{nativeReadPending=false;failure.accept("unavailable");});}
    catch(RuntimeException|LinkageError unavailable){/* Dispatch status is unknown; retain the native slot until browser retirement. */failure.accept("unavailable");}
  }
  @Override public void later(Runnable action,long delay){web.owner.handler.postDelayed(action,delay);}
  @Override public void cancel(Runnable action){web.owner.handler.removeCallbacks(action);}
}
