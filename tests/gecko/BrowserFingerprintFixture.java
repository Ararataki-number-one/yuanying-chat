package local.pocketchat;

import android.app.Activity;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Integration-only client of the host fixture. No TLS key or server exists in the APK. */
final class BrowserFingerprintFixture implements AutoCloseable {
  static final String A="fp-a.pocketchat.test",B="fp-b.pocketchat.test";
  static final int GUEST_PORT=18765;
  final String nonce,source,engine,leafSha256,caPemSha256;final int guestPort;
  final AtomicInteger accepted=new AtomicInteger();volatile boolean closed;
  volatile JSONObject latest=new JSONObject();Thread reader;
  BrowserFingerprintFixture(Activity activity,String expectedEngine)throws Exception{
    if(!"local.pocketchat.test".equals(activity.getPackageName()))throw new SecurityException("Integration only");
    nonce=activity.getIntent().getStringExtra("runNonce");source=activity.getIntent().getStringExtra("sourceCommit");engine=expectedEngine;
    leafSha256=activity.getIntent().getStringExtra("expectedLeafSha256");caPemSha256=activity.getIntent().getStringExtra("publicCaPemSha256");guestPort=activity.getIntent().getIntExtra("fixturePort",-1);
    if(nonce==null||!nonce.matches("[0-9a-f]{32}")||source==null||!source.matches("[0-9a-f]{40}")||!expectedEngine.equals(activity.getIntent().getStringExtra("fixtureEngine"))||guestPort!=GUEST_PORT||leafSha256==null||!leafSha256.matches("[0-9a-f]{64}")||caPemSha256==null||!caPemSha256.matches("[0-9a-f]{64}"))throw new SecurityException("Current host fixture binding required");
  }
  int port(){return guestPort;}
  void start(){reader=new Thread(()->{while(!closed){try{
    HttpURLConnection connection=(HttpURLConnection)new URL("http://127.0.0.1:"+guestPort+"/__evidence?engine="+engine+"&nonce="+nonce+"&source="+source).openConnection(Proxy.NO_PROXY);
    connection.setConnectTimeout(2000);connection.setReadTimeout(2000);connection.setUseCaches(false);
    try{if(connection.getResponseCode()!=200)throw new IOException("Host evidence unavailable");byte[] raw;try(InputStream in=connection.getInputStream()){raw=read(in,262144);}JSONObject value=new JSONObject(new String(raw,StandardCharsets.UTF_8));
      JSONObject binding=value.getJSONObject("binding");if(!engine.equals(value.getString("engine"))||!nonce.equals(binding.getString("runNonce"))||!source.equals(binding.getString("sourceCommit"))||!leafSha256.equals(value.getString("leafDerSha256"))||!caPemSha256.equals(value.getString("caPemSha256")))throw new SecurityException("Host evidence binding differs");
      latest=value;accepted.set(value.getInt("accepted"));
    }finally{connection.disconnect();}
  }catch(Exception ignored){}try{Thread.sleep(100);}catch(InterruptedException done){return;}}},"synthetic-host-evidence");reader.setDaemon(true);reader.start();}
  static byte[] read(InputStream in,int max)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[2048];int count;while((count=in.read(bytes))!=-1){if(out.size()+count>max)throw new IOException("Synthetic input too large");out.write(bytes,0,count);}return out.toByteArray();}
  static String sha(byte[] bytes)throws Exception{StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
  JSONObject snapshot(){return J.parse(latest.toString());}
  public void close(){closed=true;if(reader!=null)reader.interrupt();}
}
