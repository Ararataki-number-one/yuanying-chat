package local.pocketchat;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;

/** SAF/cloud document URIs are streams, not filesystem paths usable by Gecko. */
final class GeckoUploadFiles {
  static final long MAX=512L*1024*1024;
  static final class Selection {
    final File directory;final Uri[] files;
    Selection(File directory,Uri[] files){this.directory=directory;this.files=files;}
    void delete(){File[] children=directory.listFiles();if(children!=null)for(File child:children)child.delete();directory.delete();}
  }
  static Selection prepare(Context context,Uri[] source)throws IOException {
    File parent=new File(context.getCacheDir(),"gecko-uploads"),directory=new File(parent,UUID.randomUUID().toString());
    if(!directory.mkdirs())throw new IOException("无法准备附件，请检查剩余空间");
    Selection selection=new Selection(directory,new Uri[source.length]);long total=0;Set<String> names=new HashSet<>();
    try{for(int i=0;i<source.length;i++){
      Uri uri=source[i];if(uri==null||!("content".equals(uri.getScheme())||"file".equals(uri.getScheme())))throw new IOException("所选附件不可读取，请重新选择");
      String name="附件";
      if("file".equals(uri.getScheme()))name=new File(uri.getPath()).getName();
      else try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst()&&!cursor.isNull(0))name=cursor.getString(0);}
      name=name.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_").trim();if(name.isEmpty()||name.equals(".")||name.equals(".."))name="附件";if(name.length()>80)name=name.substring(name.length()-80);
      if(!names.add(name))throw new IOException("所选附件名称重复，请分别添加");
      File file=new File(directory,name);
      try(InputStream input=context.getContentResolver().openInputStream(uri);OutputStream output=new FileOutputStream(file)){
        if(input==null)throw new IOException("附件不可读取，请重新选择");byte[] buffer=new byte[65536];int count;
        while((count=input.read(buffer))!=-1){total+=count;if(total>MAX||directory.getUsableSpace()<64L*1024*1024)throw new IOException("附件过大或剩余空间不足");output.write(buffer,0,count);}
      }
      selection.files[i]=Uri.fromFile(file);
    }return selection;}catch(Exception error){selection.delete();throw new IOException("读取附件失败："+(error.getMessage()==null?"请重新选择":error.getMessage()),error);}
  }
}
