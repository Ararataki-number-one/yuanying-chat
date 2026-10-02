package local.pocketchat;
import android.os.SystemClock;import org.json.*;import java.io.*;import java.net.*;import java.nio.charset.StandardCharsets;import java.util.concurrent.*;

/** Reads the core's one-second counters over authenticated loopback, only while visible. */
final class TrafficMonitor {
 static final long FRESH_MS=5000;
 static final class Sample {final long up,down,upTotal,downTotal,at;Sample(long up,long down,long upTotal,long downTotal,long at){this.up=up;this.down=down;this.upTotal=upTotal;this.downTotal=downTotal;this.at=at;}boolean fresh(long now){return now>=at&&now-at<=FRESH_MS;}}
 final NativeNetwork network;final ExecutorService reader=Executors.newSingleThreadExecutor();volatile Sample sample;volatile boolean visible;volatile long generation;volatile HttpURLConnection connection;
 TrafficMonitor(NativeNetwork n){network=n;}
 synchronized void watch(boolean enabled){if(enabled==visible)return;visible=enabled;long run=++generation;sample=null;HttpURLConnection old=connection;connection=null;if(old!=null)new Thread(()->old.disconnect(),"traffic-stop").start();if(enabled)reader.execute(()->loop(run));}
 boolean current(long run){return visible&&generation==run;}
 static Sample parse(String line,long time)throws Exception{JSONObject data=new JSONObject(line);String[] keys={"up","down","upTotal","downTotal"};long[] values=new long[4];for(int i=0;i<keys.length;i++){Object value=data.opt(keys[i]);if(!(value instanceof Integer)&&!(value instanceof Long))throw new IOException("invalid traffic counter");long count=((Number)value).longValue();if(count<0)throw new IOException("invalid traffic counter");values[i]=count;}return new Sample(values[0],values[1],values[2],values[3],time);}
 static String line(InputStream stream)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();int value;while((value=stream.read())!=-1){if(value=='\n')return out.toString("UTF-8");if(out.size()>=4096)throw new IOException("traffic sample too large");if(value!='\r')out.write(value);}throw new EOFException();}
 synchronized void publish(long run,String token,Sample next){if(current(run)&&network.ready&&token.equals(network.token))sample=next;}
 void loop(long run){while(current(run)){if(!network.ready||!network.coreAlive()){sample=null;pause();continue;}String token=network.token;int port=network.controllerPort;HttpURLConnection c=null;try{c=(HttpURLConnection)new URL("http://127.0.0.1:"+port+"/traffic").openConnection(Proxy.NO_PROXY);c.setConnectTimeout(2000);c.setReadTimeout(3500);c.setInstanceFollowRedirects(false);c.setRequestProperty("Authorization","Bearer "+token);connection=c;if(!current(run))break;if(c.getResponseCode()!=200)throw new IOException("traffic unavailable");try(InputStream in=new BufferedInputStream(c.getInputStream())){while(current(run)&&network.ready&&token.equals(network.token))publish(run,token,parse(line(in),SystemClock.elapsedRealtime()));}}catch(Exception ignored){if(current(run))sample=null;}finally{if(c!=null)c.disconnect();if(connection==c)connection=null;}if(current(run))pause();}}
 void pause(){try{Thread.sleep(800);}catch(InterruptedException e){Thread.currentThread().interrupt();}}
}
