package local.pocketchat;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Exercises slow storage, profile separation, real atomic replacements, and stale-reader races. */
public final class FileSnapshotCacheTest {
  static int checks;
  static void check(boolean passed,String message){if(!passed)throw new AssertionError(message);checks++;}
  static File write(Path path,String value)throws Exception{Files.writeString(path,value);return path.toFile();}
  public static void main(String[] args)throws Exception{
    Path directory=Files.createTempDirectory("network-snapshot-test-");ExecutorService worker=Executors.newSingleThreadExecutor();
    try{
      FileSnapshotCache<String> cache=new FileSnapshotCache<>(worker,()->"");AtomicInteger decrypts=new AtomicInteger();
      List<File> files=new ArrayList<>();for(int i=0;i<8;i++)files.add(write(directory.resolve("env"+i),"region-"+i));
      boolean isolated=true;for(int round=0;round<16;round++)for(int i=0;i<8;i++){File file=files.get(i);String value=cache.read(file,false,()->{decrypts.incrementAndGet();return Files.readString(file.toPath());},null);isolated&=value.equals("region-"+i);}
      check(isolated,"Regions must remain isolated per file");
      check(decrypts.get()==8,"Alternating eight profiles must decrypt only once each");
      File slow=write(directory.resolve("slow"),"slow-region");CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
      FileSnapshotCache.Loader<String> slowLoader=()->{entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("fixture blocked");return "slow-region";};
      check(cache.read(slow,true,slowLoader,null).isEmpty(),"Cold UI read returns empty without waiting for storage");
      check(entered.await(3,TimeUnit.SECONDS),"The storage load runs on the worker");long began=System.nanoTime();
      boolean responsive=true;for(int i=0;i<1000;i++)responsive&=cache.read(slow,true,slowLoader,null).isEmpty();check(responsive,"UI does not wait for the blocked reader");
      check((System.nanoTime()-began)/1000000<250,"A thousand UI reads stay responsive during blocked storage");
      release.countDown();worker.submit(()->{}).get(3,TimeUnit.SECONDS);check(cache.read(slow,true,slowLoader,null).equals("slow-region"),"The loaded snapshot becomes visible without another blocking read");
      File replacement=files.get(2);Path next=directory.resolve("next");write(next,"new-reg2");Files.setLastModifiedTime(next,Files.getLastModifiedTime(replacement.toPath()));Files.move(next,replacement.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
      check(cache.read(replacement,false,()->Files.readString(replacement.toPath()),null).equals("new-reg2"),"Atomic same-size same-time replacements are detected by inode");
      Files.delete(replacement.toPath());check(cache.read(replacement,false,()->"must-not-read",null).isEmpty(),"Deleted region files do not retain the previous snapshot");
      write(replacement.toPath(),"recreated");check(cache.read(replacement,false,()->Files.readString(replacement.toPath()),null).equals("recreated"),"A recreated profile file is loaded again");
      File corrupt=write(directory.resolve("corrupt"),"invalid-ciphertext");check(cache.read(corrupt,false,()->{throw new IOException("cannot decrypt");},null).isEmpty(),"Unreadable records expose no previous data");
      write(corrupt.toPath(),"repaired-ciphertext");check(cache.read(corrupt,false,()->"repaired-region",null).equals("repaired-region"),"A repaired sealed record becomes readable");
      File race=write(directory.resolve("race"),"old");CountDownLatch raceEntered=new CountDownLatch(1),raceRelease=new CountDownLatch(1);
      cache.read(race,true,()->{raceEntered.countDown();raceRelease.await(3,TimeUnit.SECONDS);return "old";},null);check(raceEntered.await(2,TimeUnit.SECONDS),"The stale-reader race starts");
      cache.publish(race,"new-confirmed-region");raceRelease.countDown();worker.submit(()->{}).get(3,TimeUnit.SECONDS);
      check(cache.read(race,true,()->"old",null).equals("new-confirmed-region"),"A completed write cannot be overwritten by an older queued read");
      System.out.println("{\"passed\":"+checks+",\"total\":"+checks+",\"scope\":\"Nonblocking metadata reads, eight profile paths, atomic replacement and stale-reader cancellation\"}");
    }finally{worker.shutdownNow();try(java.util.stream.Stream<Path> paths=Files.walk(directory)){paths.sorted(Comparator.reverseOrder()).forEach(path->{try{Files.deleteIfExists(path);}catch(IOException ignored){}});}}
  }
}
