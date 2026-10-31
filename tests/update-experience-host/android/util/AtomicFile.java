package android.util;
import java.io.*;
import java.nio.file.*;
/** Real host file publication/recovery adapter, not Android execution. */
public final class AtomicFile {
 final File base,next,backup;public static volatile boolean failRenameOnce;
 public AtomicFile(File base){this.base=base;next=new File(base+".new");backup=new File(base+".bak");}
 public FileOutputStream startWrite()throws IOException{base.getParentFile().mkdirs();return new FileOutputStream(next);}
 public void finishWrite(FileOutputStream out){try{out.getFD().sync();out.close();if(failRenameOnce){failRenameOnce=false;return;}Files.move(next.toPath(),base.toPath(),StandardCopyOption.REPLACE_EXISTING);}catch(IOException ignored){}}
 public void failWrite(FileOutputStream out){try{out.close();}catch(IOException ignored){}next.delete();}
 public FileInputStream openRead()throws IOException{if(backup.isFile())Files.move(backup.toPath(),base.toPath(),StandardCopyOption.REPLACE_EXISTING);if(base.isFile())next.delete();return new FileInputStream(base);}
}
