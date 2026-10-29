package local.pocketchat;

import java.util.*;
import org.mozilla.geckoview.*;

public final class GeckoSitePermissionsHost {
  static int checks;
  static void check(String name,boolean pass){checks++;if(!pass)throw new AssertionError(name);}
  static final class Fixture {
    ChatSession owner=new ChatSession();MainActivity host=new MainActivity();GeckoWebView web=new GeckoWebView();
    GeckoSitePermissions backend;StorageController storage;
    Fixture(){
      ChatSession.instance=owner;host.session=owner;host.remote=web;owner.web=web;web.owner=owner;web.displayContext.host=host;
      web.locations.put(web.current,"https://chatgpt.com/c/fixture");web.ports.put(web.current,new Object());web.appearanceLoads.put(web.current,5L);
      ProfileCatalog.instance=new ProfileCatalog();ProfileCatalog.instance.stored=new EnvironmentSpec.Identity(1,owner.environmentGeneration,owner.environmentId);
      storage=web.runtime.storage;backend=new GeckoSitePermissions(web,host);
    }
    GeckoSession.PermissionDelegate.ContentPermission record(String origin,String third,String context,boolean privateMode,int type,int value){return new GeckoSession.PermissionDelegate.ContentPermission(origin,third,context,privateMode,type,value);}
  }
  static boolean rejectedWrite(Fixture f,SitePermissions.Scope scope,SitePermissions.Entry row,int value){try{f.backend.write(scope,row,value);return false;}catch(RuntimeException rejected){return true;}}
  public static void main(String[] args) {
    Fixture f=new Fixture();SitePermissions.Scope scope=f.backend.current();
    check("live page scope",scope!=null&&scope.valid());
    List<List<SitePermissions.Entry>> output=new ArrayList<>();List<String> failures=new ArrayList<>();
    f.backend.read(scope,output::add,failures::add);
    check("exact query origin/context/mode and main handler",f.storage.origin.equals("https://chatgpt.com")&&f.storage.context==null&&!f.storage.privateMode&&f.storage.pending.handler==f.owner.handler);
    GeckoSession.PermissionDelegate.ContentPermission nativeRow=f.record("https://chatgpt.com",null,null,false,1,1);
    f.storage.pending.complete(Arrays.asList(nativeRow,f.record("https://com",null,null,false,1,1),f.record("https://chatgpt.com",null,"",false,1,1),f.record("https://chatgpt.com",null,null,true,1,1)));
    check("inherited origin and other namespace filtered",output.size()==1&&output.get(0).size()==1&&failures.isEmpty());
    SitePermissions.Entry row=output.get(0).get(0);
    check("native object retained",row.nativePermission==nativeRow);
    f.backend.write(scope,row,SitePermissions.DENY);
    check("one native dispatch under identity transaction",f.storage.writes==1&&f.storage.written==nativeRow&&f.storage.writtenValue==2&&ProfileCatalog.instance.transactions==1);
    check("allow never dispatched",rejectedWrite(f,scope,row,SitePermissions.ALLOW)&&f.storage.writes==1);
    nativeRow.uri="https://other.test";
    check("wrapped row cannot disguise another native principal",rejectedWrite(f,scope,row,SitePermissions.DENY)&&f.storage.writes==1);
    nativeRow.uri="https://chatgpt.com";
    ProfileCatalog.instance.changeBeforeTransaction=true;
    check("catalog identity race aborts dispatch",rejectedWrite(f,scope,row,SitePermissions.DENY)&&f.storage.writes==1);

    f=new Fixture();scope=f.backend.current();output.clear();failures.clear();
    f.backend.read(scope,output::add,failures::add);f.host.active=false;f.owner.uiVisible=false;
    f.storage.pending.complete(Collections.emptyList());
    check("paused activity late read rejected",output.isEmpty()&&failures.equals(Arrays.asList("stale")));
    check("paused activity has no current scope",f.backend.current()==null);

    f=new Fixture();scope=f.backend.current();long lifetime=scope.lifetime;
    f.web.current.open=false;check("closed session",f.backend.current()==null);
    f.web.current.open=true;f.web.identityPolicyRevision++;
    check("same object reopened lifetime invalidated",f.backend.current().session==scope.session&&f.backend.current().lifetime==lifetime+1&&!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.web.appearanceLoads.put(f.web.current,6L);
    check("same URL reload invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.web.locations.put(f.web.current,"https://chatgpt.com/c/next");
    check("same-origin SPA location invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.web.ports.put(f.web.current,new Object());check("new bridge invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.owner.lastDocumentId="new-document";check("document ID invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.owner.navigationEpoch++;check("navigation invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.web.current.settings.contextId="";check("null versus empty context invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();scope=f.backend.current();f.web.current.settings.privateMode=true;check("private namespace invalidates",!scope.matches(f.backend.current()));
    f=new Fixture();f.web.pendingLoads.add(f.web.current);check("pending navigation rejected",f.backend.current()==null);
    f=new Fixture();f.web.crashed.add(f.web.current);check("crashed page rejected",f.backend.current()==null);
    f=new Fixture();f.web.visible=false;check("unobserved page rejected",f.backend.current()==null);
    f=new Fixture();f.web.shown=false;check("native hub hides browser rejected",f.backend.current()==null);
    f=new Fixture();f.web.ready=false;check("not running rejected",f.backend.current()==null);
    f=new Fixture();f.web.displayContext.host=new MainActivity();check("old host rejected",f.backend.current()==null);
    f=new Fixture();f.host.destroyed=true;check("destroyed activity rejected",f.backend.current()==null);
    f=new Fixture();ChatSession.instance=new ChatSession();check("retired ChatSession rejected",f.backend.current()==null);
    f=new Fixture();ProfileCatalog.instance.stored=new EnvironmentSpec.Identity(1,2,"11111111-1111-1111-1111-111111111111");check("slot reuse UUID rejected",f.backend.current()==null);
    f=new Fixture();ProfileCatalog.instance.stored=new EnvironmentSpec.Identity(1,3,f.owner.environmentId);check("reset generation rejected",f.backend.current()==null);
    f=new Fixture();ProfileCatalog.instance.unavailable=true;check("unknown catalog fail closed",f.backend.current()==null);
    f=new Fixture();f.web.locations.put(f.web.current,"http://chatgpt.com");check("non HTTPS rejected",f.backend.current()==null);
    f=new Fixture();scope=f.backend.current();failures.clear();f.backend.read(scope,rows->{throw new AssertionError("invalid accepted");},failures::add);
    f.storage.pending.complete(Arrays.asList(f.record("https://chatgpt.com","http://third.test",null,false,8,1)));
    check("invalid third-party namespace rejected",failures.equals(Arrays.asList("invalid")));
    f=new Fixture();scope=f.backend.current();failures.clear();f.backend.read(scope,rows->{throw new AssertionError("oversize accepted");},failures::add);
    f.storage.pending.complete(Collections.nCopies(129,f.record("https://chatgpt.com",null,null,false,1,1)));
    check("query bound retained",failures.equals(Arrays.asList("invalid")));
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"applicationAndGeckoBoundaryDoubles\":true,\"actualGeckoExecution\":false,\"actualAndroidExecution\":false}");
  }
}
