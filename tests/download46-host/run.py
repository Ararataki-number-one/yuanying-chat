#!/usr/bin/env python3
"""Source-bound 46 download behaviors; preserves all existing harness sources."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat';OLD=ROOT/'tests/download-recovery-host'
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 names=['J.java','DownloadTaskRevisions.java','DownloadTasks.java','DownloadResumePolicy.java','DefaultDownloads.java','SavedFilePublication.java','SavedFileDeletion.java','SealedFileIo.java','DownloadMetadataValues.java','SavedDownloadMetadata.java','SavedFileBytes.java','DownloadPageWindow.java','DownloadListPolicy.java','DownloadRowBinding.java','DownloadOwnerLabels.java']
 inputs=[PROD/n for n in names]+[HERE/'Metadata46Cases.java',pathlib.Path(__file__).resolve(),OLD/'local/pocketchat/Support.java',OLD/'local/pocketchat/DownloadRecoveryHostTest.java',ROOT/'tests/sealed-file-host/android/util/AtomicFile.java']+sorted((OLD/'android').rglob('*.java'))
 hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inputs}
 with tempfile.TemporaryDirectory(prefix='download46-host-')as raw:
  temp=pathlib.Path(raw);pkg=temp/'local/pocketchat';pkg.mkdir(parents=True)
  for name in names:(pkg/name).write_bytes((PROD/name).read_bytes())
  for name in ['Metadata46Cases.java']:(pkg/name).write_bytes((HERE/name).read_bytes())
  (pkg/'DownloadRecoveryHostTest.java').write_bytes((OLD/'local/pocketchat/DownloadRecoveryHostTest.java').read_bytes())
  support=(OLD/'local/pocketchat/Support.java').read_text()
  support=support.replace('static Context global(Context c)', 'static final int MAX=8;static Context context(Context c,int slot){return new Context(c.root,slot);}static Context global(Context c)')
  support=support.replace('final Set<String> deleted=new HashSet<>();','final Set<String> deleted=new HashSet<>();int metadataWrites;static void changed(Context c){}JSONArray metadataPage(long after,int limit){return new JSONArray();}synchronized boolean metadataUpdate(JSONObject before,JSONObject after){JSONObject current=saved(before);if(current==null||!DownloadTaskRevisions.value(current).equals(DownloadTaskRevisions.value(before)))return false;saved.put(before.optString("uri"),J.parse(after.toString()));metadataWrites++;return true;}')
  support=support.replace('current.optString("id").equals(row.optString("id"))?', 'current.optString("id").equals(row.optString("id"))&&current.optLong("time")==row.optLong("time")?')
  support+='\nfinal class ProfileCatalog{static volatile int generation=1;static ProfileCatalog get(Context c){return new ProfileCatalog();}JSONObject item(int slot){return J.obj("environmentId","00000000-0000-0000-0000-00000000000"+slot,"generation",generation,"created",true,"deleting",false,"resetting",false);}}\n'
  (pkg/'Support.java').write_text(support)
  for f in (OLD/'android').rglob('*.java'):
   target=temp/f.relative_to(OLD);target.parent.mkdir(parents=True,exist_ok=True);text=f.read_text()
   if f.name=='Cursor.java':text=text.replace('boolean moveToFirst();','int FIELD_TYPE_INTEGER=1;boolean moveToFirst();default int getType(int at){return FIELD_TYPE_INTEGER;}default int getColumnIndex(String name){return name.equals("_display_name")?0:1;}')
   if f.name=='OpenableColumns.java':text=text.replace('public static final String SIZE=', 'public static final String DISPLAY_NAME="_display_name";public static final String SIZE=')
   target.write_text(text)
  (temp/'android/os/CancellationSignal.java').write_text('package android.os;public final class CancellationSignal{volatile boolean cancelled;public void cancel(){cancelled=true;}public boolean isCanceled(){return cancelled;}}')
  (temp/'android/os/ParcelFileDescriptor.java').write_text('package android.os;public final class ParcelFileDescriptor implements AutoCloseable{public void close(){}}')
  (temp/'android/content/ContentResolver.java').write_text('''package android.content;import android.net.Uri;import android.database.Cursor;import android.os.*;import java.io.*;public final class ContentResolver {
   final Context c;ContentResolver(Context c){this.c=c;}public static Long size=0L;public static boolean exists=true,throwQuery,missingSize,nonIntegral;public static int queries,mainQueries,opens;public static Runnable duringQuery;
   public static void reset(){queries=mainQueries=opens=0;size=0L;exists=true;throwQuery=missingSize=nonIntegral=false;duringQuery=null;}
   File file(Uri u){java.util.List<String> p=u.getPathSegments();return new File(new Context(c.root,Integer.parseInt(p.get(0))).getFilesDir(),"saved-downloads/"+p.get(1)+"/"+p.get(2));}
   public OutputStream openOutputStream(Uri u,String mode)throws IOException{return new FileOutputStream(file(u));}
   public Uri insert(Uri uri,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri uri,ContentValues v,String w,String[] a){throw new UnsupportedOperationException();}public int delete(Uri uri,String w,String[] a){return file(uri).delete()?1:0;}
   public String getType(Uri uri){return "application/octet-stream";}
   public ParcelFileDescriptor openFileDescriptor(Uri uri,String mode)throws IOException{opens++;if(!exists)throw new FileNotFoundException();return new ParcelFileDescriptor();}
   public Cursor query(Uri uri,String[] cols,String w,String[] a,String order,CancellationSignal signal){return query(uri,cols,w,a,order);}
   public Cursor query(Uri uri,String[] cols,String w,String[] a,String order){queries++;if(Looper.myLooper()==Looper.getMainLooper())mainQueries++;if(throwQuery)throw new SecurityException();boolean own=uri.getAuthority().equals(c.getPackageName()+".saved-downloads");File f=own?file(uri):null;Long value=own?Long.valueOf(f.length()):size;Runnable mutation=duringQuery;duringQuery=null;if(mutation!=null)mutation.run();return new Cursor(){public int getColumnIndex(String name){return name.equals("_display_name")?0:missingSize?-1:1;}public int getType(int i){return nonIntegral?2:1;}public boolean moveToFirst(){return !own||f.isFile();}public String getString(int i){return own?f.getName():"actual-provider-name.txt";}public int getInt(int i){return 0;}public long getLong(int i){return value==null?-1:value;}public boolean isNull(int i){return i!=0&&value==null;}public void close(){}};}
  }''')
  java=[*pkg.glob('*.java'),*sorted((temp/'android').rglob('*.java')),ROOT/'tests/sealed-file-host/android/util/AtomicFile.java'];classes=temp/'classes';binary=lambda n:str(a.java_home/'bin'/n)
  compile=subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,java)],text=True,capture_output=True);(a.output/'compile.stdout.txt').write_text(compile.stdout);(a.output/'compile.stderr.txt').write_text(compile.stderr);compile.check_returncode()
  reports=[]
  for name in ['DownloadRecoveryHostTest','Metadata46Cases']:
   run=subprocess.run([binary('java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.'+name],text=True,capture_output=True,timeout=90);(a.output/(name+'.stdout.txt')).write_text(run.stdout);(a.output/(name+'.stderr.txt')).write_text(run.stderr)
   report=json.loads(run.stdout);report['exitCode']=run.returncode;reports.append(report);assert run.returncode==0 and report['status']=='passed',report
  unchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items());receipt={'status':'passed'if unchanged else'invalid-source-changed','reports':reports,'sourceFiles':hashes,'executionInputsUnchanged':unchanged,'jsonJarSha256':hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),'actualAndroidExecution':False,'phonePerformanceMeasured':False};(a.output/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');assert unchanged
  print(json.dumps({'status':receipt['status'],'checks':[x['total']for x in reports],'output':str(a.output)},ensure_ascii=False))
if __name__=='__main__':main()
