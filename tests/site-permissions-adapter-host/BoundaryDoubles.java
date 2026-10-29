package local.pocketchat;

import java.util.*;
import org.mozilla.geckoview.*;

/** Pure JVM app edges; no Android or Gecko runtime is executed. */
class MainActivity {boolean active=true,destroyed;ChatSession session;GeckoWebView remote;}
class ChatSession {
  static ChatSession instance;static ChatSession peek(){return instance;}
  boolean deleted,navigating,uiVisible=true;int environmentGeneration=2;long navigationEpoch=3;
  String environmentId="70208cc2-508b-43c3-95c0-01d6d84fa0b5",lastDocumentId="document-a";
  Object context=new Object();FakeHandler handler=new FakeHandler();GeckoWebView web;
}
class FakeHandler {void postDelayed(Runnable action,long delay){}void removeCallbacks(Runnable action){}}
class HostContext {Object host;Object getBaseContext(){return host;}}
class GeckoWebView {
  ChatSession owner;GeckoSession current=new GeckoSession();GeckoRuntime runtime=new GeckoRuntime();
  boolean destroyed,ready=true,visible=true,shown=true;long identityPolicyRevision=4;
  HostContext displayContext=new HostContext();
  Set<GeckoSession> crashed=new HashSet<>(),pendingLoads=new HashSet<>();
  Map<GeckoSession,String> locations=new HashMap<>();Map<GeckoSession,Object> ports=new HashMap<>();
  Map<GeckoSession,Long> appearanceLoads=new HashMap<>();
  boolean hasVisibleDocument(){return visible;}
  boolean isShown(){return shown;}
}
class EnvironmentSpec {
  static class Identity {
    final int slot,generation;final String environmentId;
    Identity(int slot,int generation,String id){this.slot=slot;this.generation=generation;environmentId=id;}
  }
}
class ProfileCatalog {
  static ProfileCatalog instance=new ProfileCatalog();static ProfileCatalog get(Object context){return instance;}
  EnvironmentSpec.Identity stored;boolean unavailable,changeBeforeTransaction;int transactions;
  EnvironmentSpec.Identity identity(int slot)throws java.io.IOException {
    if(unavailable||stored==null)throw new java.io.IOException("unavailable");return stored;
  }
  interface IdentityAction<T>{T run()throws Exception;}
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception {
    transactions++;
    if(changeBeforeTransaction)stored=new EnvironmentSpec.Identity(expected.slot,expected.generation+1,expected.environmentId);
    EnvironmentSpec.Identity now=identity(expected.slot);
    if(now.slot!=expected.slot||now.generation!=expected.generation||!now.environmentId.equals(expected.environmentId))throw new java.io.IOException("stale");
    return action.run();
  }
}
class Profiles {static int slot(Object context){return 1;}}
class EnvironmentIdentityUi {
  static boolean current(MainActivity host,ChatSession owner){return !host.destroyed&&host.session==owner&&!owner.deleted;}
}
