package local.pocketchat;
import java.nio.file.*;
import org.json.*;
import android.webkit.*;
import androidx.webkit.*;
final class Cases {
  static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("Chromium identity control "+checks);}
  interface Action{void run()throws Exception;}
  static void reject(Action action){boolean rejected=false;try{action.run();}catch(IllegalArgumentException|IllegalStateException expected){rejected=true;}catch(Exception unexpected){throw new AssertionError(unexpected);}check(rejected);}
  static void reset(){WebViewFeature.metadata=true;WebViewFeature.document=true;WebViewCompat.fail=false;WebViewCompat.missingProvider=false;WebSettingsCompat.mismatch=false;android.os.Looper.main=true;}
  public static void main(String[] args)throws Exception{
    String seed="a".repeat(64),asset=Files.readString(Path.of(args[0]));ChromiumFingerprintSpec defaults=ChromiumFingerprintSpec.from(new JSONObject("{\"schema\":1,\"engine\":\"chromium\"}"));
    check(defaults.protectedMode()&&!defaults.desktop()&&defaults.canvas&&defaults.webgl&&defaults.audio&&defaults.webrtc);
    ChromiumFingerprintSpec compatible=ChromiumFingerprintSpec.from(new JSONObject("{\"protection\":\"compatibility\"}"));check(!compatible.scriptsRequired()&&!compatible.canvas);
    check(!defaults.restrictWorkers()&&defaults.workers.equals("allow"));
    ChromiumFingerprintSpec restricted=ChromiumFingerprintSpec.from(J.obj("protection","compatibility","workers","restrict"));check(restricted.restrictWorkers()&&restricted.scriptsRequired());check(ChromiumFingerprintSpec.from(restricted.json()).workers.equals("restrict"));
    for(Object value:new Object[]{true,1,JSONObject.NULL,"blocked","ALLOW"})reject(()->ChromiumFingerprintSpec.from(J.obj("workers",value)));
    check(ChromiumFingerprintSpec.from(defaults.json()).json().toString().equals(defaults.json().toString()));
    for(String unknown:new String[]{"timezone","hardware","fonts","language","locales","userAgent","ua","screen","deviceMemory"})reject(()->ChromiumFingerprintSpec.from(J.obj(unknown,"fake")));
    for(Object value:new Object[]{1,"true",JSONObject.NULL,new JSONObject()})reject(()->ChromiumFingerprintSpec.from(J.obj("canvas",value)));
    for(Object value:new Object[]{true,"1",1.0,2,JSONObject.NULL})reject(()->ChromiumFingerprintSpec.from(J.obj("schema",value)));
    reject(()->ChromiumFingerprintSpec.from(null));reject(()->ChromiumFingerprintSpec.from(J.obj("engine","gecko")));reject(()->ChromiumFingerprintSpec.from(J.obj("display","fake-device")));reject(()->ChromiumFingerprintSpec.from(J.obj("protection","full-rfp")));
    WebView view=new WebView();String actual=view.settings.ua;ChromiumFingerprintRuntime.Prepared p=ChromiumFingerprintRuntime.prepare(view,defaults,seed,asset);
    check(view.settings.block);check(actual.equals(view.settings.ua));check(WebViewCompat.added==1&&WebViewCompat.origins.equals(java.util.Set.of("*")));check(WebViewCompat.script.contains(seed)&&!WebViewCompat.script.contains(ChromiumFingerprintRuntime.TOKEN));
    JSONObject receipt=p.receipt();check(receipt.getJSONObject("nativeRequested").toString().equals(receipt.getJSONObject("nativeReadback").toString()));check(!receipt.getBoolean("fingerprintProtectionVerified")&&!receipt.getBoolean("workerCoverageVerified")&&!receipt.getBoolean("pageObserved"));check(receipt.getJSONObject("unsupported").getString("audioGetChannelData").equals("unsupported"));check(!receipt.toString().contains(seed));
    receipt.put("pageObserved",true);check(!p.receipt().getBoolean("pageObserved"));p.close();p.close();check(WebViewCompat.removed==1);final WebView usedView=view;reject(()->ChromiumFingerprintRuntime.prepare(usedView,defaults,seed,asset));
    ChromiumFingerprintSpec desktop=ChromiumFingerprintSpec.from(J.obj("display","desktop"));view=new WebView();p=ChromiumFingerprintRuntime.prepare(view,desktop,seed,asset);check(view.settings.ua.contains("Chrome/124.0.6367.219")&&!view.settings.ua.contains(" Mobile"));check(p.receipt().getJSONObject("nativeReadback").getString("platform").equals("Linux"));check(!p.receipt().getJSONObject("nativeReadback").getBoolean("mobile"));p.close();
    final WebView metaMissing=new WebView();WebViewFeature.metadata=false;reject(()->ChromiumFingerprintRuntime.prepare(metaMissing,defaults,seed,asset));check(metaMissing.settings.block&&metaMissing.settings.sets==0);reset();
    final WebView docMissing=new WebView();WebViewFeature.document=false;reject(()->ChromiumFingerprintRuntime.prepare(docMissing,defaults,seed,asset));check(docMissing.settings.block&&docMissing.settings.sets==0);reset();
    final WebView offMain=new WebView();android.os.Looper.main=false;reject(()->ChromiumFingerprintRuntime.prepare(offMain,defaults,seed,asset));check(offMain.settings.sets==0);reset();
    final WebView openNetwork=new WebView();openNetwork.settings.block=false;reject(()->ChromiumFingerprintRuntime.prepare(openNetwork,defaults,seed,asset));check(openNetwork.settings.sets==0);
    for(String invalid:new String[]{"","f".repeat(63),"A".repeat(64),"x".repeat(64)})reject(()->ChromiumFingerprintRuntime.prepare(new WebView(),defaults,invalid,asset));
    for(String invalid:new String[]{"",ChromiumFingerprintRuntime.TOKEN+ChromiumFingerprintRuntime.TOKEN,"x".repeat(131073)})reject(()->ChromiumFingerprintRuntime.prepare(new WebView(),defaults,seed,invalid));
    final WebView badUa=new WebView();badUa.settings.ua="Firefox/157.0";reject(()->ChromiumFingerprintRuntime.prepare(badUa,defaults,seed,asset));check(badUa.settings.sets==0);
    final WebView noProvider=new WebView();WebViewCompat.missingProvider=true;reject(()->ChromiumFingerprintRuntime.prepare(noProvider,defaults,seed,asset));check(noProvider.settings.sets==0);reset();
    final WebView refused=new WebView();refused.settings.refuse=true;reject(()->ChromiumFingerprintRuntime.prepare(refused,desktop,seed,asset));check(refused.settings.block);
    final WebView mismatch=new WebView();WebSettingsCompat.mismatch=true;int before=WebViewCompat.added;reject(()->ChromiumFingerprintRuntime.prepare(mismatch,desktop,seed,asset));check(mismatch.settings.block&&WebViewCompat.added==before);reset();
    final WebView registration=new WebView();WebViewCompat.fail=true;reject(()->ChromiumFingerprintRuntime.prepare(registration,defaults,seed,asset));check(registration.settings.block);reset();
    WebViewFeature.metadata=false;WebViewFeature.document=false;before=WebViewCompat.added;view=new WebView();p=ChromiumFingerprintRuntime.prepare(view,compatible,seed,null);check(view.settings.block&&WebViewCompat.added==before);check(!p.receipt().getBoolean("documentStartRegistered"));p.close();reset();
    WebViewFeature.metadata=false;WebViewFeature.document=false;final WebView workerMissing=new WebView();before=WebViewCompat.added;reject(()->ChromiumFingerprintRuntime.prepare(workerMissing,restricted,seed,asset));check(workerMissing.settings.block&&WebViewCompat.added==before&&workerMissing.settings.sets==0);reset();
    WebViewFeature.metadata=false;view=new WebView();p=ChromiumFingerprintRuntime.prepare(view,restricted,seed,asset);check(p.receipt().getBoolean("documentStartRegistered")&&WebViewCompat.script.contains("\"workers\":\"restrict\""));JSONObject workerReceipt=p.receipt().getJSONObject("workerCreationPolicy");check(workerReceipt.getString("mode").equals("restrict")&&workerReceipt.getString("state").equals("requested")&&!workerReceipt.getBoolean("existingWorkerExecutionControlled"));check(!p.receipt().getBoolean("workerCoverageVerified")&&!p.receipt().getBoolean("pageObserved"));p.close();reset();
    System.out.println(J.obj("status","passed","passed",checks,"total",checks).toString());
  }
}
