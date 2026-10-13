package android.content;
import java.io.File;import java.util.concurrent.ConcurrentHashMap;
/** Plain host directories/preferences only; Android storage has its own fixture. */
public final class Context {
  public final File root;public final int slot;static final ConcurrentHashMap<String,SharedPreferences> preferences=new ConcurrentHashMap<>();
  public Context(File root,int slot){this.root=root;this.slot=slot;}
  public File getNoBackupFilesDir(){File out=new File(root,"env"+slot);out.mkdirs();return out;}
  public SharedPreferences getSharedPreferences(String name,int flags){return preferences.computeIfAbsent(root.getAbsolutePath()+"|"+slot+"|"+name,key->new SharedPreferences());}
}
