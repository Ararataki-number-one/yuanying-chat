package android.util;
import java.io.*;import java.nio.file.*;
/** Host behavior fixture mirrors Android openRead recovery and quiet finishWrite rename failure. */
public final class AtomicFile {
  final File base,next,backup;public static boolean failRenameOnce;
  public AtomicFile(File file){base=file;next=new File(file.getPath()+".new");backup=new File(file.getPath()+".bak");}
  public FileOutputStream startWrite()throws IOException{base.getParentFile().mkdirs();return new FileOutputStream(next);}
  public void finishWrite(FileOutputStream out){try{out.getFD().sync();out.close();if(failRenameOnce){failRenameOnce=false;return;}Files.move(next.toPath(),base.toPath(),StandardCopyOption.REPLACE_EXISTING);}catch(IOException ignored){/* Android reports this only through logs. */}}
  public void failWrite(FileOutputStream out){try{out.close();}catch(IOException ignored){}next.delete();}
  public byte[] readFully()throws IOException{if(backup.exists())Files.move(backup.toPath(),base.toPath(),StandardCopyOption.REPLACE_EXISTING);if(next.exists()&&base.exists())next.delete();try(FileInputStream in=new FileInputStream(base)){return in.readAllBytes();}}
  public void delete(){base.delete();next.delete();backup.delete();}
}
