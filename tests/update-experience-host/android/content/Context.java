package android.content;
import java.io.File;
public class Context {final File root;public Context(File root){this.root=root;}public File getNoBackupFilesDir(){return root;}}
