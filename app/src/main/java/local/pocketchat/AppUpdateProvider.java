package local.pocketchat;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import java.io.*;

/** Private control endpoint and narrowly granted read-only access for Android's installer. */
public class AppUpdateProvider extends ContentProvider {
  public boolean onCreate(){return true;}
  AppUpdateManager manager(){return AppUpdateManager.get(getContext());}
  @Override public Bundle call(String method,String arg,Bundle extras){if(Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException("仅应用可管理更新");AppUpdateManager m=manager();switch(method){case "check":m.check(false,null);break;case "download":m.download();break;case "cancel":m.cancel();break;case "settings":m.settings(extras);break;case "verify":Bundle result=new Bundle();result.putLong("requestedSerial",m.verify());return result;case "status":m.refresh(null);break;default:throw new IllegalArgumentException("未知更新操作");}return m.snapshot();}
  File resolve(Uri uri)throws FileNotFoundException {AppUpdateManager m=manager();File file=m.file();if(uri.getPathSegments().size()!=1||!uri.getLastPathSegment().equals(file.getName())||!"ready".equals(m.snapshot().getString("state"))||!file.isFile())throw new FileNotFoundException("更新文件尚未核验或已移除");return file;}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {if(!"r".equals(mode))throw new FileNotFoundException("更新文件只允许读取");return ParcelFileDescriptor.open(resolve(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
  public String getType(Uri uri){return "application/vnd.android.package-archive";}
  public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){try{File file=resolve(uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor row=new MatrixCursor(cols);Object[] values=new Object[cols.length];for(int i=0;i<cols.length;i++)values[i]=OpenableColumns.DISPLAY_NAME.equals(cols[i])?"元婴期院士更新.apk":OpenableColumns.SIZE.equals(cols[i])?file.length():null;row.addRow(values);return row;}catch(FileNotFoundException e){return null;}}
  public Uri insert(Uri uri,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri uri,ContentValues v,String s,String[] args){throw new UnsupportedOperationException();}public int delete(Uri uri,String s,String[] args){throw new UnsupportedOperationException();}
}
