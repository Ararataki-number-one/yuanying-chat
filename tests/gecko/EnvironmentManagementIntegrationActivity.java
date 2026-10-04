package local.pocketchat;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Actual storage/process cleanup through the production implementation, using synthetic data. */
public final class EnvironmentManagementIntegrationActivity extends Activity {
  @Override public void onCreate(Bundle state){super.onCreate(state);run(getIntent().getStringExtra("managementAction"));}
  @Override protected void onNewIntent(android.content.Intent i){super.onNewIntent(i);setIntent(i);run(i.getStringExtra("managementAction"));}
  void run(String action){new Thread(()->{JSONObject result=new JSONObject();try{
    android.content.Context zero=Profiles.context(this,0),one=Profiles.context(this,1);ProfileCatalog catalog=ProfileCatalog.get(this);
    if("deleteOne".equals(action)){
      catalog.created(0);catalog.created(1);zero.getSharedPreferences("chat",0).edit().putString("managementMarker","kept-zero").commit();one.getSharedPreferences("chat",0).edit().putString("managementMarker","remove-one").commit();
      new SecretStore(one).put("exit-region","synthetic-private-data".getBytes(StandardCharsets.UTF_8));
      java.io.File saved=new File(one.getFilesDir(),"saved-downloads/synthetic/saved.txt");saved.getParentFile().mkdirs();java.nio.file.Files.write(saved.toPath(),"keep-saved-file".getBytes(StandardCharsets.UTF_8));
      int generation=catalog.item(1).optInt("generation");catalog.beginDelete(1);EnvironmentDeleteActivity.remove(this,1);
      result=J.obj("action",action,"removed",!catalog.item(1).optBoolean("created")&&!catalog.item(1).optBoolean("deleting"),"generationChanged",catalog.item(1).optInt("generation")==generation+1,"privateDataGone",!new SecretStore(one).file("exit-region").exists()&&!one.getSharedPreferences("chat",0).contains("managementMarker"),"otherEnvironmentKept","kept-zero".equals(zero.getSharedPreferences("chat",0).getString("managementMarker","")),"savedFileKept",saved.isFile());
      Profiles.prepare(zero,1,false);NetworkCatalog.put(result,"slotReusable",catalog.item(1).optBoolean("created")&&one.getSharedPreferences("chat",0).getBoolean("environmentInitialized",false));
    }else if("deleteZero".equals(action)){
      one.getSharedPreferences("chat",0).edit().putString("managementMarker","kept-one").commit();Profiles.global(this).getSharedPreferences("app-updates",0).edit().putString("managementMarker","kept-updates").commit();
      NetworkCatalog library=new NetworkCatalog(this);JSONObject exit=library.addExit("synthetic shared exit","日本","example.test",1080,"",""),sub=library.addSubscription("synthetic shared subscription","https://example.test/subscription");library.parsed(sub.optString("id"),J.arr("大阪 03"),"synthetic cache".getBytes(StandardCharsets.UTF_8),123);
      catalog.beginDelete(0);EnvironmentDeleteActivity.remove(this,0);NetworkCatalog after=new NetworkCatalog(this);
      result=J.obj("action",action,"removed",!catalog.item(0).optBoolean("created"),"otherEnvironmentKept","kept-one".equals(one.getSharedPreferences("chat",0).getString("managementMarker","")),"updateSettingsKept","kept-updates".equals(Profiles.global(this).getSharedPreferences("app-updates",0).getString("managementMarker","")),"libraryKept",after.exit(exit.optString("id"))!=null&&after.subscription(sub.optString("id"))!=null&&after.cache(after.subscription(sub.optString("id")))!=null,"defaultReassigned",AppSettings.defaultSlot(this)==1);
      boolean lastProtected=false;try{catalog.beginDelete(1);}catch(IOException expected){lastProtected=true;}NetworkCatalog.put(result,"lastEnvironmentProtected",lastProtected);
    }else throw new IllegalArgumentException();
  }catch(Exception e){result=J.obj("action",action,"error",e.toString());}Log.i("PocketEnvironmentManagement",result.toString());},"management-fixture").start();}
}
