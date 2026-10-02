package local.pocketchat;

import android.content.*;
import android.database.DatabaseErrorHandler;
import android.database.sqlite.SQLiteDatabase;
import java.io.File;

/** Browser profiles use separate app records in addition to separate WebView data. */
final class ProfileContext extends ContextWrapper {
  final int slot;
  ProfileContext(Context base,int id){super(base instanceof ProfileContext?((ProfileContext)base).getBaseContext():base);if(id<0||id>=Profiles.MAX)throw new IllegalArgumentException();slot=id;}
  String name(String value){if(slot==0)return value;if(value.contains("/")||value.contains("\\"))throw new IllegalArgumentException("Invalid profile storage name");return "env"+slot+"_"+value;}
  @Override public Context getApplicationContext(){Context app=super.getApplicationContext();if(app instanceof ProfileContext)app=((ProfileContext)app).getBaseContext();return app instanceof PocketApplication?((PocketApplication)app).profile(slot):new ProfileContext(app,slot);}
  @Override public android.content.SharedPreferences getSharedPreferences(String name,int mode){return super.getSharedPreferences(name(name),mode);}
  @Override public File getDatabasePath(String name){return super.getDatabasePath(name(name));}
  @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory){return super.openOrCreateDatabase(name(name),mode,factory);}
  @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory,DatabaseErrorHandler handler){return super.openOrCreateDatabase(name(name),mode,factory,handler);}
  @Override public boolean deleteDatabase(String name){return super.deleteDatabase(name(name));}
  File directory(File base){if(slot==0)return base;File result=new File(base,"profiles/env"+slot);if(!result.isDirectory()&&!result.mkdirs())throw new IllegalStateException("独立环境目录无法创建");return result;}
  @Override public File getFilesDir(){return directory(super.getFilesDir());}
  @Override public File getCacheDir(){return directory(super.getCacheDir());}
  @Override public File getNoBackupFilesDir(){return directory(super.getNoBackupFilesDir());}
}
