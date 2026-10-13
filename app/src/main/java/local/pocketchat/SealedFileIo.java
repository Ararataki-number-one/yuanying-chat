package local.pocketchat;

import android.util.AtomicFile;
import java.io.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/** AtomicFile recovery and publication share one lease for each canonical file.
 * Multi-record transactions use their outer catalogue/snapshot lease and acquire
 * one stripe at a time; only nesting on the same stripe is reentrant.
 */
final class SealedFileIo {
  interface Action<T>{T run()throws Exception;}
  interface BeforeCommit{void reached(File file)throws Exception;}
  private static final class Gate{final ReentrantLock lock=new ReentrantLock();int users;}
  private static final Map<String,Gate> gates=new HashMap<>();
  static File lockFile(File file)throws IOException{
    File target=file.getCanonicalFile();byte[] digest;try{digest=java.security.MessageDigest.getInstance("SHA-256").digest(target.getName().getBytes(java.nio.charset.StandardCharsets.UTF_8));}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    // Stable bounded inodes: never unlink a lock another process may await.
    return new File(target.getParentFile(),String.format(java.util.Locale.ROOT,"sealed-io-%02d.lock",digest[0]&63));
  }
  static <T>T lease(File file,Action<T> action)throws Exception{
    String identity=lockFile(file).getCanonicalPath();Gate gate;synchronized(gates){gate=gates.get(identity);if(gate==null){gate=new Gate();gates.put(identity,gate);}gate.users++;}
    boolean locked=false;
    try{gate.lock.lockInterruptibly();locked=true;if(gate.lock.getHoldCount()>1)return action.run();
      try(RandomAccessFile handle=new RandomAccessFile(identity,"rw");java.nio.channels.FileLock held=handle.getChannel().lock()){return action.run();}
    }finally{if(locked)gate.lock.unlock();synchronized(gates){if(--gate.users==0)gates.remove(identity);}}
  }
  static byte[] read(File file)throws Exception{
    File target=file.getCanonicalFile();return lease(target,()->{try{return new AtomicFile(target).readFully();}catch(FileNotFoundException absent){if(target.exists()||new File(target.getPath()+".bak").exists())throw absent;return null;}});
  }
  static void publish(File file,byte[] bytes)throws Exception{publish(file,new byte[0],bytes,null);}
  static void publish(File file,byte[] prefix,byte[] bytes,BeforeCommit barrier)throws Exception{
    if(prefix==null||bytes==null)throw new IllegalArgumentException("保存内容无效");
    File target=file.getCanonicalFile();lease(target,()->{AtomicFile atomic=new AtomicFile(target);FileOutputStream out=atomic.startWrite();boolean finished=false;
      try{out.write(prefix);out.write(bytes);out.getFD().sync();if(barrier!=null)barrier.reached(target);atomic.finishWrite(out);
        // finishWrite() reports rename/fsync failures only through Android logs.
        // Explicitly verify the committed bytes rather than reporting success.
        if(new File(target.getPath()+".new").exists()||new File(target.getPath()+".bak").exists()||!published(target,prefix,bytes))throw new IOException("加密配置未能完整发布，请重试");finished=true;
      }catch(Exception failure){if(!finished)atomic.failWrite(out);throw failure;}return null;
    });
  }
  static boolean published(File file,byte[] prefix,byte[] bytes)throws IOException{
    long expected=(long)prefix.length+bytes.length;if(!file.isFile()||file.length()!=expected)return false;int difference=0;long offset=0;
    try(InputStream in=new FileInputStream(file)){byte[] chunk=new byte[8192];int n;while((n=in.read(chunk))!=-1){if(offset+n>expected)return false;for(int i=0;i<n;i++){long position=offset+i;difference|=chunk[i]^(position<prefix.length?prefix[(int)position]:bytes[(int)(position-prefix.length)]);}offset+=n;}}
    return offset==expected&&difference==0;
  }
  static void remove(File file)throws Exception{File target=file.getCanonicalFile();lease(target,()->{new AtomicFile(target).delete();if(target.exists()||new File(target.getPath()+".new").exists()||new File(target.getPath()+".bak").exists())throw new IOException("加密配置未能清理，请重试");return null;});}
}
