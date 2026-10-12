package android.content;
import java.io.File;
public final class Context {
  public final File root;public final int slot;
  public Context(File root,int slot){this.root=root;this.slot=slot;}
  public File getNoBackupFilesDir(){File out=new File(root,"env"+slot);out.mkdirs();return out;}
}
