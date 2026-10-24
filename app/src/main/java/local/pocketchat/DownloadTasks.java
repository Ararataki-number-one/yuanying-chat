package local.pocketchat;
import android.content.*;import org.json.*;import java.io.*;import java.util.*;

/** Private metadata, without cookies or temporary signed download URLs. */
final class DownloadTasks {
 final Context context;final SharedPreferences prefs;final String ownerPrefix;final Durability durability;JSONArray rows;
 final android.os.Handler main=new android.os.Handler(android.os.Looper.getMainLooper());
 static final java.util.concurrent.ExecutorService recovery=java.util.concurrent.Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"download-recovery");t.setDaemon(true);return t;});
 Map<String,String> observed;volatile boolean recovering;volatile Throwable recoveryFailure;volatile RuntimeException indexFailure;
 static final class Durability {volatile String confirmed;volatile boolean unconfirmed;Durability(String rows){confirmed=rows;}}
 static final class PersistenceFailure extends IllegalStateException {PersistenceFailure(Throwable cause){super("下载记录尚未写入存储，请稍后重试",cause);}}
 static final java.util.concurrent.ConcurrentMap<String,Durability> stores=new java.util.concurrent.ConcurrentHashMap<>();
 static final java.util.concurrent.ConcurrentMap<String,java.lang.ref.WeakReference<DownloadTasks>> owners=new java.util.concurrent.ConcurrentHashMap<>();
 final Set<String> owned=new HashSet<>();
 String ownerKey(String id){return ownerPrefix+id;}
 boolean liveOwner(String id){java.lang.ref.WeakReference<DownloadTasks> ref=owners.get(ownerKey(id));return ref!=null&&ref.get()!=null;}
 boolean claim(JSONObject row){
  save();if(row==null||DownloadTaskRevisions.find(rows,row.optString("id"))!=row)return false;String key=ownerKey(row.optString("id"));
  while(true){java.lang.ref.WeakReference<DownloadTasks> old=owners.get(key);DownloadTasks live=old==null?null:old.get();if(live!=null&&live!=this)return false;
   java.lang.ref.WeakReference<DownloadTasks> next=new java.lang.ref.WeakReference<>(this);
   if(old==null?owners.putIfAbsent(key,next)==null:owners.replace(key,old,next))break;
  }
  // Only a successful claim retires this instance's previous task. Merely opening
  // another Activity must not cancel a live publisher or lose our current owner.
  for(String previous:new HashSet<>(owned))if(!previous.equals(key)){java.lang.ref.WeakReference<DownloadTasks> old=owners.get(previous);if(old!=null&&old.get()==this)owners.remove(previous,old);owned.remove(previous);}
  owned.add(key);put(row,"taskGeneration",UUID.randomUUID().toString());save();return owns(row);
 }
 void release(){for(String key:owned){java.lang.ref.WeakReference<DownloadTasks> ref=owners.get(key);if(ref!=null&&ref.get()==this)owners.remove(key,ref);}owned.clear();}
 DownloadTasks(Context c){
  context=c;prefs=c.getSharedPreferences("download-tasks",0);ownerPrefix=c.getFilesDir().getAbsolutePath()+"/";durability=stores.computeIfAbsent(ownerPrefix,k->new Durability(prefs.getString("rows","[]")));rows=read();observed=DownloadTaskRevisions.snapshot(rows);
  JSONArray initial=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&(!row.optString("pendingDestination").isEmpty()||Arrays.asList("downloading","preparing","saving","choosing").contains(row.optString("state"))))initial.put(J.parse(row.toString()));}recovering=initial.length()>0;
  if(rows.length()>0||durability.unconfirmed)recovery.execute(()->{try{for(int i=0;i<initial.length();i++){JSONObject row=initial.optJSONObject(i);if(row!=null)recover(row);}}catch(Exception error){recoveryFailure=error;}finally{main.post(()->{try{save();}catch(RuntimeException error){recoveryFailure=error;}finally{recovering=false;}});}});
 }
 JSONArray read(){try{return new JSONArray(durability.unconfirmed?durability.confirmed:prefs.getString("rows","[]"));}catch(Exception error){return new JSONArray();}}
 static JSONArray copy(JSONArray rows){try{return new JSONArray(rows.toString());}catch(Exception error){throw new IllegalStateException(error);}}
 void recover(JSONObject initial)throws Exception{
  String pending=initial.optString("pendingDestination");
  if(pending.isEmpty()){recoverOwned(initial);return;}
  // Never enter the URI lease on the UI thread. An older publisher can still be
  // waiting for its final main-thread commit while this new instance is created.
  SavedFileDeletion.lease(context,android.net.Uri.parse(pending),()->{recoverOwned(initial);return null;});
 }
 void recoverOwned(JSONObject initial)throws Exception{
  final JSONObject[] candidate={null};
  SavedFileDeletion.onMain(main,()->{
   save();JSONObject latest=DownloadTaskRevisions.find(rows,initial.optString("id"));
   if(latest!=null&&DownloadTaskRevisions.value(latest).equals(DownloadTaskRevisions.value(initial))&&(!latest.optString("pendingDestination").isEmpty()||!liveOwner(latest.optString("id"))))candidate[0]=J.parse(latest.toString());
  });
  JSONObject row=candidate[0];if(row==null)return;String before=DownloadTaskRevisions.value(row);
  if(!row.optString("pendingDestination").isEmpty())DefaultDownloads.recoverOwned(context,row);
  if(Arrays.asList("downloading","preparing","saving","choosing").contains(row.optString("state")))put(row,"state",partial(row)!=null?"paused":"failed","reason","上次下载中断；可重新获取链接继续");
  if(before.equals(DownloadTaskRevisions.value(row)))return;
  SavedFileDeletion.onMain(main,()->{
   save();JSONObject latest=DownloadTaskRevisions.find(rows,row.optString("id"));
   if(latest==null||!before.equals(DownloadTaskRevisions.value(latest))||latest.optString("pendingDestination").isEmpty()&&liveOwner(latest.optString("id")))return;
   JSONArray next=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);next.put(item==latest?row:item);}rows=next;save();
  });
 }
 boolean published(JSONObject row,android.net.Uri uri){JSONObject stored;try{stored=DownloadTaskRevisions.find(new JSONArray(durability.confirmed),row.optString("id"));}catch(Exception error){return false;}return stored!=null&&"saved".equals(stored.optString("state"))&&uri.toString().equals(stored.optString("uri"));}
 boolean owns(JSONObject row){if(row==null||DownloadTaskRevisions.find(rows,row.optString("id"))!=row)return false;java.lang.ref.WeakReference<DownloadTasks> owner=owners.get(ownerKey(row.optString("id")));return owner!=null&&owner.get()==this;}
 void beginSave(JSONObject row,android.net.Uri uri,String location,String name,String generation){
  save();if(!owns(row))throw new IllegalStateException("下载任务已变化，请重新打开下载记录");
  put(row,"pendingDestination",uri.toString(),"pendingLocation",location,"pendingName",name,"pendingGeneration",generation);save();requirePending(row,uri,generation);
 }
 void requirePending(JSONObject row,android.net.Uri uri,String generation){
  JSONObject stored=DownloadTaskRevisions.find(read(),row.optString("id"));
  if(!owns(row)||!DownloadTaskRevisions.pending(row,uri.toString(),generation)||!DownloadTaskRevisions.pending(stored,uri.toString(),generation))throw new IllegalStateException("下载任务已变化，请重新保存");
 }
 void finishSave(JSONObject row,android.net.Uri uri,String generation,Runnable changes){
  requirePending(row,uri,generation);JSONObject previous=J.parse(row.toString());
  try{changes.run();DownloadTaskRevisions.clearPending(row);save(true);}
  catch(RuntimeException error){DownloadTaskRevisions.restore(row,previous);throw error instanceof PersistenceFailure?error:new PersistenceFailure(error);}
 }
 void clearPending(JSONObject row,android.net.Uri uri,String generation){
  JSONObject stored=DownloadTaskRevisions.find(read(),row.optString("id"));
  if(!owns(row)||!DownloadTaskRevisions.pending(row,uri.toString(),generation)||!DownloadTaskRevisions.pending(stored,uri.toString(),generation))return;
  DownloadTaskRevisions.clearPending(row);save();
 }
 static void put(JSONObject r,Object... pairs){try{for(int i=0;i<pairs.length;i+=2)r.put((String)pairs[i],pairs[i+1]);}catch(Exception ignored){}}
 JSONObject add(String source,String key,String conversation){release();JSONObject r=J.obj("id",UUID.randomUUID().toString(),"source",source,"key",key,"conversation",conversation,"name","正在获取文件","state","preparing","reason","","received",0,"total",-1,"time",System.currentTimeMillis());JSONArray next=new JSONArray();next.put(r);for(int i=0;i<rows.length();i++)next.put(rows.optJSONObject(i));rows=next;if(!claim(r))throw new IllegalStateException("下载任务已变化，请重试");return r;}
 void save(){save(false);}
 void save(boolean forceCommit){
  DownloadLibrary library=DownloadLibrary.get(context);rows=library.prune(DownloadTaskRevisions.merge(rows,observed,read()));
  SharedPreferences chat=context.getSharedPreferences("chat",0);JSONObject history=J.parse(chat.getString("downloadHistory","{}"));JSONArray files=history.optJSONArray("files");
  if(files!=null){JSONArray kept=library.prune(files);if(!kept.toString().equals(files.toString())){DownloadTasks.put(history,"files",kept);chat.edit().putString("downloadHistory",history.toString()).commit();}}
  String serialized=rows.toString();
  // Android commit(false) may already have replaced SharedPreferences memory.
  // Equality with getString is not a durability receipt, including in a new instance.
  if(forceCommit||durability.unconfirmed||!serialized.equals(durability.confirmed)||!serialized.equals(prefs.getString("rows","[]"))){
   durability.unconfirmed=true;boolean committed;
   try{committed=prefs.edit().putString("rows",serialized).commit();}catch(RuntimeException error){throw new PersistenceFailure(error);}
   if(!committed)throw new PersistenceFailure(null);
   durability.confirmed=serialized;durability.unconfirmed=false;
  }
  observed=DownloadTaskRevisions.snapshot(rows);
  try{library.sync(context,rows);for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if("saved".equals(row.optString("state")))library.add(context,row);}indexFailure=null;}
  catch(RuntimeException error){indexFailure=error;/* Confirmed tasks remain authoritative; a later save or instance repairs the index. */}
 }
 JSONObject recoveredRow(JSONObject previous){return recoveryFailure==null?DownloadTaskRevisions.find(rows,previous.optString("id")):null;}
 void recoverPending(JSONObject row,Runnable done){
  JSONObject initial=J.parse(row.toString());recovering=true;recoveryFailure=null;
  recovery.execute(()->{try{recover(initial);}catch(Exception error){recoveryFailure=error;}finally{main.post(()->{recovering=false;done.run();});}});
 }
 /** A confirmed user-selected restart retires only an incomplete private cache file.
  * This is not a saved destination or a publication recovery operation. */
 boolean beginPartialRetirement(JSONObject row,String generation,String name){
  save();if(!retirementOwner(row,generation)||retirementFile(row)==null||!DownloadResumePolicy.incomplete(row)||!name.equals(partialName(row))||referencedElsewhere(row,name,rows))return false;
  JSONObject previous=J.parse(row.toString());
  try{
   put(row,"partial","","retiredPartial",name,"received",0,"total",-1,"validator","","resource","","state","cancelled","reason","旧副本清理尚未完成，请重新下载时重试");
   save(true);return retiredPartialCurrent(row,generation,name);
  }catch(RuntimeException error){DownloadTaskRevisions.restore(row,previous);throw error;}
 }
 boolean retirementOwner(JSONObject row,String generation){return !recovering&&recoveryFailure==null&&owns(row)&&!generation.isEmpty()&&generation.equals(row.optString("taskGeneration"));}
 static String partialName(JSONObject row){String name=row.optString("partial");return name.isEmpty()?row.optString("retiredPartial"):name;}
 static boolean referencedElsewhere(JSONObject selected,String name,JSONArray known){
  for(int i=0;i<known.length();i++){JSONObject row=known.optJSONObject(i);if(row!=null&&!selected.optString("id").equals(row.optString("id"))&&(name.equals(row.optString("partial"))||name.equals(row.optString("retiredPartial"))))return true;}return false;
 }
 boolean retiredPartialCurrent(JSONObject row,String generation,String name){
  if(!retirementOwner(row,generation)||durability.unconfirmed||!DownloadResumePolicy.incomplete(row)||!row.optString("partial").isEmpty()||!name.equals(row.optString("retiredPartial")))return false;
  JSONObject stored;JSONArray confirmed;
  try{confirmed=new JSONArray(durability.confirmed);stored=DownloadTaskRevisions.find(confirmed,row.optString("id"));}catch(Exception invalid){return false;}
  return stored!=null&&DownloadTaskRevisions.value(stored).equals(DownloadTaskRevisions.value(row))&&!referencedElsewhere(row,name,rows)&&!referencedElsewhere(row,name,confirmed);
 }
 void finishPartialRetirement(JSONObject row,String generation,String name){
  if(!retiredPartialCurrent(row,generation,name))return;JSONObject previous=J.parse(row.toString());
  try{row.remove("retiredPartial");put(row,"reason","旧的未完成副本已清理，请回原网页重新下载");save(true);}
  catch(RuntimeException error){DownloadTaskRevisions.restore(row,previous);throw error;}
 }
 File retirementFile(JSONObject row){
  String name=partialName(row);if(!name.matches("download-[A-Za-z0-9-]+[.]part"))return null;
  try{File root=context.getCacheDir().getCanonicalFile(),file=new File(root,name);if(!root.equals(file.getCanonicalFile().getParentFile())||!file.getAbsoluteFile().equals(file.getCanonicalFile()))return null;return file.isFile()||!file.exists()&&row.optString("partial").isEmpty()&&name.equals(row.optString("retiredPartial"))?file:null;}catch(IOException invalid){return null;}
 }
 File partial(JSONObject r){String n=r.optString("partial");if(!n.matches("download-[A-Za-z0-9-]+[.]part"))return null;File f=new File(context.getCacheDir(),n);return f.isFile()?f:null;}
 static String label(String state){switch(state){case "preparing":return "获取链接中";case "downloading":return "下载中";case "paused":return "已暂停";case "choosing":return "等待选择保存位置";case "saving":return "保存中";case "saved":return "已保存";case "cancelled":return "已取消";default:return "失败待处理";}}
 static String amount(long n){return Attachments.sizeLabel(n);}
 static String progress(JSONObject r){long received=r.optLong("received"),total=r.optLong("total",-1);return total>0?amount(received)+" / "+amount(total)+" · "+Math.min(100,received*100/total)+"%":amount(received);}
}
