package local.pocketchat;

import android.app.Application;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import java.io.File;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;

/** The same private engine lock protects startup and cold named-profile erasure. */
final class ChromiumProfileCleanup {
  static final String CALL="clearRetiredChromiumProfile";
  static final String RETRY_MESSAGE="Chromium 资料等待浏览器进程退出。重新打开应用后，请继续此项清理。";
  private static final String ENGINE_DIRECTORY="cefrium-browser";
  private static final String ENGINE_LOCK="cefrium-browser.lock";
  private static EngineLease engineLease;
  private static volatile LiveCleanup liveCleanup;
  private ChromiumProfileCleanup() {}

  interface LiveCleanup {boolean delete(Context context,EnvironmentSpec.Identity oldIdentity)throws IOException;}
  static final class Deferred extends IOException {
    Deferred(){super(RETRY_MESSAGE);}
  }

  static File dataDirectory(Context context)throws IOException {
    File directory=new File(trustedRoot(context),ENGINE_DIRECTORY);
    if(Files.isSymbolicLink(directory.toPath())||!absent(directory)&&!directory.isDirectory())
      throw new IOException("Chromium 目录无效，清理尚未确认");
    return directory;
  }

  static File profileDirectory(Context context,EnvironmentSpec.Identity identity)throws IOException {
    return new File(dataDirectory(context),"profile-"+ChromiumEntry.profileName(identity));
  }

  /** Call before Cefrium initializes. Its native profiles can remain open after all Activities close. */
  static synchronized void holdEngine(Context context)throws IOException {
    if(!mainProcess(context))throw new IOException("Chromium 仅在应用主进程运行");
    File directory=dataDirectory(context);
    if(engineLease!=null)return;
    EngineLease lease=acquire(trustedRoot(context));
    if(lease==null)throw new IOException("Chromium 正在清理环境资料，请稍后重试");
    try{
      if(Files.isSymbolicLink(directory.toPath())||!directory.isDirectory()&&!directory.mkdir())
        throw new IOException("Chromium 目录无法建立");
    }catch(IOException|RuntimeException failure){lease.close();throw failure;}
    engineLease=lease;
  }

  static synchronized void registerLive(Context context,LiveCleanup cleanup)throws IOException {
    if(!mainProcess(context)||engineLease==null)throw new IOException("Chromium 进程未持有资料锁");
    liveCleanup=cleanup;
  }

  static EnvironmentSpec.Identity previous(EnvironmentSpec.Identity current)throws IOException {
    if(current.generation<=0)throw new IOException("环境资料代际无效");
    return new EnvironmentSpec.Identity(current.slot,current.generation-1,current.environmentId);
  }

  /** Confirm the old identity came from an active durable reset/delete transaction. */
  static void requireRetired(Context context,EnvironmentSpec.Identity older)throws IOException {
    JSONObject row=ProfileCatalog.get(context).item(older.slot);
    boolean resetting=row.optBoolean("created")&&row.optBoolean("resetting")&&!row.optBoolean("deleting");
    boolean deleting=!row.optBoolean("created")&&row.optBoolean("deleting")&&!row.optBoolean("resetting");
    if(!(resetting||deleting)||older.generation==Integer.MAX_VALUE||row.optInt("generation",-1)!=older.generation+1
        ||!older.environmentId.equals(row.optString("environmentId")))
      throw new IOException("Chromium 清理对应的环境已变化");
  }

  /** A deferred SDK request leaves the catalog maintenance record active for retry. */
  static synchronized void clearRetired(Context context,EnvironmentSpec.Identity older)throws IOException {
    requireRetired(context,older);
    File target=profileDirectory(context,older);
    if(absent(dataDirectory(context)))return;
    EngineLease lease=engineLease==null?acquire(trustedRoot(context)):null;
    if(lease!=null){
      try(EngineLease ignored=lease){
        requireRetired(context,older);
        EnvironmentBrowserData.erase(profileDirectory(context,older));
        if(!absent(profileDirectory(context,older)))throw new IOException("Chromium 资料尚未清理");
      }
      return;
    }
    try{
      Bundle request=new Bundle();
      request.putInt("slot",older.slot);request.putInt("generation",older.generation);request.putString("environmentId",older.environmentId);
      Uri endpoint=Uri.parse("content://"+context.getPackageName()+".lifecycle0");
      Bundle result=Profiles.global(context).getContentResolver().call(endpoint,CALL,null,request);
      requireRetired(context,older);
      if(result!=null&&result.getBoolean("cleared")&&absent(target))return;
    }catch(RuntimeException unavailable){throw new Deferred();}
    throw new Deferred();
  }

  /** Called only by the existing same-UID lifecycle provider. Never initializes the SDK. */
  static Bundle dispatch(Context context,Bundle request){
    Bundle result=new Bundle();
    LiveCleanup cleanup=liveCleanup;
    if(request==null||cleanup==null||!mainProcess(context))return result;
    FutureTask<Boolean> job=new FutureTask<>(()->{
      EnvironmentSpec.Identity retired=new EnvironmentSpec.Identity(request.getInt("slot",-1),
        request.getInt("generation",-1),request.getString("environmentId"));
      requireRetired(context,retired);
      return cleanup.delete(context,retired)&&absent(profileDirectory(context,retired));
    });
    if(Looper.myLooper()==Looper.getMainLooper())job.run();
    else if(!new Handler(Looper.getMainLooper()).post(job))return result;
    try{result.putBoolean("cleared",job.get(6,TimeUnit.SECONDS));}
    catch(InterruptedException interrupted){job.cancel(false);Thread.currentThread().interrupt();}
    catch(Exception unfinished){job.cancel(false);}
    return result;
  }

  private static File trustedRoot(Context context)throws IOException {
    File root=Profiles.global(context).getNoBackupFilesDir();
    if(Files.isSymbolicLink(root.toPath())||!root.isDirectory())throw new IOException("应用资料目录无效");
    return root.getCanonicalFile();
  }

  private static boolean mainProcess(Context context){
    return context!=null&&Build.VERSION.SDK_INT>=29&&context.getPackageName().equals(Application.getProcessName());
  }

  private static boolean absent(File file){return Files.notExists(file.toPath(),LinkOption.NOFOLLOW_LINKS);}

  private static EngineLease acquire(File root)throws IOException {
    FileChannel channel=FileChannel.open(new File(root,ENGINE_LOCK).toPath(),StandardOpenOption.CREATE,
      StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
    try{
      FileLock lock=channel.tryLock();
      if(lock!=null)return new EngineLease(channel,lock);
    }catch(OverlappingFileLockException occupied){
      // Another caller in this process already owns the exact lock.
    }catch(IOException|RuntimeException unavailable){channel.close();throw unavailable;}
    channel.close();
    return null;
  }

  private static final class EngineLease implements AutoCloseable {
    final FileChannel channel;
    final FileLock lock;
    EngineLease(FileChannel channel,FileLock lock){this.channel=channel;this.lock=lock;}
    @Override public void close()throws IOException{try{lock.release();}finally{channel.close();}}
  }
}
