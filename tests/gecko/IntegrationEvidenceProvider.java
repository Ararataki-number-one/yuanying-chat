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

/** Shell-only export of bounded synthetic reports/events from the non-debuggable test APK. */
public final class IntegrationEvidenceProvider extends ContentProvider {
  @Override public boolean onCreate(){
    if(getContext()==null||!getContext().getPackageName().equals("local.pocketchat.test"))throw new SecurityException("Integration package only");
    return true;
  }
  @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {
    if(!"r".equals(mode)||Binder.getCallingUid()!=2000)throw new SecurityException("Read-only shell evidence");
    if(uri.getPath()!=null&&uri.getPath().startsWith("/gecko-events/")){
      java.util.List<String> parts=uri.getPathSegments();
      if(parts.size()!=4||!parts.get(1).matches("[0-7]")||!parts.get(2).matches("[0-9a-f]{32}")||!parts.get(3).matches("[1-9][0-9]{0,3}"))throw new FileNotFoundException("Invalid synthetic event path");
      try{
        File event=IntegrationEventStore.file(getContext(),Integer.parseInt(parts.get(1)),parts.get(2),Integer.parseInt(parts.get(3)));
        if(!event.isFile()||event.length()<=0||event.length()>IntegrationEventStore.MAX_BYTES)throw new FileNotFoundException("Synthetic event unavailable");
        return ParcelFileDescriptor.open(event,ParcelFileDescriptor.MODE_READ_ONLY);
      }catch(IOException failure){throw new FileNotFoundException("Synthetic event unavailable");}
    }
    String name;
    if("/build-identity".equals(uri.getPath())){
      name="integration-build-identity.json";
      try{
        android.util.AtomicFile identity=new android.util.AtomicFile(new File(getContext().getFilesDir(),name));
        java.io.FileOutputStream out=null;
        try{out=identity.startWrite();out.write((IntegrationBuildIdentity.read(getContext()).toString()+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));identity.finishWrite(out);}
        catch(Exception failure){if(out!=null)identity.failWrite(out);throw failure;}
      }catch(Exception failure){throw new FileNotFoundException("Installed synthetic build identity unavailable");}
    }
    else if("/environment-spec".equals(uri.getPath()))name="environment-spec-results.json";
    else if("/environment-intent".equals(uri.getPath()))name="environment-intent-results.json";
    else if("/resource-pressure".equals(uri.getPath()))name="resource-pressure-results.json";
    else if("/gecko-template".equals(uri.getPath()))name="gecko-template-results.json";
    else if("/gecko-identity-prototype".equals(uri.getPath()))name="gecko-identity-prototype-results.json";
    else if("/network-protection".equals(uri.getPath()))name="network-protection-results.json";
    else if("/extension-upgrade".equals(uri.getPath()))name="extension-upgrade-results.json";
    else if("/periodic-latency".equals(uri.getPath()))name="periodic-latency-results.json";
    else if("/native-probe".equals(uri.getPath()))name="native-probe-results.json";
    else if("/gecko-pool".equals(uri.getPath()))name="gecko-pool-results.json";
    else if("/preconnect".equals(uri.getPath()))name="preconnect-results.json";
    else if("/network-source-route".equals(uri.getPath()))name="network-source-route-results.json";
    else if("/network-source-sharing".equals(uri.getPath()))name="network-source-sharing-results.json";
    else if("/appearance".equals(uri.getPath()))name="appearance-results.json";
    else if("/network-source".equals(uri.getPath()))name="network-source-results.json";
    else if("/network-source-ui-state".equals(uri.getPath()))name="network-source-ui-state.json";
    else if("/network-source-ui".equals(uri.getPath()))name="network-source-ui-results.json";
    else if("/network-safe-idle".equals(uri.getPath()))name="network-safe-idle-results.json";
    else if("/network-settings-retry".equals(uri.getPath()))name="network-settings-retry-results.json";
    else if("/network-settings-application".equals(uri.getPath()))name="network-settings-application-results.json";
    else if("/network-settings-internal".equals(uri.getPath()))name="network-settings-internal-results.json";
    else if("/gecko-scroll".equals(uri.getPath()))name="gecko-scroll-diagnostics.json";
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
