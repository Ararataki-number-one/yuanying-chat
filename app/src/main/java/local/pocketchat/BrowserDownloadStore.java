package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import java.io.*;
import java.util.UUID;
import org.json.*;

/** Browser destinations publish into the shared saved-file library, with no second index. */
final class BrowserDownloadStore {
  static final class Unconfirmed extends IOException {Unconfirmed(Throwable cause){super("保存结果待确认，请在下载中心核对",cause);}}
  final Context context;
  BrowserDownloadStore(Context context){this.context=context.getApplicationContext();}
  String directory(){return "Download/元婴期浏览器/窗口_"+(Profiles.slot(context)+1)+"/";}
  static String safeName(String value){String clean=(value==null?"文件":value).replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_").trim();if(clean.isEmpty()||clean.equals(".")||clean.equals("..")||clean.equals("payload.part"))clean="文件";if(clean.length()>160){int end=160;if(Character.isHighSurrogate(clean.charAt(end-1)))--end;clean=clean.substring(0,end);}return clean;}
  static final class Target {
    final Context context;final Uri uri;final String name,location;final File file,part;
    Target(Context c,Uri uri,String name,String location,File file){context=c;this.uri=uri;this.name=name;this.location=location;this.file=file;part=file==null?null:new File(file.getParentFile(),"payload.part");}
    OutputStream output()throws IOException {if(file!=null)return new FileOutputStream(part);OutputStream out=context.getContentResolver().openOutputStream(uri,"w");if(out==null)throw new IOException("下载目录无法写入");return out;}
    void publish()throws IOException {if(file!=null){if(!part.renameTo(file))throw new IOException("文件保存失败");}else{ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.IS_PENDING,0);if(context.getContentResolver().update(uri,values,null,null)!=1)throw new IOException("文件保存未确认");}}
    void abort(){try{if(file!=null){part.delete();file.delete();file.getParentFile().delete();}else context.getContentResolver().delete(uri,null,null);}catch(RuntimeException ignored){}}
  }
  Target create(String requested,String mime)throws IOException {
    String name=safeName(requested);
    if(Build.VERSION.SDK_INT>=29){
      ContentValues values=new ContentValues();values.put(MediaStore.MediaColumns.DISPLAY_NAME,name);values.put(MediaStore.MediaColumns.MIME_TYPE,mime);values.put(MediaStore.MediaColumns.RELATIVE_PATH,directory());values.put(MediaStore.MediaColumns.IS_PENDING,1);
      Uri uri=context.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException("下载目录不可用");
      try(Cursor row=context.getContentResolver().query(uri,new String[]{MediaStore.MediaColumns.DISPLAY_NAME},null,null,null)){if(row!=null&&row.moveToFirst())name=row.getString(0);}catch(RuntimeException ignored){}
      return new Target(context,uri,name,directory()+name,null);
    }
    String id=UUID.randomUUID().toString();File folder=new File(context.getFilesDir(),"saved-downloads/"+id);if(!folder.mkdirs())throw new IOException("应用下载目录无法创建");
    Uri uri=new Uri.Builder().scheme("content").authority(context.getPackageName()+".saved-downloads").appendPath(String.valueOf(Profiles.slot(context))).appendPath(id).appendPath(name).build();
    return new Target(context,uri,name,"浏览器应用内下载/"+name,new File(folder,name));
  }
  JSONObject save(BrowserDownloadTransfer.Result result,String requested,java.util.function.BooleanSupplier valid)throws IOException {
    Target target=create(requested,result.mime);boolean[] entered={false};
    try{return SavedFileDeletion.lease(context,target.uri,()->{entered[0]=true;return saveOwned(target,result,valid);});}
    catch(IOException failed){throw failed;}
    catch(Exception failed){throw new IOException("下载保存未完成，请在下载中心核对",failed);}
    finally{if(!entered[0])target.abort();}
  }
  /** Caller retains the same URI publication lease through library confirmation or rollback. */
  JSONObject saveOwned(Target target,BrowserDownloadTransfer.Result result,java.util.function.BooleanSupplier valid)throws Exception {
    DownloadLibrary library=null;JSONObject row=new JSONObject();boolean indexAttempted=false;
    try{
      library=DownloadLibrary.get(context);
      JSONObject environment=ProfileCatalog.get(context).item(Profiles.slot(context));
      row.put("slot",Profiles.slot(context));row.put("id",UUID.randomUUID().toString());row.put("state","saved");row.put("name",target.name);row.put("mime",result.mime);row.put("uri",target.uri.toString());row.put("location",target.location);
      row.put("environmentId",environment.optString("environmentId"));row.put("environmentGeneration",environment.optInt("generation"));row.put("environmentName",environment.optString("name"));
      long bytes=0;try(InputStream in=new FileInputStream(result.file);OutputStream out=target.output()){byte[] buffer=new byte[65536];int count;while((count=in.read(buffer))!=-1){if(!valid.getAsBoolean())throw new IOException("下载已取消或连接已变化，文件未保存");out.write(buffer,0,count);bytes+=count;}if(out instanceof FileOutputStream)((FileOutputStream)out).getFD().sync();}
      if(bytes!=result.bytes||!valid.getAsBoolean())throw new IOException("文件保存未完成");target.publish();if(!valid.getAsBoolean())throw new IOException("文件保存已取消");
      row.put("time",library.publicationTime(target.uri));row.put("actualName",target.name);row.put("actualMime",result.mime);DownloadMetadataValues.checked(row,bytes,"published-copy","known");
      indexAttempted=true;library.add(context,row);JSONObject saved=library.saved(row);
      if(saved==null||DownloadMetadataValues.bytes(saved)!=bytes)throw new IOException("下载索引未能确认，文件未保存");
      if(!valid.getAsBoolean())throw new IOException("文件保存已取消");return saved;
    }catch(Exception failure){
      try{
        if(!indexAttempted)target.abort();
        else{JSONObject saved=library.saved(row);if(saved!=null)SavedFileDeletion.remove(context,saved);else if(!library.indexed(target.uri))target.abort();}
      }catch(Exception cleanup){IOException uncertain=new Unconfirmed(failure);uncertain.addSuppressed(cleanup);throw uncertain;}
      throw failure;
    }
  }
  JSONArray rows(){
    JSONArray selected=new JSONArray(),saved=DownloadLibrary.get(context).list();int slot=Profiles.slot(context);
    for(int i=0;i<saved.length();i++){JSONObject row=saved.optJSONObject(i);if(row!=null&&row.optInt("slot",-1)==slot)selected.put(row);}
    return selected;
  }
}
