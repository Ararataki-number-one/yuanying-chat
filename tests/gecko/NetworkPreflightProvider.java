package local.pocketchat;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Binder;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.util.AtomicFile;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only, separate-process CM observation. Creates no browser or service. */
public final class NetworkPreflightProvider extends ContentProvider {
  @Override public boolean onCreate() {
    if(getContext()==null||!"local.pocketchat.test".equals(getContext().getPackageName()))
      throw new SecurityException("Integration package only");
    return true;
  }
  @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000)
      throw new SecurityException("Read-only shell preflight");
    String nonce=uri.getQueryParameter("runNonce");
    if(!"/default-network".equals(uri.getPath())||nonce==null||!nonce.matches("[0-9a-f]{32}")
        ||uri.getQueryParameters("runNonce").size()!=1||uri.getQueryParameterNames().size()!=1)
      throw new FileNotFoundException("Exact preflight invocation required");
    try {
      JSONObject identity=IntegrationBuildIdentity.read(getContext());
      ConnectivityManager cm=getContext().getSystemService(ConnectivityManager.class);
      if(cm==null)throw new IllegalStateException("Actual ConnectivityManager unavailable");
      Network network=cm.getActiveNetwork();
      NetworkCapabilities caps=network==null?null:cm.getNetworkCapabilities(network);
      Network after=cm.getActiveNetwork();
      boolean stable=network!=null&&network.equals(after);
      boolean internet=caps!=null&&caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
      JSONArray transports=new JSONArray();
      if(caps!=null){
        if(caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))transports.put("wifi");
        if(caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))transports.put("ethernet");
        if(caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))transports.put("cellular");
        if(caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN))transports.put("vpn");
      }
      JSONObject report=J.obj("schema",1,"runNonce",nonce,"sourceCommit",identity.getString("sourceCommit"),
          "buildIdentity",identity,"actualAndroidExecution",true,"actualConnectivityManagerExecution",true,
          "actualGeckoExecution",false,"applicationAcceptance",false,"physicalPhoneAcceptance",false,
          "androidSdk",android.os.Build.VERSION.SDK_INT,"pid",android.os.Process.myPid(),
          "observedAtElapsedRealtime",SystemClock.elapsedRealtime(),"activeNetwork",network==null?"":network.toString(),
          "activeNetworkAfter",after==null?"":after.toString(),"capabilitiesPresent",caps!=null,
          "internetCapability",internet,"stableDuringRead",stable,"usable",stable&&internet,
          "transports",transports,"capabilities",caps==null?"":caps.toString(),
          "scope","Actual CM environment prerequisite only; no browser, proxy, website or application acceptance");
      File file=new File(getContext().getFilesDir(),"network-preflight.json");
      AtomicFile atomic=new AtomicFile(file);FileOutputStream out=null;
      try{out=atomic.startWrite();out.write((report.toString()+"\n").getBytes(StandardCharsets.UTF_8));atomic.finishWrite(out);}
      catch(Exception failure){if(out!=null)atomic.failWrite(out);throw failure;}
      return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
    }catch(Exception failure){
      FileNotFoundException missing=new FileNotFoundException("Actual network preflight unavailable: "+failure);
      missing.initCause(failure);throw missing;
    }
  }
  @Override public String getType(Uri uri){return "application/json";}
  @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){throw new UnsupportedOperationException();}
  @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
  @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
  @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
