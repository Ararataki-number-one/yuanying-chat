package local.pocketchat;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;

/** Read-only access to one explicitly granted saved file; never exposes profile records. */
public class SavedDownloadProvider extends ContentProvider {
  public boolean onCreate(){return true;}
  static File resolve(Context c,Uri uri)throws IOException {
    List<String> path=uri.getPathSegments();if(path.size()!=3||!path.get(0).matches("[0-7]")||!path.get(1).matches("[a-f0-9-]{36}")||!path.get(2).equals(FileDownloads.safeName(path.get(2)))||path.get(2).equals(".")||path.get(2).equals("..")||path.get(2).equals("payload.part"))throw new FileNotFoundException("文件地址无效");File base=new File(Profiles.context(c,Integer.parseInt(path.get(0))).getFilesDir(),"saved-downloads").getCanonicalFile();File file=new File(new File(base,path.get(1)),path.get(2)).getCanonicalFile();if(!file.getPath().startsWith(base.getPath()+File.separator))throw new FileNotFoundException();return file;
  }
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {if(!"r".equals(mode))throw new FileNotFoundException("只允许读取已保存文件");try{File f=resolve(getContext(),uri);return ParcelFileDescriptor.open(f,ParcelFileDescriptor.MODE_READ_ONLY);}catch(IOException e){throw new FileNotFoundException("已保存文件不存在");}}
  public String getType(Uri uri){try{return FileDownloads.type(resolve(getContext(),uri).getName(),null);}catch(IOException e){return "application/octet-stream";}}
  public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){try{File file=resolve(getContext(),uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor row=new MatrixCursor(cols);Object[] values=new Object[cols.length];for(int i=0;i<cols.length;i++)values[i]=cols[i].equals(OpenableColumns.DISPLAY_NAME)?file.getName():cols[i].equals(OpenableColumns.SIZE)?file.length():null;row.addRow(values);return row;}catch(IOException e){return null;}}
  public Uri insert(Uri uri,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri uri,ContentValues v,String s,String[] args){throw new UnsupportedOperationException();}public int delete(Uri uri,String s,String[] args){throw new UnsupportedOperationException();}
}
