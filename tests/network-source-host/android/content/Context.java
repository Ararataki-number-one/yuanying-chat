package android.content;
import java.io.File;import java.util.*;
public final class Context {
  public final File root;public final int slot;static final Map<String,SharedPreferences> preferences=new HashMap<>();
  public Context(File root,int slot){this.root=root;this.slot=slot;}
  public File getNoBackupFilesDir(){File out=new File(root,"env"+slot);out.mkdirs();return out;}
  public SharedPreferences getSharedPreferences(String name,int flags){return preferences.computeIfAbsent(root.getAbsolutePath()+"|"+slot+"|"+name,x->new SharedPreferences());}
}
