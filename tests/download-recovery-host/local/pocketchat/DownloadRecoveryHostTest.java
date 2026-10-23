package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.json.*;

/** Real production task/recovery/publication methods; explicit Android service doubles. */
public final class DownloadRecoveryHostTest {
  static final Handler MAIN=new Handler(Looper.getMainLooper());
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static <T>T main(Callable<T> call)throws Exception{FutureTask<T> task=new FutureTask<>(call);MAIN.post(task);return task.get(5,TimeUnit.SECONDS);}
  static void idle(DownloadTasks tasks)throws Exception{long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(tasks.recovering&&System.nanoTime()<until)Thread.sleep(2);if(tasks.recovering||tasks.recoveryFailure!=null)throw new AssertionError("Recovery did not finish",tasks.recoveryFailure);}
  static JSONObject stored(Context c,String id)throws Exception{return DownloadTaskRevisions.find(new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]")),id);}
  static JSONObject disk(Context c,String id)throws Exception{return DownloadTaskRevisions.find(new JSONArray(c.getSharedPreferences("download-tasks",0).diskString("rows","[]")),id);}
  static void commit(DownloadTasks tasks,JSONObject row,DefaultDownloads.Target target,String generation){tasks.finishSave(row,target.uri,generation,()->DownloadTasks.put(row,"state","saved","uri",target.uri.toString()));}
  static void race(File root,boolean cancel)throws Exception{
    Context context=new Context(root,cancel?1:0);DownloadTasks owner=main(()->new DownloadTasks(context));
    JSONObject row=main(()->{JSONObject r=owner.add("","","");DownloadTasks.put(r,"state","saving");owner.save();return r;});
    DefaultDownloads.Target target=DefaultDownloads.local(context,"payload.bin");byte[] payload={3,7,11,17};String generation=UUID.randomUUID().toString();
    CountDownLatch published=new CountDownLatch(1),release=new CountDownLatch(1);AtomicReference<Throwable> error=new AtomicReference<>();
    Thread writer=new Thread(()->{try{SavedFilePublication.run(context,target.uri,MAIN,()->owner.beginSave(row,target.uri,target.location,target.name,generation),()->{
      try(OutputStream out=target.output()){out.write(payload);}target.publish();published.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Writer release missing");return null;
    },()->{if(cancel)throw new IllegalStateException("Fixture cancellation after publish");commit(owner,row,target,generation);},target::abort);}catch(Throwable failure){error.set(failure);}},"host-publication");
    writer.start();if(!published.await(5,TimeUnit.SECONDS))throw new AssertionError("Writer did not publish");
    DownloadTasks reopened;
    try{
      reopened=main(()->new DownloadTasks(context));
      check((cancel?"Cancelled":"Successful")+" writer permits a new main-thread constructor while retaining its URI lease",writer.isAlive()&&reopened.recovering);
      check((cancel?"Cancelled":"Successful")+" writer permits another main-thread message before lease release",main(()->true));
    }finally{release.countDown();}
    writer.join(5000);if(writer.isAlive())throw new AssertionError("Writer did not finish");idle(reopened);
    JSONObject finalRow=stored(context,row.optString("id"));
    if(cancel){
      check("Cancelled publication removes its bytes before the waiting recovery inspects them",error.get()!=null&&!target.file.exists());
      check("Waiting recovery never records an aborted destination as saved",finalRow!=null&&!"saved".equals(finalRow.optString("state"))&&!finalRow.has("pendingDestination")&&!DownloadLibrary.get(context).indexed(target.uri));
    }else{
      check("Successful publication retains its exact bytes after new-instance recovery",error.get()==null&&Arrays.equals(payload,Files.readAllBytes(target.file.toPath())));
      check("Recovery follows the old publisher's committed task and saved index",finalRow!=null&&"saved".equals(finalRow.optString("state"))&&target.uri.toString().equals(finalRow.optString("uri"))&&DownloadLibrary.get(context).indexed(target.uri));
      // The earlier instance still holds an obsolete row. Neither its stale save
      // nor a pending cleanup can restore the destination after actual deletion.
      JSONObject selected=J.parse(finalRow.toString());SavedFileDeletion.remove(context,selected);
      main(()->{DownloadTasks.put(row,"reason","late old callback");owner.save();owner.clearPending(row,target.uri,generation);return null;});
      check("Late old-instance updates cannot restore a deleted task or saved file",stored(context,row.optString("id"))==null&&!target.file.exists()&&!DownloadLibrary.get(context).indexed(target.uri));
    }
  }
  static void orphan(File root,boolean complete)throws Exception{
    Context c=new Context(root,complete?2:3);DefaultDownloads.Target target=DefaultDownloads.local(c,"orphan.bin");
    try(OutputStream out=target.output()){out.write(new byte[]{2,4,6});}if(complete)target.publish();
    JSONObject orphan=J.obj("id",UUID.randomUUID().toString(),"state","saving","time",1,"pendingDestination",target.uri.toString(),"pendingLocation",target.location,"pendingGeneration","dead-publisher");
    c.getSharedPreferences("download-tasks",0).edit().putString("rows",new JSONArray().put(orphan).toString()).commit();
    DownloadTasks restored=main(()->new DownloadTasks(c));idle(restored);JSONObject row=stored(c,orphan.optString("id"));
    if(complete)check("A published orphan is recovered only after its real destination exists",target.file.isFile()&&"saved".equals(row.optString("state"))&&DownloadLibrary.get(c).indexed(target.uri));
    else check("An abandoned incomplete destination is cleaned without inventing a saved record",!target.part.exists()&&!target.file.exists()&&!"saved".equals(row.optString("state"))&&!row.has("pendingDestination"));
  }
  static void generations(File root)throws Exception{
    Context c=new Context(root,4);DownloadTasks tasks=main(()->new DownloadTasks(c));JSONObject row=main(()->tasks.add("","",""));
    Uri first=Uri.parse("content://fixture/first"),second=Uri.parse("content://fixture/second");
    main(()->{tasks.beginSave(row,first,"one","one","generation-one");tasks.beginSave(row,second,"two","two","generation-two");tasks.clearPending(row,first,"generation-one");return null;});
    check("A late failed-save callback cannot clear a newer destination and generation",DownloadTaskRevisions.pending(stored(c,row.optString("id")),second.toString(),"generation-two"));
    boolean rejected=main(()->{try{tasks.requirePending(row,first,"generation-one");return false;}catch(IllegalStateException expected){return true;}});
    check("An older save generation cannot commit after task replacement",rejected);
    JSONObject original=J.obj("id","same","state","saving","pendingGeneration","old"),later=J.obj("id","same","state","saved","uri","content://fixture/new");
    Map<String,String> seen=DownloadTaskRevisions.snapshot(new JSONArray().put(original));DownloadTasks.put(original,"reason","late failure");
    JSONArray merged=DownloadTaskRevisions.merge(new JSONArray().put(original),seen,new JSONArray().put(later));
    check("Conflicting stale task edits preserve the newer durable row",merged.optJSONObject(0).toString().equals(later.toString()));
    JSONObject unrelated=J.obj("id","new","state","paused");JSONArray retained=DownloadTaskRevisions.merge(new JSONArray().put(later),DownloadTaskRevisions.snapshot(new JSONArray().put(later)),new JSONArray().put(later).put(unrelated));
    check("Saving one instance preserves tasks added by another instance",DownloadTaskRevisions.find(retained,"new")!=null);
    boolean mainRejected=main(()->{try{DefaultDownloads.recover(c,J.obj("pendingDestination",first.toString()));return false;}catch(IllegalStateException expected){return true;}});
    check("The direct recovery API rejects main-thread file-lock acquisition",mainRejected);
    boolean publicationRejected=main(()->{try{SavedFilePublication.run(c,first,MAIN,()->{},()->null,()->{},()->{});return false;}catch(IllegalStateException expected){return true;}});
    check("Publication rejects main-thread lease acquisition instead of waiting for itself",publicationRejected);
  }
  static void liveTask(File root)throws Exception{
    Context c=new Context(root,5);DownloadTasks live=main(()->new DownloadTasks(c));JSONObject row=main(()->{JSONObject r=live.add("","","");DownloadTasks.put(r,"state","downloading","received",23);live.save();return r;});
    DownloadTasks reopened=main(()->new DownloadTasks(c));idle(reopened);
    check("A live older download without a pending destination is not marked interrupted",main(()->live.owns(row))&&"downloading".equals(stored(c,row.optString("id")).optString("state")));
    boolean refused=main(()->!reopened.claim(DownloadTaskRevisions.find(reopened.rows,row.optString("id"))));
    check("A second instance cannot take over a still-live owner by selecting its task",refused&&main(()->live.owns(row)));
    main(()->{DownloadTasks.put(row,"received",47);live.save();return null;});
    check("An unchanged local merge retains the running task object and later real progress",main(()->live.owns(row)&&DownloadTaskRevisions.find(live.rows,row.optString("id"))==row)&&stored(c,row.optString("id")).optLong("received")==47);
    main(()->{live.release();return null;});DownloadTasks interrupted=main(()->new DownloadTasks(c));idle(interrupted);
    check("After its owner ends an interrupted task is recovered without retaining a live writer",!"downloading".equals(stored(c,row.optString("id")).optString("state")));
  }
  static void commitFailure(File root,boolean beforeCommit)throws Exception{
    Context c=new Context(root,beforeCommit?6:7);DownloadTasks tasks=main(()->new DownloadTasks(c));JSONObject row=main(()->tasks.add("","",""));
    DefaultDownloads.Target target=DefaultDownloads.local(c,"commit-failure.bin");String generation=UUID.randomUUID().toString();AtomicBoolean aborted=new AtomicBoolean();Throwable error=null;
    try{SavedFilePublication.run(c,target.uri,MAIN,()->tasks.beginSave(row,target.uri,target.location,target.name,generation),()->{
      try(OutputStream out=target.output()){out.write(new byte[]{9,8,7});}target.publish();
      if(beforeCommit)c.getSharedPreferences("download-tasks",0).failNextCommit=true;else DownloadLibrary.get(c).failNextSync=true;
      return null;
    },()->commit(tasks,row,target,generation),()->{aborted.set(true);target.abort();});}catch(Throwable failure){error=failure;}
    JSONObject durable=stored(c,row.optString("id"));
    if(beforeCommit){
      check("A rejected task commit preserves published bytes and restores the previous pending row",error!=null&&!aborted.get()&&target.file.exists()&&!"saved".equals(row.optString("state"))&&!"saved".equals(durable.optString("state"))&&durable.has("pendingDestination"));
      DownloadTasks restarted=main(()->new DownloadTasks(c));idle(restarted);
      check("Recovery retries rejected metadata before confirming the retained published bytes",target.file.exists()&&DownloadLibrary.get(c).indexed(target.uri)&&"saved".equals(disk(c,row.optString("id")).optString("state")));
    }else{
      check("Index failure after durable saved metadata cannot abort or downgrade publication",error==null&&!aborted.get()&&target.file.isFile()&&"saved".equals(durable.optString("state"))&&tasks.indexFailure!=null&&!DownloadLibrary.get(c).indexed(target.uri));
      DownloadTasks restarted=main(()->new DownloadTasks(c));long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(!DownloadLibrary.get(c).indexed(target.uri)&&System.nanoTime()<deadline)Thread.sleep(2);
      check("A new instance repairs the saved index even when every task has no pending destination",DownloadLibrary.get(c).indexed(target.uri)&&target.file.isFile()&&"saved".equals(stored(c,row.optString("id")).optString("state"))&&restarted.recoveryFailure==null);
    }
  }
  static JSONObject memoryFailure(File root,int slot)throws Exception{
    Context c=new Context(root,slot);SharedPreferences prefs=c.getSharedPreferences("download-tasks",0);
    DownloadTasks tasks=main(()->new DownloadTasks(c));File source=new File(c.getCacheDir(),"download-memory-failure.part");Files.write(source.toPath(),new byte[]{6,7,8,9});
    JSONObject row=main(()->{JSONObject r=tasks.add("","","");DownloadTasks.put(r,"state","saving","partial",source.getName());tasks.save();return r;});
    DefaultDownloads.Target target=DefaultDownloads.local(c,"memory-failure.bin");String generation=UUID.randomUUID().toString();AtomicBoolean aborted=new AtomicBoolean();AtomicInteger notified=new AtomicInteger();Throwable error=null;
    try{SavedFilePublication.run(c,target.uri,MAIN,()->tasks.beginSave(row,target.uri,target.location,target.name,generation),()->{
      try(OutputStream out=target.output()){out.write(Files.readAllBytes(source.toPath()));}target.publish();prefs.failAfterMemoryBeforeDisk=true;return null;
    },()->commit(tasks,row,target,generation),()->{aborted.set(true);target.abort();});}catch(Throwable failure){error=failure;}
    JSONObject memory=stored(c,row.optString("id")),durable=disk(c,row.optString("id"));
    check("After-memory commit failure keeps cached saved separate from disk pending slot "+slot,error!=null&&SavedFilePublication.unconfirmed(error)&&"saved".equals(memory.optString("state"))&&!"saved".equals(durable.optString("state"))&&durable.has("pendingDestination"));
    check("Failed memory receipt cannot delete source or notify completion slot "+slot,!SavedFilePublication.complete(tasks,memory,source,notified::incrementAndGet)&&source.isFile()&&notified.get()==0);
    check("After-memory failure preserves destination and pending generation slot "+slot,!aborted.get()&&target.file.isFile()&&DownloadTaskRevisions.pending(row,target.uri.toString(),generation)&&!tasks.published(memory,target.uri));
    return J.obj("id",row.optString("id"),"uri",target.uri.toString(),"source",source.getAbsolutePath(),"slot",slot);
  }
  static void memoryRetry(File root)throws Exception{
    JSONObject control=memoryFailure(root,8);Context c=new Context(root,8);SharedPreferences prefs=c.getSharedPreferences("download-tasks",0);int attempts=prefs.commitAttempts;
    DownloadTasks reopened=main(()->new DownloadTasks(c));idle(reopened);JSONObject row=main(()->DownloadTaskRevisions.find(reopened.rows,control.optString("id")));File source=new File(control.optString("source"));AtomicInteger notices=new AtomicInteger();
    check("A new instance ignores failed cached saved and explicitly commits recovery",prefs.commitAttempts>attempts&&!reopened.durability.unconfirmed&&"saved".equals(disk(c,row.optString("id")).optString("state"))&&reopened.published(row,Uri.parse(control.optString("uri"))));
    check("Only a confirmed recovery receipt permits source cleanup and completion",SavedFilePublication.complete(reopened,row,source,notices::incrementAndGet)&&!source.exists()&&notices.get()==1);
    // Equal serialized values still need a successful write after commit(false).
    main(()->{prefs.failAfterMemoryBeforeDisk=true;try{reopened.save(true);throw new AssertionError("commit should fail");}catch(DownloadTasks.PersistenceFailure expected){}return null;});int failedAttempt=prefs.commitAttempts;
    DownloadTasks another=main(()->new DownloadTasks(c));long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(another.durability.unconfirmed&&System.nanoTime()<deadline)Thread.sleep(2);
    check("Equal cached rows never bypass a new instance's unconfirmed write retry",prefs.commitAttempts>failedAttempt&&!another.durability.unconfirmed&&another.recoveryFailure==null);
  }
  static void emptyRetry(File root)throws Exception{
    Context c=new Context(root,10);SharedPreferences prefs=c.getSharedPreferences("download-tasks",0);DownloadTasks tasks=main(()->new DownloadTasks(c));
    main(()->{prefs.failAfterMemoryBeforeDisk=true;try{tasks.save(true);throw new AssertionError("Expected failed commit");}catch(DownloadTasks.PersistenceFailure expected){}return null;});int attempts=prefs.commitAttempts;
    DownloadTasks next=main(()->new DownloadTasks(c));long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(next.durability.unconfirmed&&System.nanoTime()<deadline)Thread.sleep(2);
    check("A new empty instance also retries equal rows after failed persistence",prefs.commitAttempts>attempts&&!next.durability.unconfirmed);
  }
  static void missingRetry(File root)throws Exception{
    Context c=new Context(root,11);DownloadTasks tasks=main(()->new DownloadTasks(c));JSONObject original=main(()->tasks.add("","",""));DefaultDownloads.Target missing=DefaultDownloads.local(c,"missing.bin");
    main(()->{tasks.beginSave(original,missing.uri,missing.location,missing.name,"gone");tasks.release();return null;});
    AtomicReference<JSONObject> rebound=new AtomicReference<>();CountDownLatch done=new CountDownLatch(1);
    main(()->{tasks.recoverPending(original,()->{rebound.set(tasks.recoveredRow(original));done.countDown();});return null;});if(!done.await(5,TimeUnit.SECONDS))throw new AssertionError("Missing destination recovery timeout");JSONObject next=rebound.get();
    check("Pending recovery returns the replacement row when destination is missing",next!=null&&next!=original&&!next.has("pendingDestination")&&!"saved".equals(next.optString("state"))&&tasks.recoveryFailure==null);
    DefaultDownloads.Target retry=DefaultDownloads.local(c,"retry.bin");
    check("Recovered failed row can be claimed and saved in a new generation",main(()->{if(!tasks.claim(next))throw new AssertionError("claim failed row="+next+" rows="+tasks.rows+" observed="+tasks.observed+" confirmed="+tasks.durability.confirmed);tasks.beginSave(next,retry.uri,retry.location,retry.name,"retry-generation");return DownloadTaskRevisions.pending(next,retry.uri.toString(),"retry-generation");}));
  }
  static void keyOrder(){
    JSONObject row=J.obj("id","same-order","nested",J.obj("x",1,"y",2),"state","paused"),reordered=J.obj("state","paused","nested",J.obj("y",2,"x",1),"id","same-order");
    JSONArray merged=DownloadTaskRevisions.merge(new JSONArray().put(row),DownloadTaskRevisions.snapshot(new JSONArray().put(row)),new JSONArray().put(reordered));
    check("Equivalent reordered JSON retains the running task object",merged.optJSONObject(0)==row);
  }
  static void child(File root,String mode)throws Exception{
    File controlFile=new File(root,"restart-control.json");
    if("restart-writer".equals(mode)){
      JSONObject control=memoryFailure(root,9);Files.writeString(controlFile.toPath(),control.toString());
      check("Writer exits with disk pending plus preserved source and published destination",new File(control.optString("source")).isFile());
    }else{
      JSONObject control=J.parse(Files.readString(controlFile.toPath()));Context c=new Context(root,9);SharedPreferences prefs=c.getSharedPreferences("download-tasks",0);
      check("Fresh JVM loads disk pending without the dead process cached saved",!"saved".equals(stored(c,control.optString("id")).optString("state"))&&stored(c,control.optString("id")).has("pendingDestination"));
      File source=new File(control.optString("source"));DownloadTasks restored=main(()->new DownloadTasks(c));idle(restored);JSONObject row=main(()->DownloadTaskRevisions.find(restored.rows,control.optString("id")));Uri uri=Uri.parse(control.optString("uri"));AtomicInteger notices=new AtomicInteger();
      check("Fresh JVM recovers the real published destination with a successful disk commit",prefs.commitAttempts>0&&"saved".equals(disk(c,row.optString("id")).optString("state"))&&restored.published(row,uri)&&SavedDownloadProvider.resolve(c,uri).isFile()&&source.isFile());
      check("Fresh JVM cleanup occurs only after confirmed saved persistence",SavedFilePublication.complete(restored,row,source,notices::incrementAndGet)&&!source.exists()&&notices.get()==1);
    }
  }
  static void processRestart(File root)throws Exception{
    for(String mode:new String[]{"restart-writer","restart-reader"}){
      Process process=new ProcessBuilder(System.getProperty("java.home")+"/bin/java","-cp",System.getProperty("java.class.path"),DownloadRecoveryHostTest.class.getName(),mode,root.getAbsolutePath()).start();
      if(!process.waitFor(10,TimeUnit.SECONDS)){process.destroyForcibly();throw new AssertionError("Restart child timeout: "+mode);}
      String stdout=new String(process.getInputStream().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8),stderr=new String(process.getErrorStream().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
      JSONObject result=J.parse(stdout);if(process.exitValue()!=0||!"passed".equals(result.optString("status")))throw new AssertionError(mode+" failed: "+stdout+stderr);
      JSONArray childChecks=result.getJSONArray("checks");for(int i=0;i<childChecks.length();i++){JSONObject row=childChecks.getJSONObject(i);check(mode+": "+row.getString("name"),row.getBoolean("pass"));}
    }
  }
  public static void main(String[] args)throws Exception{
    File root=args.length==2?new File(args[1]):Files.createTempDirectory("download-recovery-host-").toFile();Throwable failure=null;
    try{if(args.length==2)child(root,args[0]);else{race(root,false);race(root,true);orphan(root,false);orphan(root,true);generations(root);liveTask(root);commitFailure(root,true);commitFailure(root,false);memoryRetry(root);emptyRetry(root);missingRetry(root);keyOrder();processRestart(root);}}catch(Throwable error){failure=error;}
    JSONObject result=J.obj("status",failure==null?"passed":"failed","checks",checks,"total",args.length==2?checks.length():42,"executed",checks.length(),"actualAndroidExecution",false,"actualMediaStoreExecution",false,"actualSQLiteExecution",false,"actualProductionFileLease",true,"actualProductionTaskRecovery",true,"actualProductionPublicationCoordinator",true,"actualHostJvmRestart",args.length==0,"scope","Production Java download task/recovery/publication/deletion methods and real host files/locks. Android main queue, preferences with independent memory/disk, local URI provider and index are explicit doubles. Includes failures before memory, after memory before disk, post-commit index failure, completion/source-cleanup gate and two separate JVM processes loading persisted fixture disk. No Android durability, physical-device or latency evidence.");
    if(failure!=null)result.put("error",failure.toString());System.out.println(result.toString(2));if(failure!=null)System.exit(1);
  }
}
