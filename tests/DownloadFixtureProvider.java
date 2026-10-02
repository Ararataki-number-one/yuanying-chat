package local.pocketchat;
import android.content.*;import android.database.*;import android.net.Uri;import android.os.*;import android.provider.OpenableColumns;import java.io.*;
public class DownloadFixtureProvider extends ContentProvider {
 public boolean onCreate(){return true;}
 File target(Uri u)throws FileNotFoundException{String n=u.getLastPathSegment();if(n==null||!n.matches("sample[0-9]*\\.(docx|pdf|png|jpg|webp)"))throw new FileNotFoundException();return new File(getContext().getCacheDir(),n);}
 public String getType(Uri u){if(u.getPath().endsWith(".png"))return "image/png";return u.getPath().endsWith(".pdf")?"application/pdf":"application/vnd.openxmlformats-officedocument.wordprocessingml.document";}
 public ParcelFileDescriptor openFile(Uri u,String mode)throws FileNotFoundException{return ParcelFileDescriptor.open(target(u),mode.contains("w")?ParcelFileDescriptor.MODE_READ_WRITE|ParcelFileDescriptor.MODE_CREATE|ParcelFileDescriptor.MODE_TRUNCATE:ParcelFileDescriptor.MODE_READ_ONLY);}
 public Cursor query(Uri u,String[] p,String s,String[] a,String o){MatrixCursor c=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});try{File f=target(u);c.addRow(new Object[]{f.getName(),f.length()});}catch(Exception ignored){}return c;}
 public Uri insert(Uri u,ContentValues v){return null;}public int update(Uri u,ContentValues v,String s,String[] a){return 0;}public int delete(Uri u,String s,String[] a){return 0;}
}
