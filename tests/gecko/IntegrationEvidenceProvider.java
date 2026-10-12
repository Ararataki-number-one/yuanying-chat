package local.pocketchat;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/** Shell-only export of two synthetic reports from the non-debuggable test APK. */
public final class IntegrationEvidenceProvider extends ContentProvider {
  @Override public boolean onCreate(){
    if(getContext()==null||!getContext().getPackageName().equals("local.pocketchat.test"))throw new SecurityException("Integration package only");
    return true;
  }
  @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000)throw new SecurityException("Read-only shell evidence");
    String name;
    if("/native-probe".equals(uri.getPath()))name="native-probe-results.json";
    else if("/gecko-pool".equals(uri.getPath()))name="gecko-pool-results.json";
    else throw new FileNotFoundException("Unknown synthetic report");
    try{
      File base=getContext().getFilesDir().getCanonicalFile(),file=new File(base,name).getCanonicalFile();
      if(!base.equals(file.getParentFile())||!file.isFile()||file.length()>2*1024*1024)throw new FileNotFoundException("Synthetic report unavailable");
      return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
    }catch(IOException failure){throw new FileNotFoundException("Synthetic report unavailable");}
  }
  @Override public String getType(Uri uri){return "application/json";}
  @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){throw new UnsupportedOperationException();}
  @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
  @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
  @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
