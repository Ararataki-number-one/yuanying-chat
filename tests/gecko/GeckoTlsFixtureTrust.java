package local.pocketchat;

import android.content.Context;
import android.os.*;
import java.io.IOException;
import java.util.*;
import java.util.function.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Only the disposable TLS integration package can observe and await test-CA import. */
final class GeckoTlsFixtureTrust {
  static final String EXTENSION="tls-fixture-trust@pocketchat.local",HOST="pockettlsfixturetrust",LOCATION="resource://android/assets/tls-fixture-trust/";
  final GeckoWebView view;final GeckoRuntime runtime;final GeckoTlsFixtureTrustState state;
  final MainActivity host;final String runtimeNonce,processNonce;final int slot;
  final Consumer<Throwable> failure;final Runnable admitted;
  WebExtension extension;WebExtension.Port port;boolean closed,failed;

  GeckoTlsFixtureTrust(Context context,GeckoWebView view,JSONObject build,String run,String invocation,String leaf,
      JSONObject input,LongSupplier deadline,Runnable admitted,Consumer<Throwable> failure)throws Exception{
    ui();this.view=view;runtime=view.runtime;this.admitted=admitted;this.failure=failure;
    slot=Profiles.slot(context);
    Class<?> activity=context.getClass();
    boolean expectedActivity=(slot==0&&activity==GeckoEnvironmentPolicyIntegrationActivity.class)
      ||(slot==1&&activity==GeckoTlsAcceptanceActivity.Profile1.class)||(slot==2&&activity==GeckoTlsAcceptanceActivity.Profile2.class)
      ||(slot==6&&(activity==GeckoTlsCpuIpComboIntegrationActivity.class
        ||activity==GeckoIpTimeZoneIntegrationActivity.class||activity==GeckoCpuIpComboIntegrationActivity.class));
    if(!"local.pocketchat.test".equals(context.getPackageName())||!expectedActivity||runtime==null||!leaf.equals(input.opt("leafDerSha256")))throw new SecurityException("FixtureTrust:scope");
    JSONObject policy=view.owner.tls.status();
    host=(MainActivity)context;runtimeNonce=policy.getString("runtimeNonce");processNonce=policy.getString("processNonce");
    JSONObject binding=GeckoTlsFixtureTrustState.obj("sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",run,"caseNonce",invocation,"bootCaseNonce",invocation,
      "runtimeNonce",policy.getString("runtimeNonce"),"processNonce",policy.getString("processNonce"),"challengeNonce",UUID.randomUUID().toString().replace("-",""),"expectedCaDerSha256",input.getString("caDerSha256"),"pid",android.os.Process.myPid(),"slot",slot);
    state=new GeckoTlsFixtureTrustState(binding,input,SystemClock::elapsedRealtime,deadline,this::owns);
  }
  void start(){try{ui();state.active();runtime.getWebExtensionController().ensureBuiltIn(LOCATION,EXTENSION).accept(value->{try{
    ui();state.active();if(extension!=null||!builtin(value)||!LOCATION.equals(value.location))throw new IOException("FixtureTrust:builtin");
    extension=value;extension.setMessageDelegate(messages,HOST);
  }catch(Throwable error){failed(error);}},this::failed);}catch(Throwable error){failed(error);}}
  final WebExtension.MessageDelegate messages=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port incoming){try{
      ui();state.active();if(port!=null||incoming==null||incoming.sender==null||!builtin(extension)||!LOCATION.equals(extension.location)||!builtin(incoming.sender.webExtension)||!Arrays.asList("",LOCATION).contains(incoming.sender.webExtension.location)||!extension.metaData.baseUrl.equals(incoming.sender.webExtension.metaData.baseUrl)||incoming.sender.session!=null||incoming.sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION||!HOST.equals(incoming.name))throw new IOException("FixtureTrust:port");
      port=incoming;incoming.setDelegate(new WebExtension.PortDelegate(){
        @Override public void onPortMessage(Object message,WebExtension.Port source){receive(message,source);}
        @Override public void onDisconnect(WebExtension.Port source){if(!closed)failed(new IOException("FixtureTrust:disconnect"));}
      });
    }catch(Throwable error){failed(error);}}
  };
  void receive(Object message,WebExtension.Port source){try{
    ui();state.active();if(source!=port||port==null||!(message instanceof JSONObject))throw new IOException("FixtureTrust:port-message");
    JSONObject value=(JSONObject)message;String kind=value.optString("kind");
    if("connected".equals(kind)){
      GeckoTlsFixtureTrustState.exact(value,GeckoTlsFixtureTrustState.keys("kind apiAvailable"));if(!Boolean.TRUE.equals(value.opt("apiAvailable")))throw new IOException("FixtureTrust:native-api");
      port.postMessage(state.connected());return;
    }
    if("armed".equals(kind)||"ready".equals(kind)){
      GeckoTlsFixtureTrustState.exact(value,GeckoTlsFixtureTrustState.keys("kind value"));JSONObject proof=value.getJSONObject("value");
      if("armed".equals(kind)){
        state.armed(proof);state.enabling();
        // The observer is already installed. This is the original single public
        // SDK setter, whose cached Java getter alone is not import completion.
        runtime.getSettings().setEnterpriseRootsEnabled(true);
      }else{state.ready(proof);state.active();admitted.run();}
      return;
    }
    if("failed".equals(kind)){
      GeckoTlsFixtureTrustState.exact(value,GeckoTlsFixtureTrustState.keys("kind binding reason"));state.bound(value);
      Object reason=value.opt("reason");if(!(reason instanceof String)||!((String)reason).matches("fixture-trust-[a-z-]+"))throw new IOException("FixtureTrust:native-failure");
      throw new IOException("FixtureTrust:"+reason);
    }
    throw new IOException("FixtureTrust:message-kind");
  }catch(Throwable error){failed(error);}}
  void resample(String invocation){try{ui();if(port==null)throw new IOException("FixtureTrust:port");port.postMessage(state.resample(invocation));}catch(Throwable error){failed(error);}}
  boolean owns(){
    if(closed||failed||host.isFinishing()||host.isDestroyed()||host.remote!=view||host.session!=view.owner||view.owner.web!=view||view.destroyed||view.owner.deleted||runtime==null||view.runtime!=runtime||!view.owner.tls.readyFor(runtime)||!view.owner.cpu.readyFor(runtime))return false;
    JSONObject actual=view.owner.tls.status();return runtimeNonce.equals(actual.opt("runtimeNonce"))&&processNonce.equals(actual.opt("processNonce"))&&actual.optInt("slot",-1)==slot&&actual.optInt("pid",-1)==android.os.Process.myPid();
  }
  boolean bootReady(){return !failed&&state.bootReady();}
  boolean caseReady(String invocation){return !failed&&state.caseReady(invocation);}
  JSONObject evidence(){return state.evidence();}
  // ExtensionStore may reconstruct the native addon with an empty source URI.
  // Match its actual extension origin and builtin metadata, not Java identity.
  // The ensureBuiltIn result separately must carry the exact requested source.
  static boolean builtin(WebExtension value){return value!=null&&value.isBuiltIn&&EXTENSION.equals(value.id)&&value.metaData!=null&&value.metaData.enabled&&"1.0.0".equals(value.metaData.version)&&value.metaData.baseUrl!=null&&!value.metaData.baseUrl.isEmpty();}
  void failed(Throwable error){if(closed||failed)return;failed=true;state.fail();failure.accept(error);}
  void close(){if(closed)return;closed=true;state.close();if(port!=null)try{port.disconnect();}catch(RuntimeException ignored){}}
  static void ui()throws IOException{if(Looper.myLooper()!=Looper.getMainLooper())throw new IOException("FixtureTrust:ui-thread");}
}
