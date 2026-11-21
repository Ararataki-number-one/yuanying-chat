package local.pocketchat;
import android.net.*;
import java.io.*;
import java.net.*;
import java.util.concurrent.*;

/** Production route with controlled Android/service/connection doubles. Never opens a socket. */
public final class AiDiagnosticRouteHost {
  static int count;
  static void ok(String name,boolean result){if(!result)throw new AssertionError(name);count++;}
  interface Work{void run()throws Exception;}
  static boolean rejects(Work work)throws Exception{try{work.run();return false;}catch(IOException expected){return true;}}
  static NativeDownloadRouteHost.Fixture fixture(boolean internal,boolean vpn,String proxy)throws Exception{return new NativeDownloadRouteHost.Fixture(internal,vpn,proxy);}
  static AiDiagnosticRoute capture(NativeDownloadRouteHost.Fixture f)throws Exception{return AiDiagnosticRoute.capture(f.session,f.session.connectionEpoch);}
  public static void main(String[] args)throws Exception{
    for(String bad:new String[]{"http://proxy.example:8080","https://192.0.2.1:8080","socks://192.0.2.1:1080","http://user@192.0.2.1:8080","http://192.0.2.1:8080?a=b","http://192.0.2.1:8080#f","http://192.0.2.1:8080/path","http://127.1:8080","http://0177.0.0.1:8080","http://256.1.1.1:8080","http://[fe80::1%1]:8080","http://192.0.2.1:0","http://192.0.2.1:65536"})ok("unsupported proxy rejected: "+bad,rejects(()->AiDiagnosticRoute.numericHttpProxy(bad)));
    for(String good:new String[]{"http://192.0.2.1:8080","http://[2001:db8::1]:8080","http://[::ffff:192.0.2.1]:8080"}){Proxy p=AiDiagnosticRoute.numericHttpProxy(good);ok("numeric HTTP proxy creates resolved byte address",p.type()==Proxy.Type.HTTP&&((InetSocketAddress)p.address()).getAddress()!=null);}
    for(String bad:new String[]{"1.2.3.4::","1::2::3","1:2:3:4:5:6:7:8:9",":::1","fe80::1%eth0","127.0.0.1.example"})ok("invalid numeric grammar rejected",rejects(()->AiDiagnosticRoute.numericAddress(bad)));
    NativeDownloadRouteHost.Fixture f=fixture(false,false,"");final NativeDownloadRouteHost.Fixture direct=f;ok("plain direct is disabled",rejects(()->capture(direct)));
    f=fixture(false,false,"http://proxy.example:8080");final NativeDownloadRouteHost.Fixture domain=f;ok("hostname proxy disabled before any open",rejects(()->capture(domain))&&f.net.opens==0);
    String explicitProxy="http://192.0.2.4:8080";boolean vpnWithProxy=BrowserNetworkGuard.needsVpn(false,explicitProxy,true);
    ok("existing explicit proxy policy has priority over the standalone VPN requirement",!vpnWithProxy);
    f=fixture(false,vpnWithProxy,explicitProxy);Fake c=new Fake();f.net.connection=c;
    try(AiDiagnosticRoute route=capture(f)){
      ok("numeric proxy opens only frozen Network",route.open("https://fixture.invalid/v1/diagnose")==c&&f.net.opens==1&&f.net.lastProxy.type()==Proxy.Type.HTTP);
      ok("redirects are disabled",!c.getInstanceFollowRedirects());
      f.cm.active=new Network("wifi-B");ok("default Network replacement revokes",rejects(route::check));
      ok("revocation closes established request",c.closed.await(2,TimeUnit.SECONDS));
      f.cm.active=f.net;ok("revoked route cannot recover under old default",rejects(route::check));
    }
    ok("close unregisters callback",f.cm.unregisters==1&&f.cm.callback==null);
    f=fixture(false,true,"");c=new Fake();f.net.connection=c;
    try(AiDiagnosticRoute route=capture(f)){ok("VPN DNS and connection use exact verified Network",route.open("https://fixture.invalid/v1/diagnose")==c&&f.net.opens==1&&f.net.lastProxy==Proxy.NO_PROXY);f.net.unavailable=true;ok("bound failure never falls back",rejects(()->route.open("https://fixture.invalid/v1/diagnose"))&&f.net.opens==2);}
    f=fixture(false,true,"");f.session.guard.vpnIssue="excluded-route";final NativeDownloadRouteHost.Fixture badVpn=f;ok("VPN without full coverage rejected",rejects(()->capture(badVpn)));
    f=fixture(false,false,"http://192.0.2.4:8080");c=new Fake();f.net.connection=c;
    try(AiDiagnosticRoute route=capture(f)){route.open("https://fixture.invalid/v1/diagnose");f.cm.callback.onAvailable(new Network("wifi-B"));f.cm.callback.onAvailable(f.net);ok("transient callback replacement stays revoked",rejects(route::check));ok("callback disconnects connection",c.closed.await(2,TimeUnit.SECONDS));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){f.cm.links=new LinkProperties("changed-dns");ok("same Network changed DNS/routes rejected",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){f.session.browserDefaultNetwork.lost(f.net.toString());f.session.browserDefaultNetwork.initial(f.net.toString(),true,false);ok("same Network revision after loss rejected",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){f.session.connectionEpoch++;ok("epoch change blocks stream",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");final NativeDownloadRouteHost.Fixture stale=f;ok("preview epoch must remain exact",rejects(()->AiDiagnosticRoute.capture(stale.session,stale.session.connectionEpoch-1)));
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){ProfileCatalog.current=new EnvironmentSpec.Identity(2,8,f.session.environmentId);ok("catalog generation replacement rejected",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){f.session.prefs.proxy="http://192.0.2.5:8080";ok("proxy change never adopted",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){f.session.deleted=true;ok("deleted owner rejected",rejects(route::check));}
    f=fixture(false,false,"http://192.0.2.4:8080");
    try(AiDiagnosticRoute route=capture(f)){ChatSession.current=new ChatSession();ok("different owner rejected",rejects(route::check));}
    f=fixture(true,false,"");
    try(AiDiagnosticRoute route=capture(f)){ok("internal uses receipt and byte loopback",route.receipt==f.nativeNetwork.verifiedRoute&&((InetSocketAddress)route.proxy.address()).getAddress().isLoopbackAddress()&&((InetSocketAddress)route.proxy.address()).getPort()==f.nativeNetwork.verifiedRoute.proxy);f.nativeNetwork.invalidateVerifiedRoute();ok("receipt invalidation blocks internal request",rejects(route::check));}
    f=fixture(true,false,"");f.nativeNetwork.transport.freshAlive=false;final NativeDownloadRouteHost.Fixture staleReceipt=f;ok("stale service evidence blocks capture",rejects(()->capture(staleReceipt)));
    f=fixture(true,false,"");f.nativeNetwork.context.slot=3;final NativeDownloadRouteHost.Fixture cross=f;ok("cross profile core rejected",rejects(()->capture(cross)));
    f=fixture(false,false,"http://192.0.2.4:8080");f.cm.failRegister=true;final NativeDownloadRouteHost.Fixture unobservable=f;ok("unobservable default changes fail closed",rejects(()->capture(unobservable)));
    f=fixture(false,false,"http://192.0.2.4:8080");final NativeDownloadRouteHost.Fixture during=f;c=new Fake();f.net.connection=c;f.net.onOpen=()->during.cm.active=new Network("wifi-B");
    try(AiDiagnosticRoute route=capture(f)){ok("open-registration race detected",rejects(()->route.open("https://fixture.invalid/v1/diagnose")));ok("open-registration race connection closed",c.closed.await(2,TimeUnit.SECONDS));}
    f=fixture(false,false,"http://192.0.2.4:8080");c=new Fake();f.net.connection=c;
    try(AiDiagnosticRoute route=capture(f)){route.open("https://fixture.invalid/v1/diagnose");final Fake blocking=c;CompletableFuture<Boolean> read=CompletableFuture.supplyAsync(()->{try{blocking.getInputStream().read();return false;}catch(IOException expected){return true;}});ok("controlled read blocked",c.reading.await(2,TimeUnit.SECONDS));f.session.connectionEpoch++;ok("watcher closes blocked I/O",c.closed.await(3,TimeUnit.SECONDS)&&read.get(2,TimeUnit.SECONDS));}
    for(String target:new String[]{"https://fixture.invalid/api","http://fixture.invalid/api","https://user@fixture.invalid/api","https://fixture.invalid/api?secret=x","https://fixture.invalid/api#f","https://127.0.0.1/api"}){f=fixture(false,false,"http://192.0.2.4:8080");try(AiDiagnosticRoute route=capture(f)){ok("invalid gateway has no open",rejects(()->route.open(target))&&f.net.opens==0);}}
    f=fixture(false,false,"http://192.0.2.4:8080");c=new Fake();f.net.connection=c;
    AiDiagnosticRoute route=capture(f);route.open("https://fixture.invalid/v1/diagnose");route.released(c);route.close();ok("released connection removed",route.active.isEmpty()&&c.closed.getCount()==1);ok("closed route cannot reopen",rejects(()->route.open("https://fixture.invalid/v1/diagnose")));ok("closed watcher stopped",route.watcher.isShutdown());
    System.out.println("{\"status\":\"passed\",\"checks\":"+count+",\"actualNetworkExecution\":false,\"actualAndroidExecution\":false}");
  }
}
