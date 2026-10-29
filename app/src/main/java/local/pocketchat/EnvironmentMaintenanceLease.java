package local.pocketchat;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileLock;
import java.nio.file.Files;

/** One maintenance action per slot, including across process restarts. The
 * lease is outside environment data and is never unlinked during cleanup. */
final class EnvironmentMaintenanceLease {
  private static final Object[] GATES=new Object[8];
  static{for(int i=0;i<GATES.length;i++)GATES[i]=new Object();}
  interface Action<T>{T run()throws Exception;}
  static <T>T with(File trustedNoBackup,int slot,Action<T> action)throws Exception{
    if(slot<0||slot>=GATES.length||action==null)throw new IOException("环境维护参数无效");
    if(Files.isSymbolicLink(trustedNoBackup.toPath())||!trustedNoBackup.isDirectory())throw new IOException("应用维护目录不可用");
    File root=trustedNoBackup.getCanonicalFile();
    synchronized(GATES[slot]){
      File lease=new File(root,"browser-maintenance-env"+slot+".lock");
      if(Files.isSymbolicLink(lease.toPath()))throw new IOException("维护锁包含链接，未清理数据");
      try(RandomAccessFile handle=new RandomAccessFile(lease,"rw");FileLock held=handle.getChannel().lock()){
        return action.run();
      }
    }
  }
}
