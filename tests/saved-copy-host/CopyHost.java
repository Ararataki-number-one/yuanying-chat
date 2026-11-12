package local.pocketchat;

import android.app.*;import android.content.*;import android.net.Uri;import android.os.*;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import org.json.*;

public final class CopyHost {
  static final JSONArray checks=new JSONArray();static final List<SavedFileActions> actions=new ArrayList<>();static final Handler main=new Handler(Looper.getMainLooper());
  static <T>T ui(Callable<T> action)throws Exception{CompletableFuture<T> result=new CompletableFuture<>();main.post(()->{try{result.complete(action.call());}catch(Throwable error){result.completeExceptionally(error);}});return result.get(5,TimeUnit.SECONDS);}
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static final class Fixture {
    final FaultProvider provider;final Activity activity;final SavedFileActions action;final JSONObject source;
    Fixture(byte[] bytes)throws Exception{File root=Files.createTempDirectory("saved-copy-host-").toFile();provider=new FaultProvider(root,bytes);activity=new Activity(root,provider);action=ui(()->new SavedFileActions(activity));actions.add(action);source=J.obj("uri",provider.original.toString(),"name","source.bin","mime","application/octet-stream");}
    void select()throws Exception{ui(()->{action.export(source);action.result(Activity.RESULT_OK,new Intent("result").setData(provider.destination));return null;});}
    void idle()throws Exception{
      try{action.worker.submit(()->{}).get(5,TimeUnit.SECONDS);}
      catch(RejectedExecutionException retired){
        if(!action.worker.isShutdown())throw retired;
        if(!action.worker.awaitTermination(5,TimeUnit.SECONDS))throw new AssertionError("copy worker retirement");
      }
      ui(()->null);
    }
  }
  static void streams()throws Exception{
    for(String fault:new String[]{"normal-empty","normal-large","write","flush","output-close","input-close","null-input","null-output","document-close"}){
      byte[] bytes=fault.equals("normal-empty")?new byte[0]:new byte[65539];Arrays.fill(bytes,(byte)41);Fixture f=new Fixture(bytes);f.provider.fault=fault;if(fault.equals("document-close"))f.provider.destination=Uri.parse("content://documents.test/target");f.select();f.idle();
      boolean normal=fault.startsWith("normal");
      check("Copy "+fault+" preserves original bytes",Arrays.equals(Files.readAllBytes(f.provider.source.toPath()),bytes));
      check("Copy "+fault+" confirms only a fully closed destination",normal?f.provider.target.isFile()&&Arrays.equals(Files.readAllBytes(f.provider.target.toPath()),bytes)&&f.activity.problems.isEmpty():!f.provider.target.exists()&&!f.activity.problems.isEmpty());
      check("Copy "+fault+" releases busy after terminal callback",!f.action.busy&&f.action.exporting==null);
    }
  }
  static void retiredCopies()throws Exception{
    for(String timing:new String[]{"queued-empty","input-eof-empty","output-close-empty","output-close-nonempty"}){
      Fixture f=new Fixture(timing.endsWith("nonempty")?new byte[]{1,2,3}:new byte[0]);
      Runnable close=()->{try{ui(()->{f.action.close();return null;});}catch(Exception error){throw new CompletionException(error);}};
      if(timing.equals("queued-empty")){
        CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1);f.action.worker.execute(()->{held.countDown();try{if(!release.await(5,TimeUnit.SECONDS))throw new AssertionError("queued copy barrier");}catch(InterruptedException error){throw new AssertionError(error);}});if(!held.await(5,TimeUnit.SECONDS))throw new AssertionError("queued worker");f.select();close.run();release.countDown();
      }else{if(timing.startsWith("input"))f.provider.onEof=close;else f.provider.onOutputClose=close;f.select();}
      f.idle();check("Retired copy "+timing+" leaves no unconfirmed destination",!f.provider.target.exists());
      check("Retired copy "+timing+" releases busy without stale UI feedback",!f.action.busy&&f.activity.problems.isEmpty()&&f.provider.source.isFile());
    }
  }
  static void admission()throws Exception{
    Fixture late=new Fixture(new byte[]{1});boolean accepted=ui(()->{late.action.export(late.source);late.action.close();try{late.action.result(Activity.RESULT_OK,new Intent("result").setData(late.provider.destination));return true;}catch(RejectedExecutionException failure){return false;}});late.idle();
    check("Late picker result after close neither schedules work nor leaks busy",accepted&&!late.action.busy&&late.provider.outputOpens==0&&late.action.exporting==null);
    Fixture closed=new Fixture(new byte[]{1});ui(()->{closed.action.close();closed.action.export(closed.source);return null;});check("Closed saved-file actions cannot launch another picker",closed.activity.pickers==0&&closed.action.exporting==null);
    Fixture same=new Fixture(new byte[]{2});ui(()->{same.action.export(same.source);same.action.result(Activity.RESULT_OK,new Intent("result").setData(same.provider.original));return null;});same.idle();check("Original destination is never overwritten or deleted",same.provider.outputOpens==0&&same.provider.deletes==0&&same.provider.source.isFile()&&!same.action.busy);
    Fixture cancelled=new Fixture(new byte[]{3});ui(()->{cancelled.action.export(cancelled.source);cancelled.action.result(Activity.RESULT_CANCELED,null);return null;});cancelled.idle();check("Cancelled picker retires its selection without filesystem writes",cancelled.action.exporting==null&&cancelled.provider.outputOpens==0&&!cancelled.action.busy);
    Fixture failed=new Fixture(new byte[]{4});failed.activity.rejectPicker=true;ui(()->{failed.action.export(failed.source);return null;});check("Missing picker leaves retryable state and clear feedback",failed.action.exporting==null&&!failed.action.busy&&!failed.activity.problems.isEmpty());
  }
  static void destinationLease()throws Exception{
    Fixture f=new Fixture(new byte[]{5,6});byte[] existing={9,8,7};CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1);CompletableFuture<Void> publisher=CompletableFuture.runAsync(()->{try{SavedFileDeletion.lease(f.activity,f.provider.destination,()->{Files.write(f.provider.target.toPath(),existing);held.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new AssertionError("destination publisher");DownloadLibrary.get(f.activity).indexed.add(f.provider.destination.toString());return null;});}catch(Exception error){throw new CompletionException(error);}});
    if(!held.await(5,TimeUnit.SECONDS))throw new AssertionError("destination lease not held");Thread worker=f.action.worker.submit(()->Thread.currentThread()).get(5,TimeUnit.SECONDS);f.select();long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);boolean waiting;
    do{waiting=false;for(StackTraceElement frame:worker.getStackTrace())if(frame.getClassName().equals("local.pocketchat.SealedFileIo")&&frame.getMethodName().equals("lease"))waiting=true;if(!waiting)Thread.yield();}while(!waiting&&System.nanoTime()<deadline);
    check("Copy waits for existing destination publication lease",waiting&&f.provider.outputOpens==0);release.countDown();publisher.get(5,TimeUnit.SECONDS);f.idle();
    check("Index recheck under destination lease preserves newly published bytes",Arrays.equals(Files.readAllBytes(f.provider.target.toPath()),existing)&&f.provider.outputOpens==0&&f.provider.deletes==0&&!f.activity.problems.isEmpty());
  }
  static void cleanupUnconfirmed()throws Exception{
    for(String fault:new String[]{"refused","exception","closed-refused"}){
      byte[] original={11,12,13};Fixture f=new Fixture(original);f.provider.fault="output-close";f.provider.deletionFault=fault;
      if(fault.equals("exception"))f.provider.destination=Uri.parse("content://documents.test/refused-target");
      if(fault.equals("closed-refused"))f.provider.onOutputClose=()->{try{ui(()->{f.action.close();return null;});}catch(Exception error){throw new CompletionException(error);}};
      f.select();f.idle();
      check("Cleanup "+fault+" cannot convert failed copy into success",!f.action.busy&&f.provider.deletes==1&&f.provider.target.isFile());
      check("Cleanup "+fault+" preserves the source file",Arrays.equals(Files.readAllBytes(f.provider.source.toPath()),original));
      check("Cleanup "+fault+" gives only current owner accurate uncertainty",fault.equals("closed-refused")?f.activity.problems.isEmpty():f.activity.problems.size()==1&&f.activity.problems.get(0).equals("原文件已保留，目标副本清理未确认，请检查保存位置"));
    }
  }
  public static void main(String[] args)throws Exception{
    try{streams();retiredCopies();admission();destinationLease();cleanupUnconfirmed();}
    finally{for(SavedFileActions action:actions)action.worker.shutdownNow();}
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;
    System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);
  }
}

final class FaultProvider extends ContentResolver {
  final Uri original=Uri.parse("content://copy.test/original");Uri destination=Uri.parse("content://copy.test/destination");final File source,target;
  String fault="",deletionFault="";int outputOpens,deletes;Runnable onEof,onOutputClose;
  FaultProvider(File root,byte[] bytes)throws Exception{source=new File(root,"original.bin");target=new File(root,"destination.bin");Files.write(source.toPath(),bytes);}
  public InputStream openInputStream(Uri uri)throws IOException{
    if(!original.equals(uri))throw new AssertionError("Unexpected source URI");if(fault.equals("null-input"))return null;
    return new FilterInputStream(new FileInputStream(source)){
      public int read(byte[] bytes,int offset,int length)throws IOException{int count=in.read(bytes,offset,length);if(count==-1&&onEof!=null){Runnable action=onEof;onEof=null;action.run();}return count;}
      public void close()throws IOException{super.close();if(fault.equals("input-close"))throw new IOException("Input close failure");}
    };
  }
  public OutputStream openOutputStream(Uri uri,String mode)throws IOException{
    if(!destination.equals(uri)||!"wt".equals(mode))throw new AssertionError("Unexpected destination open");outputOpens++;if(fault.equals("null-output"))return null;
    return new FilterOutputStream(new FileOutputStream(target)){
      public void write(byte[] bytes,int offset,int length)throws IOException{if(fault.equals("write")){out.write(bytes,offset,1);throw new IOException("Write failure");}out.write(bytes,offset,length);}
      public void flush()throws IOException{if(fault.equals("flush"))throw new IOException("Flush failure");out.flush();}
      public void close()throws IOException{if(onOutputClose!=null){Runnable action=onOutputClose;onOutputClose=null;action.run();}out.close();if(fault.equals("output-close")||fault.equals("document-close"))throw new IOException("Provider close failure");}
    };
  }
  public int delete(Uri uri,String where,String[] args){if(!destination.equals(uri))throw new AssertionError("Copy must never delete source");deletes++;if(deletionFault.equals("exception"))throw new SecurityException("Controlled delete refusal");if(!deletionFault.isEmpty())return 0;return target.delete()?1:0;}
}
final class SavedFileActions {
  static final int EXPORT=85;final Activity a;final ExecutorService worker=Executors.newSingleThreadExecutor();final Handler main=new Handler(Looper.getMainLooper());JSONObject exporting;volatile boolean closed,busy;long detailEpoch;AlertDialog detailDialog;
  SavedFileActions(Activity activity){a=activity;}
  static void problem(Activity activity,String message){activity.problems.add(message);}
  /* SAVEDFILEACTIONS */
}
final class DownloadMetadataValues {/* METADATA */}
final class Profiles {static Context global(Context context){return context;}}
final class AppUpdatePolicy {static String hash(byte[] bytes){try{byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder out=new StringBuilder();for(byte value:digest)out.append(String.format(java.util.Locale.ROOT,"%02x",value&255));return out.toString();}catch(java.security.NoSuchAlgorithmException impossible){throw new AssertionError(impossible);}}}
/** Index admission only; saved-file deletion and database persistence are unsupported. */
final class DownloadLibrary {
  static final Map<Context,DownloadLibrary> values=new ConcurrentHashMap<>();final Set<String> indexed=ConcurrentHashMap.newKeySet();static DownloadLibrary get(Context context){return values.computeIfAbsent(context,key->new DownloadLibrary());}
  boolean indexed(Uri uri){return indexed.contains(uri.toString());}
  boolean isRemoved(JSONObject row){throw new AssertionError("Saved-file deletion outside copy host");}JSONObject saved(JSONObject row){throw new AssertionError("Saved-file lookup outside copy host");}void removeSaved(JSONObject row){throw new AssertionError("Saved-file deletion outside copy host");}
}
final class SavedDownloadProvider {static File resolve(Context context,Uri uri){throw new AssertionError("Owned-provider deletion outside copy host");}}
