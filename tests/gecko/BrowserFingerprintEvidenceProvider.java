package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;

/** Shell-only bounded synthetic metadata; no screenshots, cookies or arbitrary file paths. */
public final class BrowserFingerprintEvidenceProvider extends ContentProvider {
  public boolean onCreate(){if(getContext()==null||!"local.pocketchat.test".equals(getContext().getPackageName()))throw new SecurityException("Integration package only");return true;}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000)throw new SecurityException("Read-only shell evidence");
    String name="/chromium".equals(uri.getPath())?"browser-fingerprint-chromium.json":"/gecko".equals(uri.getPath())?"browser-fingerprint-gecko.json":null;
    if(name==null)throw new FileNotFoundException("Unknown synthetic evidence");File file=new File(getContext().getFilesDir(),name);
    if(!file.isFile()||file.length()>1024*1024)throw new FileNotFoundException("Synthetic report unavailable");
    return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}
  public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
  public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
  public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
