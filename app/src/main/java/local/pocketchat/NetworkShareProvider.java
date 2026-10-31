package local.pocketchat;

import android.content.*;import android.database.*;import android.net.Uri;import android.os.ParcelFileDescriptor;import android.provider.OpenableColumns;
import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;

/** One granted temporary file; no access to environment directories or encrypted stores. */
public final class NetworkShareProvider extends ContentProvider {
  static File directory(Context c){return new File(Profiles.context(c,0).getCacheDir(),"network-shares");}
  static Uri create(Context c,String text)throws Exception{
    byte[] bytes=text.getBytes(StandardCharsets.UTF_8);if(bytes.length>NetworkShareCodec.LIMIT)throw new IOException("分享配置过大");File root=directory(c);if(!root.isDirectory()&&!root.mkdirs())throw new IOException("暂时无法准备分享文件");
    File[] all=root.listFiles();long now=System.currentTimeMillis();if(all!=null)for(File f:all)if(now-f.lastModified()>24*60*60*1000L)f.delete();
    File file=new File(root,UUID.randomUUID()+".pocketnet"),pending=new File(root,file.getName()+".pending");boolean published=false;
    try{try(FileOutputStream out=new FileOutputStream(pending)){out.write(bytes);out.getFD().sync();}if(!pending.renameTo(file))throw new IOException("分享文件未生成");published=true;
      return new Uri.Builder().scheme("content").authority(c.getPackageName()+".network-shares").appendPath(file.getName()).build();
    }finally{if(!published){pending.delete();file.delete();}}
  }
  static File resolve(Context c,Uri uri)throws IOException{
    if(!"content".equals(uri.getScheme())||!(c.getPackageName()+".network-shares").equals(uri.getAuthority())||uri.getPathSegments().size()!=1||!uri.getLastPathSegment().matches("[0-9a-f-]{36}\\.pocketnet"))throw new FileNotFoundException();
    File root=directory(c).getCanonicalFile(),file=new File(root,uri.getLastPathSegment()).getCanonicalFile();if(!root.equals(file.getParentFile())||!file.isFile()||System.currentTimeMillis()-file.lastModified()>24*60*60*1000L)throw new FileNotFoundException("分享文件已过期，请重新分享");return file;
  }
  public boolean onCreate(){return true;}
  public String getType(Uri uri){return NetworkShareCodec.MIME;}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(!"r".equals(mode))throw new FileNotFoundException("只读分享");try{return ParcelFileDescriptor.open(resolve(getContext(),uri),ParcelFileDescriptor.MODE_READ_ONLY);}catch(IOException e){throw new FileNotFoundException("分享文件不可用");}}
  public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){try{File f=resolve(getContext(),uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor cursor=new MatrixCursor(columns);Object[] row=new Object[columns.length];for(int i=0;i<columns.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(columns[i])?f.getName():OpenableColumns.SIZE.equals(columns[i])?f.length():null;cursor.addRow(row);return cursor;}catch(IOException e){return null;}}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
