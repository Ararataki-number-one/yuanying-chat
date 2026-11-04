package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;

/** Integration-only, shell-only export of the bounded synthetic browser result. */
public final class BrowserEvidenceProvider extends ContentProvider {
  public boolean onCreate(){if(getContext()==null||!"local.pocketchat.test".equals(getContext().getPackageName()))throw new SecurityException("Integration package only");return true;}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000)throw new SecurityException("Read-only shell evidence");
    if(!"/result".equals(uri.getPath()))throw new FileNotFoundException("Unknown synthetic report");
    File file=new File(getContext().getFilesDir(),"browser-integration-results.json");if(!file.isFile()||file.length()>2*1024*1024)throw new FileNotFoundException("Synthetic report unavailable");
    return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}
  public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
  public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
  public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
