package local.pocketchat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.MediaStore;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;
import org.json.JSONArray;
import org.json.JSONObject;

/** Deletes only freshly created synthetic destinations through the real Android APIs. */
final class DownloadDeletionIntegration {
  final Activity activity;
  final JSONArray checks=new JSONArray();
  final JSONObject report=J.obj("schema",1,"status","running","actualAndroidExecution",true,
      "actualAdbTouchExecution",false,"scope","Synthetic saved downloads only; no existing phone files selected.");
  final List<DefaultDownloads.Target> targets=new ArrayList<>();
  final Set<String> ownIds=new HashSet<>(),ownUris=new HashSet<>();
  Context main,seven;
  DownloadLibrary library;

  DownloadDeletionIntegration(Activity activity){this.activity=activity;}

  static void run(Activity activity,Consumer<JSONObject> done){
    new Thread(()->{
      DownloadDeletionIntegration test=new DownloadDeletionIntegration(activity);
      try{test.exercise();test.report.put("status","passed");}
      catch(Throwable error){try{test.report.put("status","failed").put("error",error.toString());}catch(Exception ignored){}}
      finally{try{test.cleanup();}catch(Throwable error){try{test.report.put("status","failed").put("cleanupError",error.toString());}catch(Exception ignored){}}}
      try{test.report.put("checks",test.checks).put("checkCount",test.checks.length());}catch(Exception ignored){}
      activity.runOnUiThread(()->done.accept(test.report));
    },"download-deletion-fixture").start();
  }

  void check(String name,boolean passed)throws Exception{
    checks.put(J.obj("name",name,"pass",passed));
    if(!passed)throw new IllegalStateException(name);
  }

  void exercise()throws Exception{
    main=Profiles.context(activity,0);seven=Profiles.context(activity,7);library=DownloadLibrary.get(activity);
    check("Saved-file deletion runs outside the Android main thread",Looper.myLooper()!=Looper.getMainLooper());
    check("The controlled device supports real MediaStore Downloads",Build.VERSION.SDK_INT>=29);
    String filename="deletion-fixture-"+UUID.randomUUID()+".apk";
    byte[] publicBytes=bytes(5127,11),remainingBytes=bytes(6193,29),privateBytes=bytes(8197,43),replacementBytes=bytes(7341,61);
    DefaultDownloads.Target publicTarget=create(main,filename,publicBytes,false);
    DefaultDownloads.Target remainingTarget=create(main,filename,remainingBytes,false);
    DefaultDownloads.Target privateTarget=create(seven,filename,privateBytes,true);
    DefaultDownloads.Target privateRemaining=create(seven,filename,remainingBytes,true);
    JSONObject publicRow=row(main,publicTarget),remainingRow=row(main,remainingTarget),privateRow=row(seven,privateTarget),privateRemainingRow=row(seven,privateRemaining);
    DownloadTasks stale=new DownloadTasks(seven);
    stale.rows.put(privateRow).put(privateRemainingRow);
    JSONObject otherTask=J.obj("id",UUID.randomUUID().toString(),"slot",7,"state","paused","name","independent-fixture-task","time",System.currentTimeMillis(),"received",1,"total",10);
    ownIds.add(otherTask.optString("id"));stale.rows.put(otherTask);stale.save();
    appendHistory(seven,privateRow,privateRemainingRow);
    library.add(main,publicRow);library.add(main,remainingRow);
    check("Published MediaStore and profile-7 private APK bytes are readable",
        "media".equals(publicTarget.uri.getAuthority())&&Profiles.slot(seven)==7&&Arrays.equals(read(publicTarget.uri),publicBytes)&&Arrays.equals(read(privateTarget.uri),privateBytes));

    long publicFreed=SavedFileDeletion.remove(activity,publicRow);
    check("Deleting the selected MediaStore APK reports its actual size and removes its row",publicFreed==publicBytes.length&&mediaMissing(publicTarget.uri)&&!indexed(publicTarget.uri));
    check("A same-name private APK in another profile survives MediaStore deletion",publicTarget.name.equals(privateTarget.name)&&library.saved(privateRow)!=null&&Arrays.equals(read(privateTarget.uri),privateBytes));
    long privateFreed=SavedFileDeletion.remove(activity,privateRow);
    check("Deleting a profile-7 private APK removes its physical payload and both shared indexes",privateFreed==privateBytes.length&&!privateTarget.file.isFile()&&!indexed(privateTarget.uri)&&!taskIndexed(privateTarget.uri));
    check("Same-name destinations in another profile and directory retain their exact bytes",Arrays.equals(read(remainingTarget.uri),remainingBytes)&&Arrays.equals(read(privateRemaining.uri),remainingBytes));

    DownloadTasks.put(otherTask,"received",4);stale.save();
    library.add(seven,J.parse(privateRow.toString()));library.sync(seven,new JSONArray().put(J.parse(privateRow.toString())));
    check("An unrelated progress save and late add/sync cannot resurrect a deleted saved file",!contains(stale.rows,privateTarget.uri)&&!indexed(privateTarget.uri)&&!taskIndexed(privateTarget.uri)&&containsId(stale.rows,otherTask.optString("id")));
    DownloadTasks reopened=new DownloadTasks(seven);
    check("Reopening profile tasks and migrating legacy history keep the deletion durable",!contains(reopened.rows,privateTarget.uri)&&!indexed(privateTarget.uri)&&!taskIndexed(privateTarget.uri)&&!contains(history(seven),privateTarget.uri));

    // Reuse only this synthetic URI to model a later SAF save to the same destination.
    privateTarget.file.getParentFile().mkdirs();write(privateTarget,replacementBytes);
    JSONObject replacement=row(seven,privateTarget);
    long deadline=SystemClock.elapsedRealtime()+2000;
    while(library.isRemoved(replacement)&&SystemClock.elapsedRealtime()<deadline){Thread.sleep(2);replacement.put("time",System.currentTimeMillis());}
    library.add(seven,replacement);library.sync(seven,new JSONArray().put(replacement));
    check("A later download with a fresh id and timestamp may reuse the exact destination URI",!library.isRemoved(replacement)&&library.saved(replacement)!=null&&Arrays.equals(read(privateTarget.uri),replacementBytes));
    long staleFreed=SavedFileDeletion.remove(activity,privateRow);
    check("An old captured menu cannot delete a newer download at the same URI",staleFreed==0&&library.saved(replacement)!=null&&Arrays.equals(read(privateTarget.uri),replacementBytes));
    sameUriWriterBarrier(privateTarget,replacement,bytes(9359,107));

    DefaultDownloads.Target absentPrivate=create(seven,filename,bytes(2111,79),true);JSONObject absentPrivateRow=row(seven,absentPrivate);library.add(seven,absentPrivateRow);
    if(!absentPrivate.file.delete())throw new IllegalStateException("Synthetic external private-file removal failed");
    long absentPrivateFreed=SavedFileDeletion.remove(activity,absentPrivateRow);
    check("An already absent private payload clears stale metadata without claiming freed bytes",absentPrivateFreed==0&&library.isRemoved(absentPrivateRow)&&!indexed(absentPrivate.uri));
    DefaultDownloads.Target absentMedia=create(main,filename,bytes(3221,97),false);JSONObject absentMediaRow=row(main,absentMedia);library.add(main,absentMediaRow);
    if(main.getContentResolver().delete(absentMedia.uri,null,null)!=1)throw new IllegalStateException("Synthetic external MediaStore removal failed");
    long absentMediaFreed=SavedFileDeletion.remove(activity,absentMediaRow);
    check("A known empty MediaStore query clears stale metadata without claiming freed bytes",absentMediaFreed==0&&library.isRemoved(absentMediaRow)&&!indexed(absentMedia.uri));

    Uri failureUri=Uri.parse("content://synthetic.pocket.upload/deletion-fixture/"+UUID.randomUUID());
    JSONObject failureRow=J.obj("id",UUID.randomUUID().toString(),"slot",0,"name","synthetic-unremovable-document","mime","text/plain","uri",failureUri.toString(),"state","saved","time",System.currentTimeMillis());
    ownIds.add(failureRow.optString("id"));ownUris.add(failureUri.toString());library.add(main,failureRow);
    byte[] failureBefore=read(failureUri);boolean failed=false;
    try{SavedFileDeletion.remove(activity,failureRow);}catch(java.io.IOException expected){failed=true;}
    check("Provider deletion failure retains its exact file bytes and indexed metadata",failed&&!library.isRemoved(failureRow)&&library.saved(failureRow)!=null&&Arrays.equals(failureBefore,read(failureUri)));

    JSONObject wrongIdentity=J.parse(privateRemainingRow.toString());wrongIdentity.put("id",UUID.randomUUID().toString());boolean rejected=false;
    try{SavedFileDeletion.remove(activity,wrongIdentity);}catch(java.io.IOException expected){rejected=true;}
    check("A stale or unindexed identity cannot delete another saved payload",rejected&&library.saved(privateRemainingRow)!=null&&Arrays.equals(read(privateRemaining.uri),remainingBytes));
    cancelConfirmation(privateRemainingRow);
    check("Cancelling the rendered confirmation preserves the file and its metadata",library.saved(privateRemainingRow)!=null&&!library.isRemoved(privateRemainingRow)&&Arrays.equals(read(privateRemaining.uri),remainingBytes));
    check("Unrelated same-name saved files remain readable after every deletion and failure case",library.saved(remainingRow)!=null&&Arrays.equals(read(remainingTarget.uri),remainingBytes)&&Arrays.equals(read(privateRemaining.uri),remainingBytes));
    report.put("actualMediaStoreExecution",true).put("actualPrivateProviderExecution",true).put("actualWorkerThreadDeletion",true)
        .put("profileSlot",7).put("freedMediaStoreBytes",publicFreed).put("freedPrivateBytes",privateFreed)
        .put("alreadyAbsentPrivateFreedBytes",absentPrivateFreed).put("alreadyAbsentMediaStoreFreedBytes",absentMediaFreed)
        .put("staleMenuFreedBytes",staleFreed).put("cancelConfirmation","Android negative Button.performClick; no ADB gesture");
  }

  DefaultDownloads.Target create(Context context,String filename,byte[] data,boolean privateFile)throws Exception{
    DefaultDownloads.Target target=privateFile?DefaultDownloads.local(context,filename):DefaultDownloads.create(context,filename,"application/vnd.android.package-archive");
    targets.add(target);ownUris.add(target.uri.toString());write(target,data);return target;
  }
  static void write(DefaultDownloads.Target target,byte[] data)throws Exception{try(OutputStream out=target.output()){out.write(data);out.flush();}target.publish();}
  JSONObject row(Context context,DefaultDownloads.Target target){JSONObject row=J.obj("id",UUID.randomUUID().toString(),"slot",Profiles.slot(context),"name",target.name,"mime","application/vnd.android.package-archive","uri",target.uri.toString(),"state","saved","location",target.location,"time",System.currentTimeMillis());ownIds.add(row.optString("id"));return row;}
  static byte[] bytes(int size,int seed){byte[] data=new byte[size];for(int i=0;i<size;i++)data[i]=(byte)(i*31+seed);return data;}
  byte[] read(Uri uri)throws Exception{try(InputStream in=activity.getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){if(in==null)throw new IllegalStateException("Missing synthetic input stream");byte[] buffer=new byte[1024];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);return out.toByteArray();}}
  boolean mediaMissing(Uri uri){try(Cursor cursor=activity.getContentResolver().query(uri,new String[]{MediaStore.MediaColumns._ID},null,null,null)){return cursor!=null&&!cursor.moveToFirst();}}
  boolean indexed(Uri uri){return contains(library.list(),uri);}
  boolean taskIndexed(Uri uri){return contains(library.tasks(),uri);}
  static boolean contains(JSONArray rows,Uri uri){for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&uri.toString().equals(row.optString("uri")))return true;}return false;}
  static boolean containsId(JSONArray rows,String id){for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&id.equals(row.optString("id")))return true;}return false;}
  static JSONArray history(Context context){JSONArray rows=J.parse(context.getSharedPreferences("chat",0).getString("downloadHistory","{}")).optJSONArray("files");return rows==null?new JSONArray():rows;}
  static void appendHistory(Context context,JSONObject... added)throws Exception{SharedPreferences prefs=context.getSharedPreferences("chat",0);JSONObject value=J.parse(prefs.getString("downloadHistory","{}"));JSONArray rows=value.optJSONArray("files");if(rows==null)rows=new JSONArray();for(JSONObject row:added)rows.put(J.parse(row.toString()));value.put("files",rows);if(!prefs.edit().putString("downloadHistory",value.toString()).commit())throw new IllegalStateException("Synthetic history publication failed");}

  void cancelConfirmation(JSONObject row)throws Exception{
    CountDownLatch done=new CountDownLatch(1);AtomicReference<Throwable> failure=new AtomicReference<>();
    activity.runOnUiThread(()->{SavedFileActions actions=new SavedFileActions(activity);try{AlertDialog dialog=actions.confirmDelete(row);if(dialog==null||!dialog.isShowing()||dialog.getButton(AlertDialog.BUTTON_NEGATIVE)==null)throw new IllegalStateException("Delete confirmation was not rendered");dialog.getButton(AlertDialog.BUTTON_NEGATIVE).performClick();new android.os.Handler(Looper.getMainLooper()).post(()->{try{if(dialog.isShowing())throw new IllegalStateException("Negative confirmation did not close");}catch(Throwable error){failure.set(error);}finally{actions.close();done.countDown();}});}catch(Throwable error){failure.set(error);actions.close();done.countDown();}});
    if(!done.await(5,TimeUnit.SECONDS))throw new IllegalStateException("Delete confirmation UI did not finish");
    if(failure.get()!=null)throw new IllegalStateException("Delete confirmation UI failed",failure.get());
  }

  void sameUriWriterBarrier(DefaultDownloads.Target target,JSONObject oldSelection,byte[] newBytes)throws Exception{
    JSONObject fresh=row(main,target);
    CountDownLatch published=new CountDownLatch(1),release=new CountDownLatch(1),writerDone=new CountDownLatch(1),deleteEntered=new CountDownLatch(1),deleteDone=new CountDownLatch(1);
    AtomicReference<Throwable> writerError=new AtomicReference<>(),deleteError=new AtomicReference<>();AtomicLong freed=new AtomicLong(-1);
    Thread writer=new Thread(()->{try{SavedFileDeletion.lease(activity,target.uri,()->{write(target,newBytes);fresh.put("time",library.publicationTime(target.uri));library.add(main,fresh);library.sync(main,new JSONArray().put(fresh));published.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IllegalStateException("Synthetic writer release was not delivered");return null;});}catch(Throwable error){writerError.set(error);}finally{published.countDown();writerDone.countDown();}},"deletion-fixture-writer");
    Thread deleter=new Thread(()->{deleteEntered.countDown();try{freed.set(SavedFileDeletion.remove(activity,oldSelection));}catch(Throwable error){deleteError.set(error);}finally{deleteDone.countDown();}},"deletion-fixture-waiter");
    writer.start();boolean deleteStarted=false;
    try{
      if(!published.await(5,TimeUnit.SECONDS)||writerError.get()!=null||writerDone.getCount()==0)throw new IllegalStateException("Synthetic writer did not retain its published URI lease",writerError.get());
      deleter.start();deleteStarted=true;if(!deleteEntered.await(5,TimeUnit.SECONDS))throw new IllegalStateException("Delete waiter did not begin");
      long deadline=SystemClock.elapsedRealtime()+2000;boolean enteredLease=false;
      while(deleteDone.getCount()!=0&&SystemClock.elapsedRealtime()<deadline){for(StackTraceElement frame:deleter.getStackTrace())if(frame.getClassName().startsWith(SealedFileIo.class.getName()))enteredLease=true;if(enteredLease)break;Thread.sleep(2);}
      check("A same-URI delete actually waits inside the active publication lease",enteredLease&&!deleteDone.await(100,TimeUnit.MILLISECONDS));
    }finally{
      release.countDown();if(!writerDone.await(5,TimeUnit.SECONDS))throw new IllegalStateException("Synthetic writer did not release its URI lease");if(deleteStarted&&!deleteDone.await(5,TimeUnit.SECONDS))throw new IllegalStateException("Delete waiter did not drain");
    }
    check("After the writer publishes a new identity the old deletion preserves its bytes and index",writerError.get()==null&&(deleteError.get() instanceof java.io.IOException||deleteError.get()==null&&freed.get()==0)&&library.saved(fresh)!=null&&Arrays.equals(read(target.uri),newBytes));
    library.add(seven,J.parse(oldSelection.toString()));library.sync(seven,new JSONArray().put(J.parse(oldSelection.toString())));
    check("Late old-slot add/sync cannot replace a newer saved identity from another profile",fresh.optInt("slot")==0&&oldSelection.optInt("slot")==7&&library.saved(fresh)!=null&&library.saved(oldSelection)==null&&!containsId(library.tasks(),oldSelection.optString("id"))&&Arrays.equals(read(target.uri),newBytes));
    report.put("actualSameUriPublicationBarrier",true).put("staleDeleteWaitedForWriter",true).put("newPublishedBytesPreserved",true).put("writerProfileSlot",0).put("oldSelectionProfileSlot",7).put("lateOldSlotSuppressed",true);
  }

  void cleanup()throws Exception{
    for(DefaultDownloads.Target target:targets)target.abort();
    if(library==null)return;
    // Remove only this fixture's identifiers; unsupported provider bytes were never owned by us.
    for(String uri:ownUris)library.getWritableDatabase().delete("files","uri=?",new String[]{uri});
    for(String id:ownIds)library.getWritableDatabase().delete("tasks","id=?",new String[]{id});
    for(Context context:new Context[]{main,seven}){
      if(context==null)continue;
      SharedPreferences tasks=context.getSharedPreferences("download-tasks",0);JSONArray old=new JSONArray(tasks.getString("rows","[]")),kept=new JSONArray();
      for(int i=0;i<old.length();i++){JSONObject row=old.optJSONObject(i);if(row!=null&&!ownIds.contains(row.optString("id"))&&!ownUris.contains(row.optString("uri")))kept.put(row);}
      if(!tasks.edit().putString("rows",kept.toString()).commit())throw new IllegalStateException("Synthetic task cleanup failed");
      SharedPreferences chat=context.getSharedPreferences("chat",0);JSONObject value=J.parse(chat.getString("downloadHistory","{}"));JSONArray oldHistory=value.optJSONArray("files");
      if(oldHistory!=null){JSONArray retained=new JSONArray();for(int i=0;i<oldHistory.length();i++){JSONObject row=oldHistory.optJSONObject(i);if(row!=null&&!ownUris.contains(row.optString("uri")))retained.put(row);}value.put("files",retained);if(!chat.edit().putString("downloadHistory",value.toString()).commit())throw new IllegalStateException("Synthetic history cleanup failed");}
    }
    report.put("ownSyntheticDestinationsCleaned",true);
  }
}
