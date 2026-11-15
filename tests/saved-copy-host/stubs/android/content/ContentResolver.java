package android.content;
import android.net.Uri;import android.database.Cursor;import java.io.*;
/** A controlled stream provider; metadata/deletion workflows are not emulated. */
public abstract class ContentResolver {
  public abstract InputStream openInputStream(Uri uri)throws IOException;
  public abstract OutputStream openOutputStream(Uri uri,String mode)throws IOException;
  public abstract int delete(Uri uri,String where,String[] args);
  public Cursor query(Uri uri,String[] columns,String where,String[] args,String order){throw new AssertionError("Metadata query outside copy host");}
}
