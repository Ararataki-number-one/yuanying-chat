package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;

/** Test-only five-record visual fixture; opens the production environment page. */
public final class FiveEnvironmentVisualActivity extends Activity {
  private static final String SEEDED="nativeUiFiveEnvironmentSeedV1";

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    try{
      seedFive();
      startActivity(new Intent(this,WindowHomeActivity.class));
    }catch(Exception error){Log.e("PocketUiVisual","five-environment fixture setup failed",error);}
    finish();
  }

  void seedFive()throws Exception{
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package required");
    if(AppSettings.bool(this,SEEDED,false))return;
    ProfileCatalog catalog=ProfileCatalog.get(this);
    JSONArray existing=catalog.list();
    // The runner clears only its installed disposable test package first.
    // Refuse an unrelated populated catalog rather than deleting any records.
    for(int i=0;i<existing.length();i++){
      JSONObject row=existing.optJSONObject(i);
      if((row.optInt("slot")!=0&&row.optBoolean("created"))||row.optLong("opened")!=0
          ||row.optLong("seen")!=0||!row.optString("problem").isEmpty()||!row.optString("draft").isEmpty())
        throw new IllegalStateException("A fresh disposable visual fixture is required");
    }
    String[] names={"日常会话","资料整理","开发调试","长文阅读与文件整理","翻译与写作"};
    for(int slot=0;slot<names.length;slot++){
      catalog.created(slot);Profiles.rename(this,slot,names[slot]);
      catalog.details(slot,slot==0?"个人":"工作","");
      catalog.favorite(slot,slot==0);
      catalog.browserDisplay(slot,slot==0||slot==3);
      Profiles.context(this,slot).getSharedPreferences("chat",0).edit()
        .putString("browserEngine","gecko").putString("networkMode","external")
        .putBoolean("networkConfigured",false).putBoolean("pageMode",true)
        .putBoolean("environmentInitialized",true).commit();
    }
    Bundle options=new Bundle();options.putBoolean("autoCheck",false);AppUpdates.call(this,"settings",options);
    AppSettings.defaultSlot(this,0);AppSettings.put(this,"brandSeen","true");
    AppSettings.put(this,"updateAutoCheck","false");AppSettings.put(this,SEEDED,"true");
  }
}
