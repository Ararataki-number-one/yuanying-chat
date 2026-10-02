package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.webkit.CookieManager;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class ProfileIsolationTestActivity extends Activity {
  final android.os.Handler handler=new android.os.Handler();final JSONArray checks=new JSONArray();int attempts;
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));}
  @Override public void onCreate(Bundle b){super.onCreate(b);try{getSharedPreferences("profile-proof",0).edit().clear().putString("marker","parent").commit();J.write(new File(getFilesDir(),"scope-proof.txt"),"parent");deleteDatabase("scope-proof.db");SQLiteDatabase db=openOrCreateDatabase("scope-proof.db",0,null);db.execSQL("CREATE TABLE proof(value TEXT)");db.execSQL("INSERT INTO proof VALUES('parent')");db.close();CookieManager.getInstance().setCookie("https://chatgpt.com/","profile_marker=parent; Path=/; Secure");CookieManager.getInstance().flush();new SecretStore(this).put("scope-proof","parent-secret".getBytes(StandardCharsets.UTF_8));
    for(int id=1;id<=2;id++){Context child=Profiles.context(this,id);child.getSharedPreferences("profile-proof",0).edit().clear().commit();new File(child.getFilesDir(),"scope-proof.txt").delete();child.deleteDatabase("scope-proof.db");new File(getFilesDir(),"profile-probe-"+id+".json").delete();}
    startActivity(new Intent(this,ProfileProbeActivity.class).putExtra("slot",1).setClassName(getPackageName(),"local.pocketchat.ProfileProbe1"));handler.postDelayed(()->waitChild(1),200);
  }catch(Exception e){write(e.toString());}}
  void waitChild(int slot){File file=new File(getFilesDir(),"profile-probe-"+slot+".json");if(!file.exists()){if(attempts++<100){handler.postDelayed(()->waitChild(slot),100);return;}write("Child process timed out");return;}try{JSONObject result;try(FileInputStream in=new FileInputStream(file)){result=J.parse(J.text(in,64*1024));}
    check("Environment "+slot+" runs in its own process",result.optString("process").endsWith(":profile"+slot)&&result.optInt("slot")==slot);check("Environment "+slot+" does not inherit preferences",!result.optBoolean("inheritedPrefs"));check("Environment "+slot+" does not inherit local files",!result.optBoolean("inheritedFile"));check("Environment "+slot+" does not inherit conversation database",result.optInt("inheritedRows")==0);check("Environment "+slot+" does not inherit default login cookies",!result.optString("cookieBefore").contains("profile_marker=parent"));check("Environment "+slot+" has its own cookie jar",result.optString("cookieAfter").contains("profile_marker=child"+slot));check("Environment "+slot+" isolates temporary and encrypted storage",result.optString("files").contains("profiles/env"+slot)&&result.optString("cache").contains("profiles/env"+slot)&&result.optString("noBackup").contains("profiles/env"+slot));
    if(slot==1){attempts=0;startActivity(new Intent().setClassName(getPackageName(),"local.pocketchat.ProfileProbe2"));handler.postDelayed(()->waitChild(2),150);}else parent();
  }catch(Exception e){write(e.toString());}}
  void parent()throws Exception{check("Default environment preserves preferences",getSharedPreferences("profile-proof",0).getString("marker","").equals("parent"));try(FileInputStream in=new FileInputStream(new File(getFilesDir(),"scope-proof.txt"))){check("Default environment preserves local files",J.text(in,100).equals("parent"));}check("Default environment preserves login cookies",String.valueOf(CookieManager.getInstance().getCookie("https://chatgpt.com/")).contains("profile_marker=parent"));SecretStore own=new SecretStore(this);check("Default environment preserves encrypted records",new String(own.get("scope-proof"),StandardCharsets.UTF_8).equals("parent-secret"));
    for(int slot=1;slot<=2;slot++){Context child=Profiles.context(this,slot);SecretStore scoped=new SecretStore(child);check("Environment "+slot+" reads its own encrypted records",new String(scoped.get("scope-proof"),StandardCharsets.UTF_8).equals("secret"+slot));check("Environment "+slot+" uses distinct notification IDs",Profiles.notification(child,4101)!=Profiles.notification(this,4101));check("Environment "+slot+" routes its waiting service correctly",Profiles.service(child).getSimpleName().equals("ProfileChatService"+slot));check("Environment "+slot+" routes local previews correctly",Profiles.preview(child).getSimpleName().equals("ProfilePreview"+slot));}
    byte[] saved;try(FileInputStream in=new FileInputStream(own.file("scope-proof"))){saved=J.read(in,4096);}byte[] foreign;try(FileInputStream in=new FileInputStream(new SecretStore(Profiles.context(this,1)).file("scope-proof"))){foreign=J.read(in,4096);}try(FileOutputStream out=new FileOutputStream(own.file("scope-proof"))){out.write(foreign);}boolean rejected=false;try{own.get("scope-proof");}catch(Exception expected){rejected=true;}finally{try(FileOutputStream out=new FileOutputStream(own.file("scope-proof"))){out.write(saved);}}check("Different environments cannot decrypt each other's sealed record",rejected);write("");
  }
  void write(String error){try{J.write(new File(getFilesDir(),"profile-isolation-results.json"),J.obj("checks",checks,"error",error).toString(2));}catch(Exception ignored){}}
}
