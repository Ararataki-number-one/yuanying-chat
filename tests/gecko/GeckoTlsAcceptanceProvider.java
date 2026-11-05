package local.pocketchat;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;
/** Shell-only fixed reports and explicit manual-system fixture preparation. */
public final class GeckoTlsAcceptanceProvider extends ContentProvider {
  public boolean onCreate(){return getContext()!=null&&"local.pocketchat.test".equals(getContext().getPackageName());}
  @Override public Bundle call(String method,String arg,Bundle extras){
    if(Binder.getCallingUid()!=2000||arg!=null||extras==null||extras.size()!=4||!extras.keySet().equals(new java.util.HashSet<>(java.util.Arrays.asList("sourceCommit","runNonce","slot","purpose"))))throw new SecurityException("Exact shell manual TLS scope required");
    for(String key:new String[]{"sourceCommit","runNonce","purpose"})if(!(extras.get(key) instanceof String))throw new SecurityException("Typed TLS scope");
    if(!(extras.get("slot") instanceof Integer))throw new SecurityException("Typed TLS slot");
    try{String source=extras.getString("sourceCommit"),run=extras.getString("runNonce"),purpose=extras.getString("purpose");int slot=extras.getInt("slot");Bundle result=new Bundle();
      if("prepare".equals(method)){org.json.JSONObject proof=GeckoTlsFixtureScopes.prepareManual(getContext(),source,run,slot,purpose);result.putString("status","armed");result.putString("claimNonce",proof.getString("claimNonce"));}
      else if("inspect".equals(method)){org.json.JSONObject proof=GeckoTlsFixtureScopes.inspectManual(getContext(),source,run,slot,purpose);result.putString("status","armed");result.putString("claimNonce",proof.getString("claimNonce"));}
      else if("clear".equals(method)){GeckoTlsFixtureScopes.clearManual(getContext(),source,run,slot,purpose);result.putString("status","cleared");}
      else throw new SecurityException("Unknown TLS scope action");return result;
    }catch(RuntimeException error){throw error;}catch(Exception error){throw new IllegalStateException("Manual TLS scope failed",error);}
  }
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000||getContext()==null||!"local.pocketchat.test".equals(getContext().getPackageName()))throw new SecurityException("ShellIntegrationReadOnly");
    if(uri.getQuery()!=null||uri.getFragment()!=null)throw new SecurityException("Fixed TLS path");
    String path=uri.getPath();if(path==null||!path.matches("/report/[0-9a-f]{32}/[12]"))throw new FileNotFoundException("UnknownCase");
    int slot=path.charAt(path.length()-1)-'0';String nonce=path.substring(8,40);File file=new File(Profiles.context(getContext(),slot).getFilesDir(),"tls-acceptance-"+nonce+".json");
    if(!file.isFile()||java.nio.file.Files.isSymbolicLink(file.toPath())||file.length()>262144)throw new FileNotFoundException("ReportUnavailable");
    return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
