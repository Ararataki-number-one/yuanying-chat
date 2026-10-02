package local.pocketchat;

import android.os.Bundle;
import android.net.Uri;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Local intercepted HTTPS fixtures only. No account traffic or real messages. */
public class NetworkShieldTestActivity extends ContinuityFixtureActivity {
  final JSONArray checks=new JSONArray();int tries;final AtomicInteger workerPermitted=new AtomicInteger();
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  @Override public void onCreate(Bundle b){getSharedPreferences("chat",0).edit().clear().putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).putString("conversation",ORIGIN+"c/network-shield").commit();super.onCreate(b);handler.postDelayed(()->ready(),200);}
  void ready(){if((session.navigating||session.entries.length()!=2)&&tries++<80){handler.postDelayed(()->ready(),100);return;}
    check("Protected fixture remains usable",!session.navigating&&session.entries.length()==2);
    check("Service worker request guard is installed",session.guard.workerProtection);
    check("Worker file and content access are disabled",!session.guard.workers.getAllowFileAccess()&&!session.guard.workers.getAllowContentAccess());
    check("Proxy mode does not require a second system VPN",!BrowserNetworkGuard.needsVpn(false,"http://127.0.0.1:7890",true));
    check("Internal fixed exit does not require a second VPN",!BrowserNetworkGuard.needsVpn(true,"",true));
    check("Phone-network mode requires VPN by default",BrowserNetworkGuard.needsVpn(false,"",true));
    NativeNetwork dnsNetwork=NativeNetwork.get(this);dnsNetwork.settings=J.obj("exitHost","127.0.0.1","exitPort",9);dnsNetwork.names=new ArrayList<>();JSONObject dns=dnsNetwork.config(false,false).optJSONObject("dns");
    check("Bootstrap DNS has only encrypted IP-literal endpoints",dns.optJSONArray("default-nameserver").optString(0).startsWith("https://223.5.5.5/")&&dns.optJSONArray("default-nameserver").optString(1).startsWith("https://223.6.6.6/"));
    session.prefs.edit().putInt("privacyLevel",0).commit();check("Compatibility mode retains fixed-exit website DNS",dnsNetwork.config(false,false).optJSONObject("dns").optJSONArray("nameserver").optString(0).endsWith("#FixedExit"));session.prefs.edit().putInt("privacyLevel",1).commit();
    for(String host:new String[]{"localhost","LOCALHOST.","sub.localhost","printer.local","router.lan","router.home.arpa","127.0.0.1","127.1","2130706433","0x7f000001","0177.0.0.1","10.0.0.1","172.16.1.1","192.168.1.1","169.254.169.254","100.64.0.1","0.0.0.0","[::1]","[fe80::1]","[fc00::1]","[::ffff:127.0.0.1]"})check("Local destination blocked: "+host,BrowserNetworkGuard.localHost(host));
    check("Public hostname remains allowed",BrowserNetworkGuard.publicHttps(Uri.parse("https://chatgpt.com/c/example")));
    check("Public IPv4 remains allowed",!BrowserNetworkGuard.localHost("1.1.1.1"));
    check("Public IPv6 remains allowed",!BrowserNetworkGuard.localHost("2606:4700:4700::1111"));
    check("Cleartext resource is denied",!BrowserNetworkGuard.publicHttps(Uri.parse("http://example.com/")));
    check("Credential-bearing URL is denied",!BrowserNetworkGuard.publicHttps(Uri.parse("https://user:pass@example.com/")));
    session.guard.setBlocked(true);
    check("Connection gate blocks both page and worker loads",remote.getSettings().getBlockNetworkLoads()&&session.guard.workers.getBlockNetworkLoads());
    check("Public worker request denied before connection",session.guard.intercept(Uri.parse("https://guard.fixture.invalid/probe"))!=null);
    session.guard.setBlocked(false);
    check("Confirmed connection reopens both gates",!remote.getSettings().getBlockNetworkLoads()&&!session.guard.workers.getBlockNetworkLoads());
    remote.evaluateJavascript("(()=>({connectionHidden:navigator.connection===undefined&&navigator.webkitConnection===undefined,early:!!window.__pocketPrivacy}))()",raw->{JSONObject d=J.parse(raw);check("Network type is hidden before page scripts",d.optBoolean("connectionHidden")&&d.optBoolean("early"));remote.evaluateJavascript("window.batteryResult='pending';typeof navigator.getBattery==='function'?navigator.getBattery().then(()=>window.batteryResult='allowed',e=>window.batteryResult=e.name):window.batteryResult='absent'",null);handler.postDelayed(()->battery(),200);});
  }
  void battery(){remote.evaluateJavascript("window.batteryResult",raw->{check("Battery state cannot be read",raw.contains("NotAllowedError")||raw.contains("absent"));
    boolean saved=session.privacy.earlyInstalled;session.privacy.earlyInstalled=false;check("Standard mode refuses missing document-start protection",!session.privacy.canNavigate());session.privacy.earlyInstalled=saved;
    session.prefs.edit().putBoolean("requireExternalVpn",true).commit();check("Actual phone mode detects absent system VPN",session.guard.requiresVpn()&&!session.guard.vpnActive());session.invalidateConnection();session.openConnection(false,false);check("Missing VPN never enables page or background networking",!session.networkReady&&session.guard.blocked&&remote.getSettings().getBlockNetworkLoads()&&session.guard.workers.getBlockNetworkLoads());
    session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.manualAttention=false;session.guard.setBlocked(false);session.networkReady=true;workerSetup();
  });}
  WebResourceResponse response(String text,String mime){return new WebResourceResponse(mime,"UTF-8",200,"OK",Collections.singletonMap("Service-Worker-Allowed","/"),new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));}
  WebResourceResponse workerResponse(){return response("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('message',e=>{fetch('/probe?phase='+e.data).then(r=>r.text().then(t=>({status:r.status,text:t}))).then(d=>e.source.postMessage(d)).catch(()=>e.source.postMessage({status:0,text:'blocked'}));});","application/javascript");}
  void workerSetup(){ServiceWorkerController.getInstance().setServiceWorkerClient(new ServiceWorkerClient(){@Override public WebResourceResponse shouldInterceptRequest(WebResourceRequest r){WebResourceResponse deny=session.guard.intercept(r.getUrl());if(deny!=null)return deny;if(!"guard.fixture.invalid".equals(r.getUrl().getHost()))return BrowserNetworkGuard.denied();if(r.getUrl().getPath().equals("/worker.js"))return workerResponse();workerPermitted.incrementAndGet();return response("fixture-only","text/plain");}});
    remote.setWebViewClient(new WebViewClient(){@Override public WebResourceResponse shouldInterceptRequest(WebView w,WebResourceRequest r){WebResourceResponse deny=session.guard.intercept(r.getUrl());if(deny!=null)return deny;if(!"guard.fixture.invalid".equals(r.getUrl().getHost()))return BrowserNetworkGuard.denied();if(r.getUrl().getPath().equals("/worker.js"))return workerResponse();return response("<!doctype html><script>window.swState='pending';navigator.serviceWorker.addEventListener('message',e=>window.swResult=e.data);navigator.serviceWorker.register('/worker.js').then(()=>navigator.serviceWorker.ready).then(r=>{window.sw=r.active;window.swState='ready';}).catch(e=>window.swState='failed:'+e.name);</script>","text/html");}});
    remote.loadUrl("https://guard.fixture.invalid/index.html");tries=0;pollReady();
  }
  void pollReady(){remote.evaluateJavascript("window.swState||'pending'",raw->{if(raw.contains("ready")){check("Real service worker registers on local HTTPS fixture",true);phase(false);return;}if(tries++<80){handler.postDelayed(()->pollReady(),100);return;}check("Real service worker registers on local HTTPS fixture",false);write(raw);});}
  void phase(boolean blocked){session.guard.setBlocked(blocked);int before=workerPermitted.get();remote.evaluateJavascript("window.swResult=null;window.sw.postMessage('"+(blocked?"blocked":"allowed")+"')",null);tries=0;pollPhase(blocked,before);}
  void pollPhase(boolean blocked,int before){remote.evaluateJavascript("window.swResult",raw->{JSONObject result=J.parse(raw);if(result.has("status")){check(blocked?"Real worker cannot fetch while disconnected":"Real worker fetch uses the shared request guard",blocked?result.optInt("status")!=200&&workerPermitted.get()==before:result.optInt("status")==200&&result.optString("text").equals("fixture-only")&&workerPermitted.get()>before);if(!blocked)phase(true);else {session.guard.setBlocked(false);vpnStart();}return;}if(tries++<80){handler.postDelayed(()->pollPhase(blocked,before),100);return;}check("Worker response completes in phase "+blocked,false);write(raw);});}
  void vpnStart(){session.prefs.edit().putBoolean("requireExternalVpn",true).commit();startService(new android.content.Intent(this,ShieldFixtureVpnService.class));tries=0;pollVpn();}
  void pollVpn(){if(!session.guard.vpnActive()&&tries++<40){handler.postDelayed(()->pollVpn(),80);return;}check("Real test-only VPN is detected",session.guard.vpnActive());if(!session.guard.vpnActive()){startService(new android.content.Intent(this,ShieldFixtureVpnService.class).setAction("STOP"));write("Test VPN did not establish: "+ShieldFixtureVpnService.error);return;}session.guard.setBlocked(false);session.networkReady=true;check("Confirmed VPN permits new requests",session.guard.allowed());startService(new android.content.Intent(this,ShieldFixtureVpnService.class).setAction("STOP"));tries=0;pollVpnLoss();}
  void pollVpnLoss(){if((session.guard.vpnActive()||!session.guard.blocked)&&tries++<50){handler.postDelayed(()->pollVpnLoss(),80);return;}check("VPN removal pauses page and worker without reconnecting directly",!session.guard.vpnActive()&&session.guard.blocked&&!session.networkReady&&remote.getSettings().getBlockNetworkLoads()&&session.guard.workers.getBlockNetworkLoads());check("Native downloads cannot fall back after VPN loss",downloadBlocked());session.prefs.edit().putBoolean("requireExternalVpn",false).commit();write("");}
  boolean downloadBlocked(){try{downloads.route();return false;}catch(Exception expected){return true;}}
  void write(String detail){try{J.write(new File(getFilesDir(),"network-shield-results.json"),J.obj("checks",checks,"fixtureDetail",detail,"webView",WebView.getCurrentWebViewPackage().versionName,"scope","Intercepted fixtures; no production account or VPN reputation assessment").toString(2));}catch(Exception ignored){}}
}
