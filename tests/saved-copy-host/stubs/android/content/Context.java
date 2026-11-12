package android.content;
import java.io.File;
public class Context {
  public final File root;private final ContentResolver resolver;
  public Context(File root,ContentResolver resolver){this.root=root;this.resolver=resolver;}
  public ContentResolver getContentResolver(){return resolver;}
  public File getNoBackupFilesDir(){File directory=new File(root,"no-backup");if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("Host directory");return directory;}
  public String getPackageName(){return "local.pocketchat.copy-host";}
}
