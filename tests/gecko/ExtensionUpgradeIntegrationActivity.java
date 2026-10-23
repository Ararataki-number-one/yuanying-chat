package local.pocketchat;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import org.json.*;
import org.mozilla.geckoview.*;
import java.io.File;

/** Same-profile SDK extension replacement and synthetic session-cookie preservation. */
public final class ExtensionUpgradeIntegrationActivity extends Activity {
  final JSONArray checks=new JSONArray();GeckoRuntime runtime;boolean finished,upgrading,versionVerified,cookieRequested;String expected;WebExtension.Port preparedPort;
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));Log.i("PocketExtensionUpgrade",J.obj("check",name,"pass",pass).toString());if(!pass)throw new AssertionError(name);}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);if(!getPackageName().endsWith(".test"))throw new SecurityException();
    try{
      try(java.io.InputStream in=getAssets().open("gecko/manifest.json")){expected=J.parse(J.text(in,8192)).getString("version");}
      File profile=new File(getNoBackupFilesDir(),"extension-upgrade-fixture");profile.mkdirs();
      runtime=GeckoRuntime.create(this,new GeckoRuntimeSettings.Builder().arguments(new String[]{"-profile",profile.getAbsolutePath()}).build());
      runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/legacy-gecko-upgrade/","browser@pocketchat.local").accept(old->{
        try{check("Legacy built-in version is installed","2.0.3".equals(old.metaData.version));old.setMessageDelegate(legacy,"pocketroute");}catch(Throwable error){complete(error);}
      },this::complete);
    }catch(Throwable error){complete(error);}
  }
  final WebExtension.MessageDelegate legacy=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){
      // Update can connect its new background before ensureBuiltIn's completion
      // callback replaces the old Java delegate for this same extension ID.
      if(upgrading){upgraded.onConnect(port);return;}
      port.setDelegate(new WebExtension.PortDelegate(){
      @Override public void onPortMessage(Object message,WebExtension.Port sender){try{
        JSONObject value=(JSONObject)message;if(!"seeded".equals(value.optString("kind")))throw new AssertionError("Legacy cookie was not seeded");
        check("Legacy session cookie is present",value.optBoolean("session"));
        runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/legacy-gecko-upgrade/","browser@pocketchat.local").accept(same->{
          try{check("Same-version ensure keeps the legacy extension","2.0.3".equals(same.metaData.version));upgrade();}catch(Throwable error){complete(error);}
        },ExtensionUpgradeIntegrationActivity.this::complete);
      }catch(Throwable error){complete(error);}}
    });port.postMessage(J.obj("kind","seed"));}
  };
  void upgrade(){upgrading=true;runtime.getWebExtensionController().ensureBuiltIn("resource://android/assets/gecko/","browser@pocketchat.local").accept(current->{
    try{check("New APK extension version replaces the legacy scripts",expected.equals(current.metaData.version)&&!expected.equals("2.0.3"));versionVerified=true;current.setMessageDelegate(upgraded,"pocketroute");requestCookies();}catch(Throwable error){complete(error);}
  },this::complete);}
  final WebExtension.MessageDelegate upgraded=new WebExtension.MessageDelegate(){
    @Override public void onConnect(WebExtension.Port port){port.setDelegate(new WebExtension.PortDelegate(){
      @Override public void onPortMessage(Object message,WebExtension.Port sender){try{
        JSONObject value=(JSONObject)message;String kind=value.optString("kind");
        if(kind.equals("ready")){preparedPort=sender;requestCookies();}
        else if(kind.equals("cookies")){check("Synthetic session login survives same-profile extension replacement",!value.optBoolean("error")&&value.optString("value").contains("pocket_upgrade_fixture=retained-session"));complete(null);}
        else if(kind.equals("cookieRecoveryError"))throw new AssertionError("Session cookie recovery failed");
      }catch(Throwable error){complete(error);}}
    });port.postMessage(J.obj("kind","prepare","level",0,"token",1));}
  };
  void requestCookies(){if(!versionVerified||preparedPort==null||cookieRequested||finished)return;cookieRequested=true;preparedPort.postMessage(J.obj("kind","cookies","id",1,"url","https://chatgpt.com/"));}
  void complete(Throwable error){if(finished)return;finished=true;JSONObject report=J.obj("status",error==null?"passed":"failed","actualAndroidExecution",true,"actualGeckoExecution",true,"sameRuntimeExtensionReplacement",true,"actualApkUpgrade",false,"realChatGptAcceptance",false,"expectedVersion",expected,"checks",checks);
    try{NetworkCatalog.put(report,"buildIdentity",IntegrationBuildIdentity.read(this));if(error!=null)NetworkCatalog.put(report,"error",error.toString());File target=new File(getFilesDir(),"extension-upgrade-results.json");File staged=new File(getFilesDir(),"extension-upgrade-results.json.tmp");J.write(staged,report.toString(2));if(!staged.renameTo(target))throw new java.io.IOException("Could not publish extension upgrade report");}
    catch(Throwable failure){Log.e("PocketExtensionUpgrade","report failed",failure);}
    Log.i("PocketExtensionUpgrade",J.obj("status",report.optString("status"),"error",report.optString("error")).toString());finish();
  }
}
