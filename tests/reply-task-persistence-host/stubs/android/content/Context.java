package android.content;

import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** A fresh Context reopens persisted host bytes, with no retained preference cache. */
public final class Context {
  public final Path root;
  public final Map<String,SQLiteDatabase> databases=new HashMap<>();
  public final SharedPreferences preferences;
  public final List<String> completionCalls=new ArrayList<>(),endedJobs=new ArrayList<>();
  public String serviceJob="";
  public Runnable onCompleted,onEnd;
  public Context(Path root)throws IOException{this.root=root;Files.createDirectories(root);preferences=new SharedPreferences(root.resolve("chat.json"));}
  public Context getApplicationContext(){return this;}
  public SharedPreferences getSharedPreferences(String name,int mode){if(!name.equals("chat"))throw new AssertionError("Unsupported preferences: "+name);return preferences;}
  public Assets getAssets(){return new Assets();}
  public static final class Assets {public InputStream open(String name)throws IOException{throw new IOException("Page asset execution is outside this persistence host");}}
}
