package android.util;
import java.io.File;
public final class AtomicFile {final File file;public AtomicFile(File file){this.file=file;}public void delete(){file.delete();new File(file.getPath()+".bak").delete();new File(file.getPath()+".new").delete();}}
