package local.pocketchat;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;
/** SAF-like document with no filesystem _data column. Synthetic test data only. */
public class GeckoUploadFixtureProvider extends ContentProvider {
 public boolean onCreate(){return true;}
 public String getType(Uri uri){return "text/plain";}
 public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){MatrixCursor result=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});result.addRow(new Object[]{"sample.txt",16});return result;}
 public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {try{ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createPipe();new Thread(()->{try(OutputStream out=new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])){out.write("synthetic-upload".getBytes(java.nio.charset.StandardCharsets.UTF_8));}catch(IOException ignored){}},"fixture-document").start();return pipe[0];}catch(IOException error){throw new FileNotFoundException(error.getMessage());}}
 public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
 public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
 public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
}
