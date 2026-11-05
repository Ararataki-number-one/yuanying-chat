package local.pocketchat;
import android.content.Context;import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;
final class TestContext extends Context {
  final Path directory,globalDirectory,data;final ProfileCatalog catalog=new ProfileCatalog();TestContext(Path directory)throws IOException{this.globalDirectory=directory;this.data=directory.getParent();this.directory=directory.resolve("profiles/env1");Files.createDirectories(this.directory);}
  public android.content.pm.ApplicationInfo getApplicationInfo(){android.content.pm.ApplicationInfo value=new android.content.pm.ApplicationInfo();value.dataDir=data.toString();return value;}Context global(){return new StorageContext(data,globalDirectory,globalDirectory,0);}public Context getApplicationContext(){return this;}public File getNoBackupFilesDir(){if(MainQueue.ui)throw new AssertionError("TLS disk directory on UI");return directory.toFile();}
}
final class ChatSession {
  final TestContext context;boolean deleted;final int environmentGeneration=1;final String environmentId="00000000-0000-0000-0000-000000000001";final ManualExecutor environmentIo=new ManualExecutor();final MainQueue handler=new MainQueue();ChatSession(TestContext context){this.context=context;}
}
final class MainQueue {static boolean ui;final List<Runnable> tasks=new ArrayList<>(),delayed=new ArrayList<>();void post(Runnable task){tasks.add(task);}void postDelayed(Runnable task,long ignored){delayed.add(task);}void drain(){ui=true;try{while(!tasks.isEmpty())tasks.remove(0).run();}finally{ui=false;}}}
final class ManualExecutor extends AbstractExecutorService {
  final List<Runnable> tasks=new ArrayList<>();public void execute(Runnable work){tasks.add(work);}void drain(){while(!tasks.isEmpty())tasks.remove(0).run();}public void shutdown(){}public List<Runnable> shutdownNow(){return Collections.emptyList();}public boolean isShutdown(){return false;}public boolean isTerminated(){return false;}public boolean awaitTermination(long timeout,TimeUnit unit){return false;}
}
final class Profiles {static final int MAX=32;static int slot(Context context){return context instanceof StorageContext?((StorageContext)context).slot:1;}static int processSlot(){return 1;}static Context global(Context context){return context instanceof StorageContext?((StorageContext)context).global():((TestContext)context).global();}}
final class ProfileCatalog {
  EnvironmentSpec.Identity current=new EnvironmentSpec.Identity(1,1,"00000000-0000-0000-0000-000000000001");static ProfileCatalog get(Context context){return ((TestContext)context).catalog;}EnvironmentSpec.Identity identity(int slot){return current;}
  interface IdentityAction<T>{T run()throws Exception;}synchronized <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{if(!current.equals(expected))throw new IOException("Changed owner");return action.run();}
}
final class SecretStore {
  final TestContext context;SecretStore(Context context){this.context=(TestContext)context;}
  byte[] get(String name)throws IOException{Path file=context.directory.resolve(name+".vault");return Files.exists(file)?Files.readAllBytes(file):null;}
  void put(String name,byte[] value)throws Exception{Path temporary=Files.createTempFile(context.directory,"vault-",".tmp");Files.write(temporary,value);Files.move(temporary,context.directory.resolve(name+".vault"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
}

final class StorageContext extends Context {
 final Path data,noBackup,actual;final int slot;int rootReads;StorageContext(Path data,Path noBackup,Path actual,int slot){this.data=data;this.noBackup=noBackup;this.actual=actual;this.slot=slot;}public Context getApplicationContext(){return this;}public File getNoBackupFilesDir(){rootReads++;return actual.toFile();}public android.content.pm.ApplicationInfo getApplicationInfo(){android.content.pm.ApplicationInfo value=new android.content.pm.ApplicationInfo();value.dataDir=data.toString();return value;}Context global(){return new StorageContext(data,noBackup,noBackup,0);}
}
