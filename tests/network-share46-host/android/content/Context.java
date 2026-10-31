package android.content;
import java.io.File;
public class Context {public final String id;public Context(String id){this.id=id;}public File getNoBackupFilesDir(){return new File(System.getProperty("java.io.tmpdir"),"share46-host-"+id);}}
