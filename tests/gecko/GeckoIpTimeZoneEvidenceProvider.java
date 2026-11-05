package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;

/** UID2000-only explicit scope setup and bounded synthetic evidence; no arbitrary paths. */
public final class GeckoIpTimeZoneEvidenceProvider extends ContentProvider {
  public boolean onCreate(){if(getContext()==null)throw new SecurityException("Fixture context absent");IpTimeZoneFixtureScopes.integration(getContext());return true;}
  private void shell(){if(Binder.getCallingUid()!=2000)throw new SecurityException("Shell fixture owner only");}
  @Override public Bundle call(String method,String arg,Bundle extras){
    shell();if(extras==null||extras.size()!=2||!extras.containsKey("sourceCommit")||!extras.containsKey("runNonce")||arg!=null)throw new SecurityException("Exact fixture invocation required");String source=extras.getString("sourceCommit"),nonce=extras.getString("runNonce");
    try{Bundle value=new Bundle();if("prepare".equals(method))value.putString("status",IpTimeZoneFixtureScopes.prepareIp(getContext(),source,nonce).getString("status"));
      else if("clear".equals(method)){IpTimeZoneFixtureScopes.clear(getContext(),source,nonce);value.putString("status","cleared");}else throw new SecurityException("Unknown fixture command");return value;
    }catch(RuntimeException error){throw error;}catch(Exception error){throw new IllegalStateException("Explicit fixture scope operation failed",error);}
  }
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    shell();if(!"r".equals(mode)||uri.getQuery()!=null||uri.getFragment()!=null)throw new SecurityException("Read-only fixed fixture reports");
    String name;if("/report".equals(uri.getPath()))name="gecko-ip-timezone-results.json";else if("/setup".equals(uri.getPath()))name=IpTimeZoneFixtureScopes.SETUP;else throw new FileNotFoundException("Unknown fixture report");
    File target="/setup".equals(uri.getPath())?IpTimeZoneFixtureScopes.file(getContext(),name):new File(Profiles.global(getContext()).getFilesDir(),name);
    if(java.nio.file.Files.isSymbolicLink(target.toPath())||!target.isFile()||target.length()>4*1024*1024)throw new FileNotFoundException("Bounded fixture report absent");return ParcelFileDescriptor.open(target,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}
  public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
  public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
  public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
