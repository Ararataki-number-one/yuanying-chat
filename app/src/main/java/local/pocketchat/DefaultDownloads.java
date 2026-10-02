package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import org.json.*;
import java.io.*;
import java.util.*;

/** App-owned default destinations. Existing names are never overwritten. */
final class DefaultDownloads {
  static String directory(Context c){return Environment.DIRECTORY_DOWNLOADS+"/元婴期院士/窗口_"+(Profiles.slot(c)+1)+"/";}
  static String description(Context c){return Build.VERSION.SDK_INT>=29?directory(c):"应用内文件/窗口_"+(Profiles.slot(c)+1)+"（可在下载页打开、分享或另存为）";}
  static final class Target {
    final Context c;final Uri uri;final String name,location;final File file,part;
    Target(Context c,Uri uri,String name,String location,File file){this.c=c;this.uri=uri;this.name=name;this.location=location;this.file=file;part=file==null?null:new File(file.getParentFile(),"payload.part");}
    OutputStream output()throws IOException{if(file!=null)return new FileOutputStream(part);OutputStream out=c.getContentResolver().openOutputStream(uri,"w");if(out==null)throw new IOException("默认下载目录无法写入");return out;}
    void publish()throws IOException{if(file!=null){if(!part.renameTo(file))throw new IOException("文件保存失败");return;}ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.IS_PENDING,0);if(c.getContentResolver().update(uri,values,null,null)!=1)throw new IOException("文件保存确认失败");}
    void abort(){try{if(file!=null){part.delete();file.delete();file.getParentFile().delete();}else c.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}}
  }
  static Target create(Context c,String name,String mime)throws IOException {
    if(Build.VERSION.SDK_INT<29)return local(c,name);
    String actual=uniqueName(c,name);ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.DISPLAY_NAME,actual);values.put(MediaStore.MediaColumns.MIME_TYPE,mime);values.put(MediaStore.MediaColumns.RELATIVE_PATH,directory(c));values.put(MediaStore.MediaColumns.IS_PENDING,1);Uri uri=c.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException("默认下载目录不可用，可在下载管理中另存为");try(Cursor row=c.getContentResolver().query(uri,new String[]{MediaStore.MediaColumns.DISPLAY_NAME},null,null,null)){if(row!=null&&row.moveToFirst())actual=row.getString(0);}catch(Exception ignored){}return new Target(c,uri,actual,directory(c)+actual,null);
  }
  static String uniqueName(Context c,String name)throws IOException {String clean=FileDownloads.safeName(name);int dot=clean.lastIndexOf('.');String base=dot>0?clean.substring(0,dot):clean,ext=dot>0?clean.substring(dot):"";for(int i=0;i<10000;i++){String candidate=i==0?clean:base+" ("+i+")"+ext;try(Cursor row=c.getContentResolver().query(MediaStore.Downloads.EXTERNAL_CONTENT_URI,new String[]{MediaStore.MediaColumns._ID},MediaStore.MediaColumns.RELATIVE_PATH+"=? AND "+MediaStore.MediaColumns.DISPLAY_NAME+"=?",new String[]{directory(c),candidate},null)){if(row==null)throw new IOException("无法确认默认文件名");if(!row.moveToFirst())return candidate;}}throw new IOException("同名文件过多，请在下载管理中另存为");}
  static Target local(Context c,String name)throws IOException {
    String clean=FileDownloads.safeName(name);if(clean.equals(".")||clean.equals("..")||clean.equals("payload.part"))clean="文件_"+clean.replace('.','_');String id=UUID.randomUUID().toString();File folder=new File(c.getFilesDir(),"saved-downloads/"+id);if(!folder.mkdirs())throw new IOException("应用文件目录无法创建");Uri uri=new Uri.Builder().scheme("content").authority(c.getPackageName()+".saved-downloads").appendPath(String.valueOf(Profiles.slot(c))).appendPath(id).appendPath(clean).build();return new Target(c,uri,clean,"应用内文件/窗口_"+(Profiles.slot(c)+1)+"/"+clean,new File(folder,clean));
  }
  static void recover(Context c,JSONObject task){String pending=task.optString("pendingDestination");if(pending.isEmpty())return;boolean saved=false;Uri uri=Uri.parse(pending);try{
    if(Build.VERSION.SDK_INT>=29&&"media".equals(uri.getAuthority())){try(Cursor row=c.getContentResolver().query(uri,new String[]{MediaStore.MediaColumns.IS_PENDING,MediaStore.MediaColumns.RELATIVE_PATH,MediaStore.MediaColumns.OWNER_PACKAGE_NAME},null,null,null)){if(row!=null&&row.moveToFirst()&&directory(c).equals(row.getString(1))&&c.getPackageName().equals(row.getString(2))){saved=row.getInt(0)==0;if(!saved)c.getContentResolver().delete(uri,null,null);}}}
    else if((c.getPackageName()+".saved-downloads").equals(uri.getAuthority())){File file=SavedDownloadProvider.resolve(c,uri);if(uri.getPathSegments().get(0).equals(String.valueOf(Profiles.slot(c)))){saved=file.isFile();if(!saved){new File(file.getParentFile(),"payload.part").delete();file.getParentFile().delete();}}}
    if(saved)DownloadTasks.put(task,"state","saved","reason","","uri",pending,"location",task.optString("pendingLocation"),"name",task.optString("pendingName",task.optString("name","文件")));
  }catch(Exception ignored){}task.remove("pendingDestination");task.remove("pendingLocation");task.remove("pendingName");}
}
