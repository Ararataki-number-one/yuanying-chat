#!/usr/bin/env python3
"""Run exact production chooser members with explicit Android boundary adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'


def member(source, needle):
    start=source.index(needle); opened=source.index('{',start)
    depth=0; quote=None; escaped=False; line=False; block=False; index=opened
    while index<len(source):
        char=source[index]; pair=source[index:index+2]
        if line:
            if char=='\n': line=False
        elif block:
            if pair=='*/': block=False; index+=1
        elif quote:
            if escaped: escaped=False
            elif char=='\\': escaped=True
            elif char==quote: quote=None
        elif pair=='//': line=True; index+=1
        elif pair=='/*': block=True; index+=1
        elif char in ('"',"'"): quote=char
        elif char=='{': depth+=1
        elif char=='}':
            depth-=1
            if depth==0: return source[start:index+1]
        index+=1
    raise ValueError(needle)


STUBS={
'android/net/Uri.java':'''package android.net;
public final class Uri {
  final String value; final java.net.URI parsed;
  private Uri(String raw){value=raw;parsed=java.net.URI.create(raw);}
  public static Uri parse(String raw){return new Uri(raw);}
  public String getScheme(){return parsed.getScheme();}
  public String getAuthority(){return parsed.getRawAuthority();}
  public java.util.List<String> getPathSegments(){java.util.List<String> result=new java.util.ArrayList<>();for(String part:parsed.getPath().split("/"))if(!part.isEmpty())result.add(part);return result;}
  public String toString(){return value;}
  public boolean equals(Object other){return other instanceof Uri&&value.equals(((Uri)other).value);}
  public int hashCode(){return value.hashCode();}
  public static final class Builder {
    String scheme,authority;final java.util.List<String> segments=new java.util.ArrayList<>();
    public Builder scheme(String value){scheme=value;return this;}
    public Builder authority(String value){authority=value;return this;}
    public Builder appendPath(String value){segments.add(java.net.URLEncoder.encode(value,java.nio.charset.StandardCharsets.UTF_8).replace("+","%20"));return this;}
    public Uri build(){return Uri.parse(scheme+"://"+authority+"/"+String.join("/",segments));}
  }
}''',
'android/content/Context.java':'''package android.content;
public class Context {
  public int slot;public final ContentResolver resolver=new ContentResolver();public final SharedPreferences preferences=new SharedPreferences();
  public final java.util.List<String> preferenceNames=new java.util.ArrayList<>();
  private java.io.File directory;
  public Context getApplicationContext(){return this;}
  public String getPackageName(){return "local.pocketchat";}
  public ContentResolver getContentResolver(){return resolver;}
  public java.io.File getFilesDir(){if(directory==null)try{directory=java.nio.file.Files.createTempDirectory("browser-store-context-").toFile();}catch(java.io.IOException error){throw new IllegalStateException(error);}return directory;}
  public SharedPreferences getSharedPreferences(String name,int mode){preferenceNames.add(name);return preferences;}
  public void clean(){if(directory!=null)try(java.util.stream.Stream<java.nio.file.Path> paths=java.nio.file.Files.walk(directory.toPath())){paths.sorted(java.util.Comparator.reverseOrder()).forEach(path->{try{java.nio.file.Files.delete(path);}catch(java.io.IOException error){throw new IllegalStateException(error);}});}catch(java.io.IOException error){throw new IllegalStateException(error);}}
}''',
'android/content/ContentValues.java':'''package android.content;public final class ContentValues extends java.util.HashMap<String,Object> {public void put(String key,String value){super.put(key,value);}public void put(String key,Integer value){super.put(key,value);}}''',
'android/content/SharedPreferences.java':'''package android.content;public final class SharedPreferences {public final java.util.Map<String,String> values=new java.util.HashMap<>();public int writes;public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}public Editor edit(){return new Editor();}public final class Editor{public Editor putString(String key,String value){values.put(key,value);return this;}public boolean commit(){writes++;return true;}}}''',
'android/content/ContentResolver.java':'''package android.content;
import android.net.Uri;import android.database.Cursor;
public final class ContentResolver {
  public Uri insertedCollection;public ContentValues insertedValues;public String displayName;public boolean denyInsert;public int updates,deletes,updateResult=1;private int sequence;
  public final java.util.Map<Uri,byte[]> contents=new java.util.HashMap<>();
  public Uri insert(Uri collection,ContentValues values){insertedCollection=collection;insertedValues=values;return denyInsert?null:Uri.parse("content://media/external/downloads/"+(++sequence));}
  public Cursor query(Uri uri,String[] projection,String selection,String[] arguments,String sort){return new Cursor(displayName==null?(String)insertedValues.get(android.provider.MediaStore.MediaColumns.DISPLAY_NAME):displayName);}
  public java.io.OutputStream openOutputStream(Uri uri,String mode){return new java.io.ByteArrayOutputStream(){public void close()throws java.io.IOException{super.close();contents.put(uri,toByteArray());}};}
  public int update(Uri uri,ContentValues values,String selection,String[] arguments){updates++;return updateResult;}
  public int delete(Uri uri,String selection,String[] arguments){deletes++;contents.remove(uri);return 1;}
}''',
'android/database/Cursor.java':'''package android.database;public final class Cursor implements AutoCloseable {final String value;public Cursor(String value){this.value=value;}public boolean moveToFirst(){return true;}public String getString(int index){return value;}public void close(){}}''',
'android/provider/MediaStore.java':'''package android.provider;
public final class MediaStore {
  public static final class MediaColumns {public static final String DISPLAY_NAME="display_name",MIME_TYPE="mime_type",RELATIVE_PATH="relative_path",IS_PENDING="is_pending";}
  public static final class Downloads {public static final android.net.Uri EXTERNAL_CONTENT_URI=android.net.Uri.parse("content://media/external/downloads");}
}''',
'android/content/Intent.java':'''package android.content;
import android.net.Uri; import java.util.*;
public class Intent {
  public static final String ACTION_OPEN_DOCUMENT="android.intent.action.OPEN_DOCUMENT",CATEGORY_OPENABLE="android.intent.category.OPENABLE",EXTRA_MIME_TYPES="android.intent.extra.MIME_TYPES",EXTRA_ALLOW_MULTIPLE="android.intent.extra.ALLOW_MULTIPLE";
  public static final String ACTION_VIEW="android.intent.action.VIEW",ACTION_CHOOSER="android.intent.action.CHOOSER",CATEGORY_BROWSABLE="android.intent.category.BROWSABLE",EXTRA_INTENT="android.intent.extra.INTENT",EXTRA_TITLE="android.intent.extra.TITLE",EXTRA_EXCLUDE_COMPONENTS="android.intent.extra.EXCLUDE_COMPONENTS";
  public static final int FLAG_GRANT_READ_URI_PERMISSION=1,FLAG_GRANT_WRITE_URI_PERMISSION=2,FLAG_GRANT_PERSISTABLE_URI_PERMISSION=64;
  public String action,type;public int flags;public final Set<String> categories=new HashSet<>();public final Map<String,Object> extras=new HashMap<>();
  public Uri data;public ClipData clip;public RuntimeException clipFailure,dataFailure;
  public Intent(String action){this.action=action;}
  public Intent(String action,Uri uri){this.action=action;data=uri;}
  public static Intent createChooser(Intent target,CharSequence title){Intent chooser=new Intent(ACTION_CHOOSER);chooser.extras.put(EXTRA_INTENT,target);chooser.extras.put(EXTRA_TITLE,title);return chooser;}
  public Intent addCategory(String category){categories.add(category);return this;}
  public Intent setType(String value){type=value;return this;}
  public Intent addFlags(int value){flags|=value;return this;}
  public Intent putExtra(String key,String[] value){extras.put(key,value);return this;}
  public Intent putExtra(String key,boolean value){extras.put(key,value);return this;}
  public Intent putExtra(String key,Object[] value){extras.put(key,value);return this;}
  public Intent setData(Uri value){data=value;return this;}
  public Intent setClipData(ClipData value){clip=value;return this;}
  public ClipData getClipData(){if(clipFailure!=null)throw clipFailure;return clip;}
  public Uri getData(){if(dataFailure!=null)throw dataFailure;return data;}
}''',
'android/content/ComponentName.java':'''package android.content;public final class ComponentName {public final String packageName,className;public ComponentName(Context context,Class<?> type){packageName=context.getPackageName();className=type.getName();}}''',
'android/content/DialogInterface.java':'''package android.content;public interface DialogInterface {interface OnClickListener {void onClick(DialogInterface dialog,int which);}}''',
'android/content/ClipData.java':'''package android.content;
import android.net.Uri;import java.util.*;
public final class ClipData {
  public final List<Item> items=new ArrayList<>();public RuntimeException itemFailure;
  public ClipData(Uri... values){for(Uri value:values)items.add(new Item(value));}
  public int getItemCount(){return items.size();}
  public Item getItemAt(int index){if(itemFailure!=null)throw itemFailure;return items.get(index);}
  public static final class Item {public final Uri uri;public RuntimeException uriFailure;Item(Uri value){uri=value;}public Uri getUri(){if(uriFailure!=null)throw uriFailure;return uri;}}
}''',
'android/content/ActivityNotFoundException.java':'''package android.content;public class ActivityNotFoundException extends RuntimeException {public ActivityNotFoundException(){super("unavailable");}}''',
'android/content/pm/ApplicationInfo.java':'''package android.content.pm;public final class ApplicationInfo {public int uid;}''',
'android/content/pm/ProviderInfo.java':'''package android.content.pm;public final class ProviderInfo {public ApplicationInfo applicationInfo=new ApplicationInfo();}''',
'android/content/pm/PackageManager.java':'''package android.content.pm;
import java.util.*;
public final class PackageManager {
  public static final int PERMISSION_GRANTED=0,PERMISSION_DENIED=-1;
  public final Map<String,ProviderInfo> providers=new HashMap<>();public RuntimeException failure;
  public ProviderInfo resolveContentProvider(String authority,int flags){if(failure!=null)throw failure;return providers.get(authority);}
}''',
'android/app/Activity.java':'''package android.app;
import android.content.*;import android.content.pm.*;import android.net.Uri;import java.util.*;
public class Activity extends Context {
  public static final int RESULT_OK=-1,RESULT_CANCELED=0;
  public final List<Integer> requests=new ArrayList<>(),finished=new ArrayList<>();public final List<Intent> intents=new ArrayList<>();
  public final List<Intent> started=new ArrayList<>();public int startAttempts;public RuntimeException viewLaunchFailure;
  public final Set<Uri> grants=new HashSet<>();public final PackageManager packages=new PackageManager();
  public RuntimeException launchFailure,finishFailure,permissionFailure;public Runnable onLaunch;
  public void startActivityForResult(Intent intent,int request){requests.add(request);intents.add(intent);RuntimeException failure=launchFailure;launchFailure=null;Runnable action=onLaunch;onLaunch=null;if(action!=null)action.run();if(failure!=null)throw failure;}
  public void startActivity(Intent intent){startAttempts++;if(viewLaunchFailure!=null)throw viewLaunchFailure;started.add(intent);}
  public void finishActivity(int request){finished.add(request);if(finishFailure!=null)throw finishFailure;}
  public PackageManager getPackageManager(){return packages;}
  public int checkUriPermission(Uri uri,int pid,int uid,int flags){if(permissionFailure!=null)throw permissionFailure;if(pid!=android.os.Process.myPid()||uid!=android.os.Process.myUid()||flags!=Intent.FLAG_GRANT_READ_URI_PERMISSION)throw new AssertionError("Incorrect grant check boundary");return grants.contains(uri)?PackageManager.PERMISSION_GRANTED:PackageManager.PERMISSION_DENIED;}
}''',
'android/app/AlertDialog.java':'''package android.app;
import android.content.DialogInterface;
public final class AlertDialog implements DialogInterface {
  public int dismissed;public String title,message;public DialogInterface.OnClickListener positive,negative;
  public void dismiss(){dismissed++;}public void confirm(){if(positive!=null)positive.onClick(this,-1);}public void cancel(){if(negative!=null)negative.onClick(this,-2);dismiss();}
  public static final class Builder {
    final AlertDialog dialog=new AlertDialog();public Builder(Activity activity){}
    public Builder setTitle(String value){dialog.title=value;return this;}public Builder setMessage(String value){dialog.message=value;return this;}
    public Builder setPositiveButton(String label,DialogInterface.OnClickListener listener){dialog.positive=listener;return this;}public Builder setNegativeButton(String label,DialogInterface.OnClickListener listener){dialog.negative=listener;return this;}
    public AlertDialog show(){return dialog;}
  }
}''',
'android/os/Process.java':'''package android.os;public final class Process {public static int myUid(){return 1000;}public static int myPid(){return 1234;}}''',
'android/os/Looper.java':'''package android.os;public final class Looper {public static Looper getMainLooper(){return new Looper();}}''',
'android/os/Handler.java':'''package android.os;public final class Handler {public int removed;public Handler(Looper ignored){}public void removeCallbacksAndMessages(Object token){removed++;}}''',
'android/os/Build.java':'''package android.os;public final class Build {public static final class VERSION {public static int SDK_INT=29;}}''',
'android/webkit/ValueCallback.java':'''package android.webkit;public interface ValueCallback<T> {void onReceiveValue(T value);}''',
'android/webkit/WebView.java':'''package android.webkit;public final class WebView {public String url;public WebView(String value){url=value;}public String getUrl(){return url;}}''',
'android/webkit/WebChromeClient.java':'''package android.webkit;public final class WebChromeClient {public abstract static class FileChooserParams {public static final int MODE_OPEN=0,MODE_OPEN_MULTIPLE=1,MODE_OPEN_FOLDER=2,MODE_SAVE=3;public abstract int getMode();public abstract String[] getAcceptTypes();}}''',
'android/webkit/MimeTypeMap.java':'''package android.webkit;
public final class MimeTypeMap {
  public static MimeTypeMap getSingleton(){return new MimeTypeMap();}
  public String getMimeTypeFromExtension(String value){switch(value){case "pdf":return "application/pdf";case "txt":return "text/plain";case "png":return "image/png";case "jpg":case "jpeg":return "image/jpeg";default:return null;}}
}''',
'local/pocketchat/ChromiumRuntime.java':'''package local.pocketchat;final class ChromiumRuntime {}''',
'local/pocketchat/BrowserActivity.java':'''package local.pocketchat;final class BrowserActivity {}''',
'local/pocketchat/Profiles.java':'''package local.pocketchat;
final class Profiles {
  static final java.util.Map<Integer,android.content.Context> contexts=new java.util.HashMap<>();static int requestedSlot=-1;
  static int slot(android.content.Context context){return context.slot;}
  static android.content.Context context(android.content.Context caller,int slot){requestedSlot=slot;android.content.Context context=contexts.get(slot);if(context==null)throw new IllegalStateException("Unconfigured profile boundary");return context;}
}''',
'local/pocketchat/DownloadTasks.java':'''package local.pocketchat;final class DownloadTasks {static void put(org.json.JSONObject row,Object... values){try{for(int i=0;i<values.length;i+=2)row.put(String.valueOf(values[i]),values[i+1]);}catch(org.json.JSONException failure){throw new IllegalStateException(failure);}}}''',
'local/pocketchat/ProfileCatalog.java':'''package local.pocketchat;
final class ProfileCatalog {
  static final ProfileCatalog INSTANCE=new ProfileCatalog();static RuntimeException failure;static ProfileCatalog get(android.content.Context ignored){if(failure!=null)throw failure;return INSTANCE;}
  org.json.JSONObject item(int slot){org.json.JSONObject row=new org.json.JSONObject();DownloadTasks.put(row,"environmentId","environment-"+slot,"generation",100L+slot,"name","Environment "+slot);return row;}
}''',
'local/pocketchat/DownloadLibrary.java':'''package local.pocketchat;
import android.content.Context;import android.net.Uri;import org.json.*;import java.util.*;import java.util.function.Consumer;
final class DownloadLibrary {
  static DownloadLibrary instance=new DownloadLibrary();static RuntimeException getFailure;static DownloadLibrary get(Context ignored){if(getFailure!=null)throw getFailure;return instance;}static DownloadLibrary reset(){getFailure=null;return instance=new DownloadLibrary();}
  final Map<String,JSONObject> records=new LinkedHashMap<>();long clock=100000;int adds,savedQueries,indexedQueries,lists;
  boolean rejectAdd;RuntimeException addBefore,addAfter,savedFailure,indexedFailure,listFailure;Consumer<JSONObject> afterAdd;JSONObject lastAdded;
  static JSONObject copy(JSONObject row){try{return row==null?null:new JSONObject(row.toString());}catch(JSONException error){throw new IllegalStateException(error);}}
  long publicationTime(Uri uri){JSONObject prior=records.get(uri.toString());return clock=Math.max(clock+1,prior==null?0:prior.optLong("time")+1);}
  void add(Context context,JSONObject row){if(!SavedFileDeletion.held(row.optString("uri")))throw new AssertionError("Library add outside URI lease");adds++;lastAdded=copy(row);if(addBefore!=null)throw addBefore;if(!rejectAdd){JSONObject stored=copy(row);DownloadTasks.put(stored,"slot",Profiles.slot(context));records.put(row.optString("uri"),stored);}if(afterAdd!=null)afterAdd.accept(row);if(addAfter!=null)throw addAfter;}
  JSONObject saved(JSONObject expected){savedQueries++;if(savedFailure!=null)throw savedFailure;JSONObject current=records.get(expected.optString("uri"));return DownloadMetadataValues.identity(expected,current)?copy(current):null;}
  boolean indexed(Uri uri){indexedQueries++;if(indexedFailure!=null)throw indexedFailure;return records.containsKey(uri.toString());}
  JSONArray list(){lists++;if(listFailure!=null)throw listFailure;JSONArray rows=new JSONArray();for(JSONObject row:records.values())rows.put(copy(row));return rows;}
  void install(JSONObject row){records.put(row.optString("uri"),copy(row));}
  void remove(JSONObject expected){JSONObject current=records.get(expected.optString("uri"));if(!DownloadMetadataValues.identity(expected,current))throw new IllegalStateException("Newer publication must remain");records.remove(expected.optString("uri"));}
}''',
'local/pocketchat/SavedFileDeletion.java':'''package local.pocketchat;
import android.content.Context;import android.net.Uri;import org.json.JSONObject;import java.io.*;import java.util.*;import java.util.concurrent.locks.ReentrantLock;
final class SavedFileDeletion {
  interface Action<T>{T run()throws Exception;}
  static final Map<String,ReentrantLock> locks=new HashMap<>();static int leases,depth,maxDepth,removeAttempts;static RuntimeException removeFailure,leaseFailure;
  static boolean held(String uri){ReentrantLock lock=locks.get(uri);return lock!=null&&lock.isHeldByCurrentThread();}
  static void reset(){locks.clear();leases=depth=maxDepth=removeAttempts=0;removeFailure=leaseFailure=null;}
  static <T>T lease(Context context,Uri uri,Action<T> action)throws Exception{if(leaseFailure!=null)throw leaseFailure;ReentrantLock lock=locks.computeIfAbsent(uri.toString(),key->new ReentrantLock());lock.lock();leases++;depth++;maxDepth=Math.max(maxDepth,depth);try{return action.run();}finally{depth--;lock.unlock();}}
  static long remove(Context context,JSONObject expected)throws IOException{
    removeAttempts++;if(removeFailure!=null)throw removeFailure;
    try{return lease(context,Uri.parse(expected.optString("uri")),()->{DownloadLibrary library=DownloadLibrary.get(context);JSONObject current=library.saved(expected);if(current==null)throw new IOException("Publication changed");Uri uri=Uri.parse(current.optString("uri"));long bytes=current.optLong("savedBytes");if(uri.getAuthority().equals(context.getPackageName()+".saved-downloads")){File file=SavedDownloadResolve.resolve(context,uri);if(file.exists()&&!file.delete())throw new IOException("Delete failed");file.getParentFile().delete();}else context.getContentResolver().delete(uri,null,null);library.remove(current);return bytes;});}
    catch(IOException error){throw error;}catch(Exception error){throw new IOException("Controlled deletion failed",error);}
  }
}''',
}


def sha(value): return hashlib.sha256(value).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path,default=ROOT/'work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')
    parser.add_argument('--json-jar',type=Path,default=ROOT/'work/ux-build-deps/json-20240303.jar')
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-files-chooser-host')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'results.json').unlink(missing_ok=True)
    files_path=PROD/'BrowserFiles.java';source=files_path.read_text()
    prefix=source[:source.index('  void download(String url,')]
    destroyed=member(source,'void destroy()')
    handoff=member(source,'void handoff(')
    chooser=prefix+'  '+handoff+'\n  '+destroyed+'\n}\n'
    native_names=('BrowserDownloadTransfer.java','BrowserDownloadStore.java','BrowserAddressPolicy.java','DownloadMetadataValues.java','DownloadTaskRevisions.java')
    resolver_path=PROD/'SavedDownloadProvider.java';legacy_path=PROD/'FileDownloads.java'
    resolved=member(resolver_path.read_text(),'static File resolve(')
    safe_name=member(legacy_path.read_text(),'static String safeName(')
    inputs=[files_path,*[PROD/name for name in native_names],resolver_path,legacy_path,HERE/'ChooserCases.java.in',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in inputs}
    with tempfile.TemporaryDirectory(prefix='browser-chooser-host-') as raw:
        temp=Path(raw)
        generated=dict(STUBS)
        generated['local/pocketchat/BrowserFiles.java']=chooser
        for name in native_names:generated['local/pocketchat/'+name]=(PROD/name).read_text()
        generated['local/pocketchat/SavedDownloadResolve.java']='package local.pocketchat;\nimport android.content.Context;import android.net.Uri;import java.io.*;import java.util.*;\nfinal class SavedDownloadResolve {\n'+resolved+'\n}\nfinal class FileDownloads {\n'+safe_name+'\n}\n'
        generated['local/pocketchat/ChooserCases.java']=(HERE/'ChooserCases.java.in').read_text()
        for name,text in generated.items():
            target=temp/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
        classes=temp/'classes'
        compile=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),*map(str,temp.rglob('*.java'))],text=True,capture_output=True)
        (args.output/'compile.stdout.txt').write_text(compile.stdout);(args.output/'compile.stderr.txt').write_text(compile.stderr);compile.check_returncode()
        run=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(args.json_jar),'local.pocketchat.ChooserCases'],text=True,capture_output=True,timeout=45)
        (args.output/'stdout.txt').write_text(run.stdout);(args.output/'stderr.txt').write_text(run.stderr);run.check_returncode()
        report=json.loads(run.stdout)
    unchanged=all(sha((ROOT/path).read_bytes())==value for path,value in hashes.items())
    report.update(sourceSha256=hashes,chooserPrefixSha256=sha(prefix.encode()),destroyMemberSha256=sha(destroyed.encode()),handoffMemberSha256=sha(handoff.encode()),generatedChooserSha256=sha(chooser.encode()),resolveMemberSha256=sha(resolved.encode()),legacySafeNameMemberSha256=sha(safe_name.encode()),executionInputsUnchanged=unchanged,
        scope='Exact production BrowserFiles chooser/handoff/destroy, actual BrowserDownloadTransfer/BrowserAddressPolicy, full BrowserDownloadStore save/copy/publish/confirm/rollback/rows with real legacy local-file bytes, actual DownloadMetadataValues/DownloadTaskRevisions, exact SavedDownloadProvider.resolve/FileDownloads.safeName; controlled global DownloadLibrary, reentrant deletion lease/remove and Android Activity/Intent/URI/provider/MediaStore/WebView/Profiles/catalog adapters; not actual Android chooser resolution, SQLite or OS permission/provider acceptance',
        actualAndroidExecution=False,actualPickerExecution=False,actualProviderPermissionExecution=False)
    assert unchanged,'Production or test source changed while verifying'
    (args.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':report['passed'],'report':str(args.output/'results.json')},ensure_ascii=False))


if __name__=='__main__':main()
