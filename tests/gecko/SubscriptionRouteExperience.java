package local.pocketchat;

import android.content.*;
import android.graphics.Rect;
import android.net.Uri;
import android.view.*;
import android.view.inspector.WindowInspector;
import android.widget.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Actual native dialogs, clipboard, granted provider file and encrypted catalogue. */
final class SubscriptionRouteExperience {
  final NetworkSharingIntegrationActivity a;
  static final String URL="https://entry.example.invalid/full?token=synthetic%2Fsubscription&group=all";
  SubscriptionRouteExperience(NetworkSharingIntegrationActivity a){this.a=a;}
  <T>T ui(Callable<T> action)throws Exception{CompletableFuture<T> result=new CompletableFuture<>();a.runOnUiThread(()->{try{result.complete(action.call());}catch(Throwable error){result.completeExceptionally(error);}});return result.get(10,TimeUnit.SECONDS);}
  static TextView find(View view,String text){if(view instanceof TextView&&text.contentEquals(((TextView)view).getText())&&view.isShown())return (TextView)view;if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){TextView found=find(((ViewGroup)view).getChildAt(i),text);if(found!=null)return found;}return null;}
  TextView shown(String text)throws Exception{return ui(()->{for(View root:WindowInspector.getGlobalWindowViews()){TextView found=find(root,text);if(found!=null)return found;}return null;});}
  TextView waitFor(String text)throws Exception{long end=android.os.SystemClock.elapsedRealtime()+25000;while(android.os.SystemClock.elapsedRealtime()<end){if(shown("选择本次分享的入口")!=null)throw new AssertionError("Whole subscription route opened a node chooser");TextView view=shown(text);if(view!=null)return view;Thread.sleep(50);}throw new AssertionError("Native view did not become visible: "+text);}
  void click(String label)throws Exception{TextView view=waitFor(label);ui(()->{Rect visible=new Rect();if(!(view instanceof Button)||!view.isEnabled()||!view.isClickable()||!view.getGlobalVisibleRect(visible)||visible.isEmpty()||!view.performClick())throw new AssertionError("Native button unavailable: "+label);return null;});}
  String clipboard()throws Exception{return ui(()->{ClipboardManager manager=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);ClipData clip=manager.getPrimaryClip();return clip==null?"":clip.getItemAt(0).coerceToText(a).toString();});}
  void open()throws Exception{ui(()->{a.openRoute();return null;});click("整条线路");click("准备分享");waitFor("复制配置");}
  void run()throws Exception{
    JSONArray names=new JSONArray();JSONObject keys=new JSONObject();for(int i=0;i<a.portableDetails.length();i++){JSONObject item=a.portableDetails.getJSONObject(i);names.put(item.getString("name"));keys.put(item.getString("name"),item.getString("configFingerprint"));}
    a.check("Subscription route has several actual native-parsed entry choices",names.length()>1);
    a.uiConfig=J.obj("subscriptionUrl",URL,"entryMode","latency","entryPool",names,"entryPoolNodeKeys",keys,"entry",names.getString(0),"entryNodeKey",keys.getString(names.getString(0)),"exitName",a.exit.getString("name"),"exitHost",a.exit.getString("server"),"exitPort",a.exit.getInt("port"),"exitUser",a.exit.optString("username"),"exitPassword",a.exit.optString("password"));
    NetworkSourceSelection.withActiveSnapshot(a.vault.context,()->{a.vault.put("subscription",a.portableRaw);return null;});
    ClipData previous=ui(()->((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).getPrimaryClip());Uri file=null;
    try{
      open();click("复制配置");String copied=clipboard();NetworkShareCodec.Bundle decoded=NetworkShareCodec.decode(copied);
      a.check("Actual whole-route UI copies subscription address without choosing a node",decoded.kind.equals("route")&&decoded.entry==null&&URL.equals(decoded.subscriptionUrl));
      a.check("Copied whole route keeps the fixed exit credentials",decoded.exit.getString("server").equals(a.exit.getString("server"))&&decoded.exit.optString("password").equals(a.exit.optString("password")));
      ui(()->{a.captureSubscriptionShare=true;a.subscriptionShareIntent=null;return null;});open();click("分享文件");
      long end=android.os.SystemClock.elapsedRealtime()+10000;while(a.subscriptionShareIntent==null&&android.os.SystemClock.elapsedRealtime()<end)Thread.sleep(30);Intent sent=a.subscriptionShareIntent;if(sent==null)throw new AssertionError("Actual share Intent was not emitted");file=sent.getParcelableExtra(Intent.EXTRA_STREAM);
      byte[] raw;try(java.io.InputStream stream=a.getContentResolver().openInputStream(file)){raw=J.read(stream,NetworkShareCodec.LIMIT);}
      a.check("Actual clipboard and share file contain exactly identical configuration bytes",Arrays.equals(copied.getBytes(StandardCharsets.UTF_8),raw));
      a.check("Subscription route file carries a read grant and its actual stream URI",NetworkShareCodec.MIME.equals(sent.getType())&&(sent.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0&&sent.getClipData()!=null&&file.equals(sent.getClipData().getItemAt(0).getUri()));
      NetworkShareCodec.Bundle imported=NetworkShareCodec.decode(new String(raw,StandardCharsets.UTF_8));
      JSONObject entry=J.obj("sourceType","subscription","name","Shared full subscription","url",imported.subscriptionUrl,"nodes",names,"nodeDetails",a.portableDetails);
      JSONObject ids=a.catalog.importLocalSources(entry,a.portableRaw,a.records[1],a.payloads[1]);JSONObject restored=new NetworkCatalog(a).subscription(NetworkCatalog.ENTRY,ids.getString(NetworkCatalog.ENTRY));
      a.check("Native parsed subscription import retains the HTTPS address and every entry node",!NetworkCatalog.local(restored)&&URL.equals(restored.getString("url"))&&restored.getJSONArray("nodes").length()==names.length());
      NetworkCatalog.RefreshToken refresh=a.catalog.beginRefresh(NetworkCatalog.ENTRY,restored.getString("id"));a.catalog.parsed(refresh,names,a.portableDetails,a.portableRaw,System.currentTimeMillis());
      a.check("Imported entrance subscription remains refreshable after encrypted publication",URL.equals(new NetworkCatalog(a).subscription(NetworkCatalog.ENTRY,restored.getString("id")).getString("url")));
      open();String before=clipboard();NetworkShareSelection.invalidateSaved(a.profile,ProfileCatalog.get(a).identity(6));click("复制配置");waitFor("所选配置版本已变化，请重新打开分享。");
      a.check("Copy rejects a changed selected configuration instead of exporting a stale route",before.equals(clipboard()));click("取消");
      a.subscriptionRouteExperience=J.obj("status","passed","actualAndroidExecution",true,"actualNativeViews",true,"actualClipboard",true,"actualProviderFile",true,"clipboardFileBytesEqual",true,"entryNodeChooserObserved",false,"importedNodeCount",names.length(),"actualSubscriptionHttpFetch",false,"scope","Actual native entry/exit parsing, UI actions, clipboard, provider bytes and encrypted refreshable import; external subscription HTTP is covered by the separate source refresh workflow.");
    }finally{Uri owned=file;ui(()->{a.captureSubscriptionShare=false;ClipboardManager manager=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);if(previous!=null)manager.setPrimaryClip(previous);else if(android.os.Build.VERSION.SDK_INT>=28)manager.clearPrimaryClip();if(owned!=null)NetworkShareProvider.resolve(a,owned).delete();return null;});}
  }
}
