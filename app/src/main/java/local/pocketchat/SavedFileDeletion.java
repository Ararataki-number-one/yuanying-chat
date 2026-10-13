package local.pocketchat;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import java.io.IOException;
import java.io.File;
import org.json.JSONObject;

/** Deletes only an indexed saved destination; failed deletion keeps its record. */
final class SavedFileDeletion {
  static long remove(Context context,JSONObject selected)throws IOException {
    try{return lease(context,Uri.parse(selected.optString("uri")),()->removeOwned(context,selected));}
    catch(IOException error){throw error;}
    catch(Exception error){throw new IOException("删除失败，下载记录已保留，请稍后重试",error);}
  }
  static <T>T lease(Context context,Uri uri,SealedFileIo.Action<T> action)throws Exception {
    File directory=new File(Profiles.global(context).getNoBackupFilesDir(),"saved-download-leases");
    if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("文件管理暂时不可用，请稍后重试");
    String name=AppUpdatePolicy.hash(uri.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    return SealedFileIo.lease(new File(directory,name),action);
  }
  /** Keep the worker's URI lease until publication really finishes. A timed-out
   * queued callback is made inert; a callback already running must finish first. */
  static void onMain(android.os.Handler handler,Runnable action)throws Exception {
    final Object gate=new Object();final boolean[] started={false},cancelled={false};
    final Throwable[] failure={null};java.util.concurrent.CountDownLatch done=new java.util.concurrent.CountDownLatch(1);
    boolean posted=handler.post(()->{
      synchronized(gate){if(cancelled[0]){done.countDown();return;}started[0]=true;}
      try{action.run();}catch(Throwable error){failure[0]=error;}finally{done.countDown();}
    });
    if(!posted)throw new IOException("保存页面已关闭，请重新保存文件");
    boolean interrupted=false,complete;
    try{complete=done.await(20,java.util.concurrent.TimeUnit.SECONDS);}
    catch(InterruptedException error){interrupted=true;complete=false;}
    if(!complete){
      synchronized(gate){if(!started[0]){cancelled[0]=true;throw new IOException("保存页面未响应，请重新保存文件");}}
      while(true)try{done.await();break;}catch(InterruptedException error){interrupted=true;}
    }
    if(interrupted)Thread.currentThread().interrupt();
    if(failure[0]!=null)throw new IOException("文件保存未完成，请重新保存",failure[0]);
  }
  private static long removeOwned(Context context,JSONObject selected)throws IOException {
    DownloadLibrary library=DownloadLibrary.get(context);
    if(library.isRemoved(selected))return 0; // A second old menu cannot delete a later download.
    JSONObject row=library.saved(selected);
    if(row==null)throw new IOException("下载记录已变化，请重新打开文件菜单");
    Uri uri=Uri.parse(row.optString("uri"));
    if(!"content".equals(uri.getScheme())||uri.getAuthority()==null)throw new IOException("这个文件需要在系统文件管理器中删除");
    try{
      long bytes=0;boolean absent=false;
      try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){
        if(cursor!=null){absent=!cursor.moveToFirst();if(!absent&&!cursor.isNull(0))bytes=Math.max(0,cursor.getLong(0));}
      }
      boolean own=(context.getPackageName()+".saved-downloads").equals(uri.getAuthority());
      if(own)absent=!SavedDownloadProvider.resolve(context,uri).isFile();
      if(!absent){
        boolean deleted=DocumentsContract.isDocumentUri(context,uri)
            ?DocumentsContract.deleteDocument(context.getContentResolver(),uri)
            :context.getContentResolver().delete(uri,null,null)>0;
        if(!deleted)throw new IOException("文件未能删除，下载记录已保留。请检查保存位置或使用系统文件管理器。");
      }
      library.removeSaved(row);
      return absent?0:bytes;
    }catch(SecurityException error){throw new IOException("没有删除此文件的权限，请在系统文件管理器中删除。下载记录已保留。",error);}
    catch(IOException error){throw error;}
    catch(Exception error){throw new IOException("删除失败，下载记录已保留，请稍后重试",error);}
  }
}
