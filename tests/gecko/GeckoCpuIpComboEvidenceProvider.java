package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import java.io.*;

/** The same exact fresh-profile allocator; only shell-owned bounded evidence. */
public final class GeckoCpuIpComboEvidenceProvider extends ContentProvider {
  public boolean onCreate(){if(getContext()==null)throw new SecurityException("Fixture context absent");IpTimeZoneFixtureScopes.integration(getContext());return true;}
  private void shell(){if(Binder.getCallingUid()!=2000)throw new SecurityException("Shell fixture owner only");}
  @Override public Bundle call(String method,String arg,Bundle extras){
    shell();if(arg!=null||extras==null||extras.size()!=2||!extras.containsKey("sourceCommit")||!extras.containsKey("runNonce"))throw new SecurityException("Exact combined invocation required");
    String source=extras.getString("sourceCommit"),nonce=extras.getString("runNonce");try{Bundle result=new Bundle();
      if("prepare".equals(method))result.putString("status",IpTimeZoneFixtureScopes.prepareIp(getContext(),source,nonce).getString("status"));
      else if("clear".equals(method)){IpTimeZoneFixtureScopes.clear(getContext(),source,nonce);result.putString("status","cleared");}
      else throw new SecurityException("Unknown combined command");return result;
    }catch(RuntimeException error){throw error;}catch(Exception error){throw new IllegalStateException("Combined scope operation failed",error);}
  }
  public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
    shell();if(!"r".equals(mode)||uri.getQuery()!=null||uri.getFragment()!=null)throw new SecurityException("Fixed read-only combined reports");
    File file;if("/report".equals(uri.getPath()))file=new File(Profiles.global(getContext()).getFilesDir(),GeckoCpuIpComboIntegrationActivity.FILE);
    else if("/setup".equals(uri.getPath()))file=IpTimeZoneFixtureScopes.file(getContext(),IpTimeZoneFixtureScopes.SETUP);else throw new FileNotFoundException("Unknown combined report");
    if(java.nio.file.Files.isSymbolicLink(file.toPath())||!file.isFile()||file.length()>524288)throw new FileNotFoundException("Bounded combined report absent");return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
  }
  public String getType(Uri uri){return "application/json";}
  public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
  public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
  public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
  public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
