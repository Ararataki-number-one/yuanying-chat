package local.pocketchat;

import android.util.AtomicFile;
import java.io.*;
import java.nio.channels.FileLock;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantLock;

public final class SealedFileIoHostTest {
  static final int EXPECTED_CHECKS=32;
  static final List<String> checks=new ArrayList<>();
  static final List<Boolean> outcomes=new ArrayList<>();
  static boolean crossJvm;
  static byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
  static void check(String name,boolean pass){checks.add(name);outcomes.add(pass);if(!pass)throw new AssertionError(name);}
  static void marker(Path root,String name)throws IOException{Files.writeString(root.resolve(name),"ready");}
  static void waitMarker(Path root,String name,Process child)throws Exception{
    long end=System.nanoTime()+15_000_000_000L;
    while(!Files.exists(root.resolve(name))){if(!child.isAlive()||System.nanoTime()>end)throw new IOException("Child barrier failed "+name);Thread.sleep(5);}
  }
  @SuppressWarnings("unchecked") static Map<String,Object> gates()throws Exception{
    java.lang.reflect.Field field=SealedFileIo.class.getDeclaredField("gates");field.setAccessible(true);return (Map<String,Object>)field.get(null);
  }
  static void waitQueued(File file,Thread thread)throws Exception{
    Map<String,Object> gates=gates();long end=System.nanoTime()+10_000_000_000L;
    while(true){synchronized(gates){Object gate=gates.get(SealedFileIo.lockFile(file).getCanonicalPath());if(gate!=null){java.lang.reflect.Field field=gate.getClass().getDeclaredField("lock");field.setAccessible(true);if(((ReentrantLock)field.get(gate)).hasQueuedThread(thread))return;}}
      if(!thread.isAlive()||System.nanoTime()>end)throw new IOException("Thread did not queue at the actual JVM stripe gate");Thread.sleep(1);
    }
  }
  static void child(String mode,Path root)throws Exception{
    File target=root.resolve("state.sealed").toFile();
    if(mode.equals("writer")){
      SealedFileIo.publish(target,new byte[0],bytes("child-new"),file->{marker(root,"writer-paused");long end=System.nanoTime()+30_000_000_000L;while(!Files.exists(root.resolve("writer-release"))){if(System.nanoTime()>end)throw new IOException("Writer release timed out");Thread.sleep(5);}});
    }else{
      // This marker is emitted only after the independent JVM has attempted
      // the actual OS stripe lock and observed that the writer owns it.
      try(RandomAccessFile handle=new RandomAccessFile(SealedFileIo.lockFile(target),"rw")){
        FileLock attempt=handle.getChannel().tryLock();if(attempt!=null){attempt.release();throw new AssertionError("Separate JVM acquired the writer's supposedly held OS lock");}
      }
      marker(root,"reader-attempted-lock");Files.write(root.resolve("reader-result"),SealedFileIo.read(target));
    }
  }
  static void run()throws Exception{
    Path root=Files.createTempDirectory("sealed-file-io-host-");File target=root.resolve("state.sealed").toFile();
    SealedFileIo.publish(target,bytes("old"));AtomicFile unsafe=new AtomicFile(target);FileOutputStream pending=unsafe.startWrite();pending.write(bytes("unsafe-new"));
    check("Unprotected baseline creates a pending .new file",new File(target+".new").isFile());byte[] observed=new AtomicFile(target).readFully();
    check("Unprotected openRead removes a different writer's .new file",Arrays.equals(observed,bytes("old"))&&!new File(target+".new").exists());unsafe.finishWrite(pending);
    check("Unprotected finishWrite can return normally without publishing",Arrays.equals(Files.readAllBytes(target.toPath()),bytes("old")));
    AtomicFile.failRenameOnce=true;boolean failure=false;try{SealedFileIo.publish(target,bytes("not-published"));}catch(IOException expected){failure=true;}
    check("Formal publication turns quiet rename failure into IOException",failure);
    check("Rejected rename publication clears its pending .new file",!new File(target+".new").exists());
    check("Rejected rename publication retains the last committed bytes",Arrays.equals(SealedFileIo.read(target),bytes("old")));
    ExecutorService jobs=Executors.newFixedThreadPool(3);
    try{
      CountDownLatch reached=new CountDownLatch(1),release=new CountDownLatch(1);AtomicReference<Thread> readerThread=new AtomicReference<>();
      Future<?> writer=jobs.submit(()->{try{SealedFileIo.publish(target,new byte[0],bytes("thread-new"),file->{reached.countDown();if(!release.await(10,TimeUnit.SECONDS))throw new IOException("Release timeout");});}catch(Exception e){throw new RuntimeException(e);}});
      try{
        check("Formal writer reaches an actual startWrite barrier",reached.await(10,TimeUnit.SECONDS)&&new File(target+".new").isFile());
        CountDownLatch readerStarted=new CountDownLatch(1);Future<byte[]> reader=jobs.submit(()->{readerThread.set(Thread.currentThread());readerStarted.countDown();return SealedFileIo.read(target);});
        if(!readerStarted.await(10,TimeUnit.SECONDS))throw new IOException("Reader did not start");waitQueued(target,readerThread.get());
        check("Formal reader waits instead of deleting an active .new",!reader.isDone()&&new File(target+".new").isFile());release.countDown();writer.get(10,TimeUnit.SECONDS);
        check("Formal reader receives the complete newly published value",Arrays.equals(reader.get(10,TimeUnit.SECONDS),bytes("thread-new")));
      }finally{release.countDown();}
      CountDownLatch deleteReached=new CountDownLatch(1),deleteRelease=new CountDownLatch(1);AtomicReference<Thread> removerThread=new AtomicReference<>();
      Future<?> deleteWriter=jobs.submit(()->{try{SealedFileIo.publish(target,new byte[0],bytes("remove-after-write"),file->{deleteReached.countDown();if(!deleteRelease.await(10,TimeUnit.SECONDS))throw new IOException("Delete barrier timeout");});}catch(Exception e){throw new RuntimeException(e);}});
      try{
        if(!deleteReached.await(10,TimeUnit.SECONDS))throw new IOException("Delete writer did not start");CountDownLatch removerStarted=new CountDownLatch(1);
        Future<?> remover=jobs.submit(()->{removerThread.set(Thread.currentThread());removerStarted.countDown();try{SealedFileIo.remove(target);}catch(Exception e){throw new RuntimeException(e);}});
        if(!removerStarted.await(10,TimeUnit.SECONDS))throw new IOException("Remover did not start");waitQueued(target,removerThread.get());
        check("Formal remove waits for publication before removing the record",!remover.isDone()&&new File(target+".new").exists());deleteRelease.countDown();deleteWriter.get(10,TimeUnit.SECONDS);remover.get(10,TimeUnit.SECONDS);
        check("Formal remove clears base and pending publication",!target.exists()&&!new File(target+".new").exists());
      }finally{deleteRelease.countDown();}
    }finally{jobs.shutdownNow();if(!jobs.awaitTermination(10,TimeUnit.SECONDS))throw new IOException("Host workers did not terminate");}
    SealedFileIo.publish(target,bytes("old"));String javaCommand=System.getProperty("java.home")+"/bin/java",cp=System.getProperty("java.class.path");
    Process childWriter=new ProcessBuilder(javaCommand,"-cp",cp,SealedFileIoHostTest.class.getName(),"writer",root.toString()).inheritIO().start(),childReader=null;
    try{
      waitMarker(root,"writer-paused",childWriter);childReader=new ProcessBuilder(javaCommand,"-cp",cp,SealedFileIoHostTest.class.getName(),"reader",root.toString()).inheritIO().start();waitMarker(root,"reader-attempted-lock",childReader);
      check("A separate JVM actually attempts and observes the held OS stripe lock",Files.exists(root.resolve("reader-attempted-lock")));
      check("A separate JVM reader cannot destroy a pending publication",!childReader.waitFor(300,TimeUnit.MILLISECONDS)&&!Files.exists(root.resolve("reader-result"))&&new File(target+".new").exists());marker(root,"writer-release");
      check("Cross-JVM writer commits successfully",childWriter.waitFor(15,TimeUnit.SECONDS)&&childWriter.exitValue()==0);
      check("Cross-JVM reader observes the complete committed value",childReader.waitFor(15,TimeUnit.SECONDS)&&childReader.exitValue()==0&&Arrays.equals(Files.readAllBytes(root.resolve("reader-result")),bytes("child-new")));crossJvm=true;
    }finally{marker(root,"writer-release");if(childWriter.isAlive())childWriter.destroyForcibly();if(childReader!=null&&childReader.isAlive())childReader.destroyForcibly();}
    File collision=null;for(int i=0;i<10000;i++){File next=root.resolve("collision-"+i+".sealed").toFile();if(SealedFileIo.lockFile(next).equals(SealedFileIo.lockFile(target))){collision=next;break;}}final File sameStripe=collision;
    check("Fixture finds two different physical files sharing one stable stripe",sameStripe!=null&&!sameStripe.equals(target));
    SealedFileIo.lease(target,()->{SealedFileIo.publish(sameStripe,bytes("nested"));return null;});
    check("Nested access to a different file on the same stripe is reentrant",Arrays.equals(SealedFileIo.read(sameStripe),bytes("nested"))&&Arrays.equals(SealedFileIo.read(target),bytes("child-new")));
    File stableLock=SealedFileIo.lockFile(target);Object inode=Files.getAttribute(stableLock.toPath(),"unix:ino");
    for(int i=0;i<256;i++){File temporary=root.resolve("ephemeral-"+i+".sealed").toFile();SealedFileIo.publish(temporary,bytes("value"));SealedFileIo.remove(temporary);}
    long lockCount;boolean noPayloads;try(java.util.stream.Stream<Path> files=Files.list(root)){lockCount=files.filter(path->path.getFileName().toString().matches("sealed-io-[0-9]{2}[.]lock")).count();}
    try(java.util.stream.Stream<Path> files=Files.list(root)){noPayloads=files.noneMatch(path->path.getFileName().toString().startsWith("ephemeral-"));}
    check("Dynamic cache slot churn creates at most 64 persistent lock inodes",lockCount>0&&lockCount<=64);
    check("Removed dynamic slots leave no committed or pending payload files",noPayloads);
    check("Payload removal never replaces or unlinks a stable stripe inode",stableLock.isFile()&&inode.equals(Files.getAttribute(stableLock.toPath(),"unix:ino")));
    check("Missing records return null without treating .lock files as data",SealedFileIo.read(root.resolve("missing.sealed").toFile())==null);
    File recovered=root.resolve("legacy-backup.sealed").toFile();Files.write(new File(recovered.getPath()+".bak").toPath(),bytes("legacy-recovered"));
    check("Legacy backup recovery remains readable under the formal lease",Arrays.equals(SealedFileIo.read(recovered),bytes("legacy-recovered"))&&recovered.isFile()&&!new File(recovered.getPath()+".bak").exists());
    byte[] prefix=bytes("IV-prefix"),payload=new byte[20000];for(int i=0;i<payload.length;i++)payload[i]=(byte)i;File large=root.resolve("prefix-and-payload.sealed").toFile();SealedFileIo.publish(large,prefix,payload,null);
    check("Publication verifies prefix and complete multi-chunk payload",SealedFileIo.published(large,prefix,payload));
    byte[] altered=Files.readAllBytes(large.toPath());altered[0]^=1;Files.write(large.toPath(),altered);
    check("Publication verification rejects same-length prefix corruption",!SealedFileIo.published(large,prefix,payload));
    altered[0]^=1;altered[altered.length-1]^=1;Files.write(large.toPath(),altered);
    check("Publication verification rejects same-length payload-tail corruption",!SealedFileIo.published(large,prefix,payload));
    Files.write(large.toPath(),Arrays.copyOf(altered,altered.length-1));boolean shortRejected=!SealedFileIo.published(large,prefix,payload);Files.write(large.toPath(),Arrays.copyOf(altered,altered.length+1));
    check("Publication verification rejects shortened and extra payload bytes",shortRejected&&!SealedFileIo.published(large,prefix,payload));
    File physical=root.resolve("physical.sealed").toFile(),alias=root.resolve("symbolic.sealed").toFile();SealedFileIo.publish(physical,bytes("physical-old"));Files.createSymbolicLink(alias.toPath(),physical.toPath());
    check("Canonical file aliases share the same stable stripe gate",SealedFileIo.lockFile(alias).equals(SealedFileIo.lockFile(physical)));
    SealedFileIo.publish(alias,bytes("physical-new"));check("Publication through an alias preserves the physical file and symlink",Files.isSymbolicLink(alias.toPath())&&Arrays.equals(SealedFileIo.read(physical),bytes("physical-new")));
    SealedFileIo.remove(alias);check("Removal through an alias clears the physical payload under its lease",!physical.exists()&&Files.isSymbolicLink(alias.toPath()));
    CountDownLatch ownerReached=new CountDownLatch(1),ownerRelease=new CountDownLatch(1);AtomicReference<Throwable> ownerFailure=new AtomicReference<>(),waiterFailure=new AtomicReference<>();AtomicReference<Boolean> interrupted=new AtomicReference<>(false);
    Thread owner=new Thread(()->{try{SealedFileIo.lease(target,()->{ownerReached.countDown();if(!ownerRelease.await(10,TimeUnit.SECONDS))throw new IOException("Queue owner release timed out");return null;});}catch(Throwable error){ownerFailure.set(error);}},"stripe-owner");
    Thread waiter=new Thread(()->{try{SealedFileIo.read(target);waiterFailure.set(new AssertionError("Interrupted waiter entered the protected action"));}catch(InterruptedException expected){interrupted.set(true);}catch(Throwable error){waiterFailure.set(error);}},"stripe-interrupted-waiter");
    try{owner.start();if(!ownerReached.await(10,TimeUnit.SECONDS))throw new IOException("Queue owner did not start");waiter.start();waitQueued(target,waiter);
      check("A queued JVM waiter retains the same live canonical gate",gates().size()==1&&owner.isAlive()&&waiter.isAlive());waiter.interrupt();waiter.join(10000);
      check("Interrupted stripe acquisition exits without entering protected I/O",!waiter.isAlive()&&interrupted.get()&&waiterFailure.get()==null);
    }finally{ownerRelease.countDown();owner.join(10000);waiter.interrupt();waiter.join(10000);}
    SealedFileIo.publish(target,bytes("post-interrupt"));
    check("Completed and interrupted leases release all JVM gate references",!owner.isAlive()&&ownerFailure.get()==null&&gates().isEmpty()&&Arrays.equals(SealedFileIo.read(target),bytes("post-interrupt"))&&gates().isEmpty());
    if(checks.size()!=EXPECTED_CHECKS)throw new AssertionError("Expected "+EXPECTED_CHECKS+" checks, executed "+checks.size());
  }
  static String quote(String value){return "\""+value.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";}
  static void report(Throwable failure){int passed=0;StringJoiner rows=new StringJoiner(",");for(int i=0;i<checks.size();i++){if(outcomes.get(i))passed++;rows.add("{\"name\":"+quote(checks.get(i))+",\"pass\":"+outcomes.get(i)+"}");}
    System.out.println("{\"status\":"+quote(failure==null?"passed":"failed")+",\"passed\":"+passed+",\"total\":"+EXPECTED_CHECKS+",\"executed\":"+checks.size()+",\"actualAndroidExecution\":false,\"actualKeystoreEncryption\":false,\"actualAtomicFileBehaviorStub\":true,\"actualCrossJvmStorageLease\":"+crossJvm+",\"failure\":"+quote(failure==null?"":failure.toString())+",\"checks\":["+rows+"]}");
  }
  public static void main(String[] args)throws Exception{
    if(args.length>0){child(args[0],Path.of(args[1]));return;}
    Throwable failure=null;try{run();}catch(Throwable error){failure=error;error.printStackTrace(System.err);}report(failure);if(failure!=null)System.exit(1);
  }
}
