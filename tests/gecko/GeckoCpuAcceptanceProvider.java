package local.pocketchat;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;
/** Read-only fixed CPU acceptance reports from integration profile1/profile2. */
public final class GeckoCpuAcceptanceProvider extends ContentProvider {
  public boolean onCreate(){return getContext()!=null&&"local.pocketchat.test".equals(getContext().getPackageName());}
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000||getContext()==null||!"local.pocketchat.test".equals(getContext().getPackageName()))throw new SecurityException("Shell integration read only");
    String path=uri.getPath();if(path==null||!path.matches("/report/[0-9a-f]{32}/[12]"))throw new FileNotFoundException("Unknown workload");
    int slot=path.charAt(path.length()-1)-'0';String nonce=path.substring(8,40);
    File file=new File(Profiles.context(getContext(),slot).getFilesDir(),"cpu-acceptance-"+nonce+".json");
    if(!file.isFile()||file.length()>262144)throw new FileNotFoundException("Report unavailable");
    return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}
  public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
  public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
  public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
