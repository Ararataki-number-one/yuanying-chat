package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.io.*;

public class ProfileProbeActivity extends Activity {
  @Override protected void attachBaseContext(Context base){super.attachBaseContext(new ProfileContext(base,Profiles.processSlot()));}
  @Override public void onCreate(Bundle b){super.onCreate(b);try{int slot=Profiles.slot(this);String cookie=CookieManager.getInstance().getCookie("https://chatgpt.com/");boolean before=getSharedPreferences("profile-proof",0).contains("marker");File own=new File(getFilesDir(),"scope-proof.txt");boolean inherited=own.exists();SQLiteDatabase db=openOrCreateDatabase("scope-proof.db",0,null);db.execSQL("CREATE TABLE IF NOT EXISTS proof(value TEXT)");int rows;try(android.database.Cursor c=db.rawQuery("SELECT COUNT(*) FROM proof",null)){c.moveToFirst();rows=c.getInt(0);}getSharedPreferences("profile-proof",0).edit().putString("marker","child"+slot).commit();J.write(own,"child"+slot);db.execSQL("INSERT INTO proof VALUES('child')");db.close();CookieManager.getInstance().setCookie("https://chatgpt.com/","profile_marker=child"+slot+"; Path=/; Secure");CookieManager.getInstance().flush();new SecretStore(this).put("scope-proof",("secret"+slot).getBytes(java.nio.charset.StandardCharsets.UTF_8));
    JSONObject result=J.obj("slot",slot,"process",android.app.Application.getProcessName(),"inheritedPrefs",before,"inheritedFile",inherited,"inheritedRows",rows,"cookieBefore",cookie==null?"":cookie,"cookieAfter",CookieManager.getInstance().getCookie("https://chatgpt.com/"),"files",getFilesDir().getAbsolutePath(),"cache",getCacheDir().getAbsolutePath(),"noBackup",getNoBackupFilesDir().getAbsolutePath(),"database",getDatabasePath("scope-proof.db").getAbsolutePath());
    Context global=Profiles.global(this);J.write(new File(global.getFilesDir(),"profile-probe-"+slot+".json"),result.toString(2));
  }catch(Exception e){try{J.write(new File(Profiles.global(this).getFilesDir(),"profile-probe-error.json"),J.obj("error",e.toString()).toString());}catch(Exception ignored){}}finish();}
}
