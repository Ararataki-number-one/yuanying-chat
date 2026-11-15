package local.pocketchat;

import static local.pocketchat.DownloadResumeHost.*;
import android.net.Uri;
import java.io.*;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.concurrent.*;
import org.json.JSONObject;

/** Real production cancellation, task claims, workers and file leases.
 * The Activity/provider adapters are the existing download-resume host boundary. */
final class CancelCases {
  static final class Gate implements AutoCloseable {
    final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
    Gate(FileDownloads downloads)throws Exception{
      downloads.worker.execute(()->{entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("cancel queue barrier");}catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(error);}});
      if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("cancel worker did not enter");
    }
    public void close(){release.countDown();}
  }
  static FileDownloads reopen(FileDownloads old)throws Exception{
    FileDownloads next=ui(()->new FileDownloads(new MainActivity(old.a.root)));downloads.add(next);
    DownloadTasks.recovery.submit(()->{}).get(5,TimeUnit.SECONDS);ui(()->null);return next;
  }
  static JSONObject selected(FileDownloads d,String id)throws Exception{
    return ui(()->{JSONObject row=DownloadTaskRevisions.find(d.tasks.rows,id);if(row==null||!d.loadTask(row))throw new AssertionError("new Activity claim");return row;});
  }
  static void staleOwner()throws Exception{
    FileDownloads old=fresh();JSONObject row=row(old,"http-range");File file=partial(old,"download-cancel-owner.part");attach(old,row,file);
    ui(()->{old.resumeValidator="\"cancel-owner\"";old.resumeAddress="https://example.test/file";old.sourceId="file-id";old.mark("paused","");return null;});
    try(Gate queued=new Gate(old)){
      ui(()->{old.cancel();old.destroy();return null;});FileDownloads next=reopen(old);JSONObject current=selected(next,row.optString("id"));
      CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1);byte[] nextBytes={7,8,9,10,11};
      Future<?> writer=next.worker.submit(()->{try{SealedFileIo.lease(file,()->{Files.write(file.toPath(),nextBytes);held.countDown();if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("new writer lease barrier");return null;});}catch(Exception error){throw new CompletionException(error);}});
      if(!held.await(5,TimeUnit.SECONDS))throw new AssertionError("new writer did not acquire lease");
      queued.close();boolean drained=old.worker.awaitTermination(5,TimeUnit.SECONDS);
      check("Cancelled old worker cannot unlink a newly claimed writer's leased file",drained&&file.isFile()&&Arrays.equals(Files.readAllBytes(file.toPath()),nextBytes));
      check("Cancelled old worker cannot release the new Activity task owner",ui(()->next.tasks.owns(current)));
      release.countDown();writer.get(5,TimeUnit.SECONDS);
    }
  }
  static void retiredBeforeQueue()throws Exception{
    FileDownloads old=fresh();JSONObject row=row(old,"gecko-response");File file=partial(old,"download-cancel-complete-owner.part");attach(old,row,file);
    ui(()->{old.completeFile=true;old.mark("paused","等待选择保存位置");return null;});
    try(Gate queued=new Gate(old)){
      ui(()->{old.cancel();old.destroy();return null;});FileDownloads next=reopen(old);JSONObject current=selected(next,row.optString("id"));queued.close();old.worker.awaitTermination(5,TimeUnit.SECONDS);ui(()->null);
      check("Uncommitted cancellation retains a complete copy for the new owner to save",file.isFile()&&current.optBoolean("complete")&&DownloadResumePolicy.SAVE.equals(ui(()->next.continuationAction(current))));
    }
  }
  static void pending()throws Exception{
    FileDownloads d=fresh();JSONObject row=row(d,"gecko-response");File file=partial(d,"download-cancel-pending.part");attach(d,row,file);
    Uri destination=Uri.parse("content://pending/controlled-target");String generation=row.optString("taskGeneration");
    ui(()->{d.completeFile=true;d.mark("paused","保存结果待确认");d.tasks.beginSave(row,destination,"provider","kept.bin",generation);d.cancel();return null;});idle(d);
    check("Cancel keeps pending publication identity and its complete recovery copy",file.isFile()&&d.temp!=null&&row.optBoolean("complete")&&DownloadTaskRevisions.pending(row,destination.toString(),generation)&&file.getName().equals(row.optString("partial")));
    check("Pending publication cancellation explains that the save is still unconfirmed",d.a.message.contains("待确认")&&!d.a.message.contains("已清理"));
  }
  static void persistence()throws Exception{
    for(String fault:new String[]{"before-memory","after-memory"}){
      FileDownloads d=fresh();JSONObject row=row(d,"gecko-response");File file=partial(d,"download-cancel-persistence.part");attach(d,row,file);
      ui(()->{d.completeFile=true;d.mark("paused","完整文件待保存");if(fault.equals("before-memory"))d.tasks.prefs.failNextCommit=true;else d.tasks.prefs.failAfterMemoryBeforeDisk=true;d.cancel();return null;});idle(d);
      JSONObject confirmed=DownloadTaskRevisions.find(new org.json.JSONArray(d.tasks.durability.confirmed),row.optString("id"));
      check("Failed cancel retirement "+fault+" retains complete bytes and authoritative save metadata",file.isFile()&&row.optBoolean("complete")&&confirmed.optBoolean("complete")&&file.getName().equals(confirmed.optString("partial"))&&!d.retiringPartial);
      check("Failed cancel retirement "+fault+" reports a failure instead of successful cleanup",!d.a.message.isEmpty()&&!d.a.message.contains("已清理"));
    }
  }
  static void leaseFailure()throws Exception{
    FileDownloads d=fresh();JSONObject row=row(d,"http-range");File file=partial(d,"download-cancel-lock.part");attach(d,row,file);File lock=SealedFileIo.lockFile(file);Files.createDirectory(lock.toPath());
    ui(()->{d.cancel();return null;});idle(d);
    check("Cancel honors private-file lease failure and leaves retryable retirement evidence",file.isFile()&&file.getName().equals(row.optString("retiredPartial"))&&row.optString("partial").isEmpty()&&!row.optString("reason").isEmpty()&&!d.retiringPartial);
    Files.delete(lock.toPath());ui(()->{if(!d.loadTask(row))throw new AssertionError("cancel retry claim");d.cancel();return null;});idle(d);
    check("Explicit cancellation retry finishes the same retired private copy",!file.exists()&&row.optString("retiredPartial").isEmpty()&&row.optString("partial").isEmpty());
  }
  static void ordinary()throws Exception{
    for(boolean complete:new boolean[]{false,true}){
      FileDownloads d=fresh();JSONObject row=row(d,"http-range");File file=partial(d,"download-cancel-selected.part"),other=partial(d,"download-cancel-unrelated.part");attach(d,row,file);
      ui(()->{d.completeFile=complete;d.resumeValidator="\"original\"";d.resumeAddress="https://example.test/file";d.mark("paused","");d.cancel();return null;});idle(d);
      check("Confirmed cancel retires only selected "+(complete?"complete":"incomplete")+" private bytes",!file.exists()&&other.isFile()&&"cancelled".equals(row.optString("state"))&&!row.optBoolean("complete")&&row.optString("partial").isEmpty()&&row.optString("retiredPartial").isEmpty()&&row.optString("validator").isEmpty()&&row.optString("resource").isEmpty()&&!d.active&&!d.retiringPartial);
    }
  }
  static void protectedRows()throws Exception{
    for(String protection:new String[]{"saved","unknown-complete","other-reference"}){
      FileDownloads d=fresh();JSONObject row=row(d,"gecko-response");File file=partial(d,"download-cancel-protected.part");attach(d,row,file);
      ui(()->{if(protection.equals("saved")){d.completeFile=true;DownloadTasks.put(row,"complete",true,"state","saved","uri","content://saved/committed");}else if(protection.equals("unknown-complete"))row.remove("complete");else d.tasks.rows.put(J.obj("id","other-reference","partial",file.getName()));d.tasks.save();d.cancel();return null;});idle(d);
      check("Cancel preserves protected "+protection+" metadata and file",file.isFile()&&file.getName().equals(row.optString("partial"))&&(protection.equals("saved")?"saved".equals(row.optString("state"))&&row.optBoolean("complete"):true));
    }
  }
  static void missingCopy()throws Exception{
    FileDownloads d=fresh();JSONObject row=row(d,"http-range");File file=partial(d,"download-cancel-evicted.part");attach(d,row,file);Files.delete(file.toPath());
    check("Evicted private file remains outside the original redownload retirement path",ui(()->d.tasks.retirementFile(row))==null);
    ui(()->{d.cancel();return null;});idle(d);
    check("Explicit cancel can retire an already evicted canonical private file","cancelled".equals(row.optString("state"))&&row.optString("partial").isEmpty()&&row.optString("retiredPartial").isEmpty()&&!file.exists()&&!d.retiringPartial);
    FileDownloads invalid=fresh();JSONObject protectedRow=row(invalid,"gecko-response");File outside=new File(invalid.a.root,"outside-user-file");Files.write(outside.toPath(),new byte[]{6});
    ui(()->{DownloadTasks.put(protectedRow,"partial","../outside-user-file");invalid.tasks.save();invalid.cancel();return null;});idle(invalid);
    check("Cancellation cannot reinterpret an invalid path as an absent private file",outside.isFile()&&"../outside-user-file".equals(protectedRow.optString("partial"))&&!"cancelled".equals(protectedRow.optString("state")));
  }
  static void changedGeneration()throws Exception{
    for(boolean cancellation:new boolean[]{true,false}){
      FileDownloads d=fresh();JSONObject row=row(d,"gecko-response");File file=partial(d,"download-cancel-generation.part");attach(d,row,file);String previous=row.optString("taskGeneration");
      CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1);CompletableFuture<Void> writer=CompletableFuture.runAsync(()->{try{SealedFileIo.lease(file,()->{held.countDown();if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("generation lease barrier");return null;});}catch(Exception error){throw new CompletionException(error);}});
      if(!held.await(5,TimeUnit.SECONDS))throw new AssertionError("generation writer lease");Thread worker=d.worker.submit(()->Thread.currentThread()).get(5,TimeUnit.SECONDS);ui(()->{if(cancellation)d.cancel();else d.discardForRedownload(row);return null;});
      long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);boolean waiting;
      do{waiting=false;for(StackTraceElement frame:worker.getStackTrace())if(frame.getClassName().equals("local.pocketchat.SealedFileIo")&&frame.getMethodName().equals("lease"))waiting=true;if(!waiting)Thread.yield();}while(!waiting&&System.nanoTime()<deadline);
      String label=cancellation?"Cancel":"Redownload";
      check(label+" waits for private writer before deleting a retired copy",waiting&&file.isFile()&&ui(()->d.retiringPartial)&&file.getName().equals(row.optString("retiredPartial")));
      // Direct storage handoff is intentional: the UI prevents a second picker
      // during retirement, but the storage generation remains the deletion fence.
      ui(()->{if(!d.tasks.claim(row))throw new AssertionError("same store newer generation");return null;});release.countDown();writer.get(5,TimeUnit.SECONDS);idle(d);
      check(label+" rechecks generation after lease and never releases a later claim",file.isFile()&&!previous.equals(row.optString("taskGeneration"))&&ui(()->d.tasks.owns(row))&&!d.retiringPartial&&file.getName().equals(row.optString("retiredPartial")));
    }
  }
  static void run()throws Exception{staleOwner();retiredBeforeQueue();pending();persistence();leaseFailure();ordinary();protectedRows();missingCopy();changedGeneration();}
}
