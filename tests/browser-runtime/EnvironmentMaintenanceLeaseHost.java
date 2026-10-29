package local.pocketchat;

import java.io.File;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Runs the production lease on a real temporary filesystem and Java threads. */
public final class EnvironmentMaintenanceLeaseHost {
  static int passed;
  static void check(boolean value)throws Exception{if(!value)throw new AssertionError("Maintenance lease assertion "+passed);passed++;}
  static void await(CountDownLatch latch)throws Exception{if(!latch.await(5,TimeUnit.SECONDS))throw new AssertionError("Bounded gate timed out");}
  public static void main(String[] args)throws Exception{
    final File root=new File(args[0]);
    if(args.length>1){
      Files.write(new File(root,"child-before").toPath(),new byte[]{1});
      EnvironmentMaintenanceLease.with(root,2,()->{Files.write(new File(root,"child-entered").toPath(),new byte[]{1});return null;});return;
    }
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1),secondAttempt=new CountDownLatch(1);AtomicBoolean secondEntered=new AtomicBoolean(),otherEntered=new AtomicBoolean();
    Thread first=new Thread(()->{try{EnvironmentMaintenanceLease.with(root,1,()->{entered.countDown();await(release);return null;});}catch(Exception error){throw new RuntimeException(error);}});
    first.start();await(entered);
    Thread second=new Thread(()->{try{secondAttempt.countDown();EnvironmentMaintenanceLease.with(root,1,()->{secondEntered.set(true);return null;});}catch(Exception error){throw new RuntimeException(error);}});second.start();await(secondAttempt);
    EnvironmentMaintenanceLease.with(root,0,()->{otherEntered.set(true);return null;});
    Thread.sleep(100);check(!secondEntered.get()&&otherEntered.get());release.countDown();first.join(5000);second.join(5000);check(!first.isAlive()&&!second.isAlive()&&secondEntered.get());
    boolean failed=false;try{EnvironmentMaintenanceLease.with(root,1,()->{throw new java.io.IOException("synthetic action failure");});}catch(java.io.IOException expected){failed=true;}check(failed);check(EnvironmentMaintenanceLease.with(root,1,()->true));
    File lock=new File(root,"browser-maintenance-env1.lock");Object inode=Files.getAttribute(lock.toPath(),"unix:ino");EnvironmentMaintenanceLease.with(root,1,()->true);check(inode.equals(Files.getAttribute(lock.toPath(),"unix:ino")));
    for(int slot:new int[]{-1,8}){failed=false;try{EnvironmentMaintenanceLease.with(root,slot,()->true);}catch(java.io.IOException expected){failed=true;}check(failed);}
    File link=new File(root,"browser-maintenance-env3.lock"),target=new File(root,"untouched-target");Files.write(target.toPath(),new byte[]{7});Files.createSymbolicLink(link.toPath(),target.toPath());failed=false;try{EnvironmentMaintenanceLease.with(root,3,()->{Files.write(target.toPath(),new byte[]{9});return null;});}catch(java.io.IOException expected){failed=true;}check(failed&&Files.readAllBytes(target.toPath())[0]==7);
    File rootLink=new File(root,"linked-root");Files.createSymbolicLink(rootLink.toPath(),root.toPath());failed=false;try{EnvironmentMaintenanceLease.with(rootLink,0,()->true);}catch(java.io.IOException expected){failed=true;}check(failed);
    String java=new File(System.getProperty("java.home"),"bin/java").getPath();Process[] child=new Process[1];
    EnvironmentMaintenanceLease.with(root,2,()->{
      File removedEnvironment=new File(root,"profiles/env2");removedEnvironment.mkdirs();Files.delete(removedEnvironment.toPath());
      child[0]=new ProcessBuilder(java,"-cp",System.getProperty("java.class.path"),EnvironmentMaintenanceLeaseHost.class.getName(),root.getPath(),"child").redirectErrorStream(true).start();
      long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(!new File(root,"child-before").isFile()&&System.nanoTime()<until)Thread.sleep(10);
      check(new File(root,"child-before").isFile());Thread.sleep(200);check(!new File(root,"child-entered").exists());return null;
    });
    check(child[0].waitFor(5,TimeUnit.SECONDS)&&child[0].exitValue()==0&&new File(root,"child-entered").isFile());
    System.out.println("{\"status\":\"passed\",\"passed\":"+passed+",\"actualAndroidExecution\":false,\"actualProductionLeaseExecution\":true}");
  }
}
