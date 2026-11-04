package local.pocketchat;

import android.content.Context;import android.net.Uri;import android.os.*;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;import java.util.concurrent.locks.ReentrantLock;import org.json.*;

/** Real production file stripes and Java concurrency; app Context/main-loop are declared adapters. */
public final class CollectionLeaseCases{
 static final JSONArray checks=new JSONArray();static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 static String stripe(Context c,Uri uri)throws Exception{File target=new File(new File(Profiles.global(c).getNoBackupFilesDir(),"saved-download-leases"),AppUpdatePolicy.hash(uri.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));return SealedFileIo.lockFile(target).getCanonicalPath();}
 static void sameStripe(Context context)throws Exception{
  Map<String,Uri> seen=new HashMap<>();Uri first=null,second=null;for(int i=0;i<1000;i++){Uri uri=Uri.parse("content://fixture/collision-"+i);String key=stripe(context,uri);if(seen.containsKey(key)){first=seen.get(key);second=uri;break;}seen.put(key,uri);}
  check("Constructed two different URIs sharing the actual production stripe",first!=null&&second!=null&&!first.equals(second));
  SavedFileDeletion.leaseAll(context,Arrays.asList(first,second,first),()->{
   java.lang.reflect.Field gates=SealedFileIo.class.getDeclaredField("gates");gates.setAccessible(true);Map<?,?> active=(Map<?,?>)gates.get(null);check("Duplicate URIs and stripe collisions acquire exactly one gate",active.size()==1);Object gate=active.values().iterator().next();java.lang.reflect.Field lock=gate.getClass().getDeclaredField("lock");lock.setAccessible(true);check("Colliding stripe is acquired once without nested same-stripe holds",((ReentrantLock)lock.get(gate)).getHoldCount()==1);return null;
  });
 }
 static void reverseOrder(Context context)throws Exception{
  List<Uri> forward=new ArrayList<>();for(int i=0;i<30;i++)forward.add(Uri.parse("content://fixture/order-"+i));List<Uri> reverse=new ArrayList<>(forward);Collections.reverse(reverse);
  AtomicInteger bodies=new AtomicInteger();CountDownLatch begin=new CountDownLatch(1);ExecutorService workers=Executors.newFixedThreadPool(2);try{
   Future<?> one=workers.submit(()->{try{begin.await();for(int i=0;i<50;i++)SavedFileDeletion.leaseAll(context,forward,()->{bodies.incrementAndGet();return null;});}catch(Exception error){throw new RuntimeException(error);}});
   Future<?> two=workers.submit(()->{try{begin.await();for(int i=0;i<50;i++)SavedFileDeletion.leaseAll(context,reverse,()->{bodies.incrementAndGet();return null;});}catch(Exception error){throw new RuntimeException(error);}});
   begin.countDown();one.get(10,TimeUnit.SECONDS);two.get(10,TimeUnit.SECONDS);check("Opposite URI orders complete 100 multi-file operations without deadlock",bodies.get()==100);
  }finally{workers.shutdownNow();}
 }
 static void throughDispatch(Context context)throws Exception{
  Uri one=Uri.parse("content://fixture/grant-a"),two=Uri.parse("content://fixture/grant-b");CountDownLatch validated=new CountDownLatch(1),mainReached=new CountDownLatch(1),allowGrant=new CountDownLatch(1),writerWaiting=new CountDownLatch(1);AtomicBoolean writerEntered=new AtomicBoolean(),granted=new AtomicBoolean();ExecutorService workers=Executors.newFixedThreadPool(2);
  try{
   Future<?> share=workers.submit(()->{try{SavedFileDeletion.leaseAll(context,Arrays.asList(one,two),()->{validated.countDown();SavedFileDeletion.onMain(new Handler(Looper.getMainLooper()),()->{mainReached.countDown();try{allowGrant.await();}catch(InterruptedException error){throw new RuntimeException(error);}check("Full validation precedes grant callback",validated.getCount()==0);check("Earlier URI cannot be republished before grant callback",!writerEntered.get());granted.set(true);});return null;});}catch(Exception error){throw new RuntimeException(error);}});
   check("Grant callback reached without blocking the main thread on a lease",mainReached.await(3,TimeUnit.SECONDS));
   Future<?> writer=workers.submit(()->{try{writerWaiting.countDown();SavedFileDeletion.lease(context,one,()->{writerEntered.set(true);check("Writer proceeds after grant dispatch",granted.get());return null;});}catch(Exception error){throw new RuntimeException(error);}});
   check("Contending writer started",writerWaiting.await(3,TimeUnit.SECONDS));check("Grant is still awaiting explicit callback release",!granted.get());allowGrant.countDown();share.get(5,TimeUnit.SECONDS);writer.get(5,TimeUnit.SECONDS);check("All leases release after grant handoff",writerEntered.get());
  }finally{allowGrant.countDown();workers.shutdownNow();}
 }
 public static void main(String[] args)throws Exception{File root=Files.createTempDirectory("collection-leases-").toFile();Context context=new Context(root,0);sameStripe(context);reverseOrder(context);throughDispatch(context);int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).getBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","total",checks.length(),"passed",passed,"checks",checks,"actualAndroidExecution",false,"scope","real SealedFileIo/SavedFileDeletion locks and main handoff, JVM concurrency with explicit Context/main adapters").toString());}
}
