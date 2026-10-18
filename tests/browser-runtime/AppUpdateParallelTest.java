package local.pocketchat;

import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Actual HTTP transfers with per-connection throttling, not a WAN speed claim. */
public final class AppUpdateParallelTest {
  static final byte[] DATA=new byte[8*1024*1024+123];
  static final String ETAG="\"parallel-fixture\"",ORIGIN=AppUpdatePolicy.asset("99.0.0");
  static int passed;static Path root;static HttpServer server;
  static {new Random(4321).nextBytes(DATA);}
  static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);passed++;}
  static final class Fixture implements HttpHandler {
    volatile String mode="range";volatile int delay=3;
    final AtomicInteger active=new AtomicInteger(),peak=new AtomicInteger(),bodies=new AtomicInteger();
    final List<String> ranges=Collections.synchronizedList(new ArrayList<>());
    final AtomicLong served=new AtomicLong();
    public void handle(HttpExchange x)throws IOException {
      String range=x.getRequestHeaders().getFirst("Range");ranges.add(range==null?"":range);
      if(mode.equals("unavailable")){x.sendResponseHeaders(503,-1);x.close();return;}
      boolean supports=!mode.equals("sequential");long start=0,end=DATA.length-1;
      if(supports&&range!=null){String[] parts=range.substring(6).split("-",-1);start=Long.parseLong(parts[0]);if(!parts[1].isEmpty())end=Long.parseLong(parts[1]);}
      String tag=mode.equals("changed")?"\"changed\"":ETAG;
      x.getResponseHeaders().add("ETag",tag);
      boolean partial=supports&&range!=null;
      if(partial)x.getResponseHeaders().add("Content-Range","bytes "+(mode.equals("wrong")&&end>0?start+1:start)+"-"+end+"/"+DATA.length);
      x.sendResponseHeaders(partial?206:200,end-start+1);
      int count=active.incrementAndGet();peak.accumulateAndGet(count,Math::max);if(end>0)bodies.incrementAndGet();
      try(OutputStream out=x.getResponseBody()){
        for(long at=start;at<=end;){int size=(int)Math.min(32768,end-at+1);out.write(DATA,(int)at,size);out.flush();served.addAndGet(size);at+=size;
          if(end>0&&delay>0)try{Thread.sleep(delay);}catch(InterruptedException e){Thread.currentThread().interrupt();return;}
        }
      }catch(IOException disconnected){}finally{active.decrementAndGet();x.close();}
    }
  }
  static final class Factory implements AppUpdateTransfer.ConnectionFactory {
    final Fixture fixture;final AtomicBoolean available=new AtomicBoolean(true);final AtomicInteger opens=new AtomicInteger();
    Factory(Fixture f){fixture=f;}
    public void check()throws IOException{if(!available.get())throw new IOException("fixture route revoked");}
    public HttpURLConnection open(String target)throws IOException {
      check();opens.incrementAndGet();HttpURLConnection local=(HttpURLConnection)new URL("http://127.0.0.1:"+server.getAddress().getPort()+"/file").openConnection();
      return new HttpURLConnection(new URL(target)){
        public void connect()throws IOException{local.connect();}public void disconnect(){local.disconnect();}public boolean usingProxy(){return true;}
        public void setRequestProperty(String k,String v){local.setRequestProperty(k,v);}
        public void setConnectTimeout(int v){local.setConnectTimeout(v);}public void setReadTimeout(int v){local.setReadTimeout(v);}
        public int getResponseCode()throws IOException{return local.getResponseCode();}public String getHeaderField(String name){return local.getHeaderField(name);}
        public long getContentLengthLong(){return local.getContentLengthLong();}public InputStream getInputStream()throws IOException{return local.getInputStream();}
      };
    }
  }
  static AppUpdateTransfer transfer(File dir,Factory f,AppUpdateTransfer.Listener listener)throws IOException{return new AppUpdateTransfer(dir,new AppUpdateTransfer.Request(99,AppUpdatePolicy.hash(DATA),DATA.length,ORIGIN),f,listener);}
  static File directory(String name)throws IOException{return Files.createDirectory(root.resolve(name)).toFile();}
  static void exact(AppUpdateTransfer t)throws IOException{check(Arrays.equals(DATA,Files.readAllBytes(t.partial().toPath())),"Both segments reconstruct exact APK bytes");}
  static void interrupted(AppUpdateTransfer t,java.util.function.BooleanSupplier stop)throws IOException{try{t.run(stop);throw new AssertionError("Expected stop");}catch(IOException expected){if(expected instanceof AppUpdateTransfer.InvalidResponse)throw expected;}}
  public static void main(String[] args)throws Exception {
    root=Files.createTempDirectory("update-parallel-");server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);ExecutorService threads=Executors.newCachedThreadPool();server.setExecutor(threads);Fixture f=new Fixture();server.createContext("/file",f);server.start();
    try{
      f.mode="sequential";AppUpdateTransfer serial=transfer(directory("serial"),new Factory(f),null);long start=System.nanoTime();serial.run(()->false);long serialMs=(System.nanoTime()-start)/1000000;exact(serial);check(!serial.parallel,"Range-ignoring server falls back to sequential transfer");
      f.mode="range";f.peak.set(0);AppUpdateTransfer parallel=transfer(directory("parallel"),new Factory(f),null);start=System.nanoTime();parallel.run(()->false);long parallelMs=(System.nanoTime()-start)/1000000;exact(parallel);
      check(parallel.parallel&&f.peak.get()==2,"Large supported asset has exactly two simultaneous body connections");
      check(parallelMs<serialMs*.85,"Two actual throttled HTTP connections reduce elapsed transfer time");
      f.delay=8;File pausedDir=directory("paused");AtomicBoolean pause=new AtomicBoolean();AppUpdateTransfer paused=transfer(pausedDir,new Factory(f),(have,total,speed)->{if(have>1024*1024)pause.set(true);});interrupted(paused,pause::get);long have=paused.received();
      check(have>0&&have<DATA.length&&paused.connections.isEmpty(),"Pause closes both workers and retains partial data");
      AppUpdateTransfer restored=transfer(pausedDir,new Factory(f),null);check(restored.received()==have,"Recreated transfer reports durable segment totals, not sparse file length");int before=f.ranges.size();restored.run(()->false);exact(restored);
      List<String> resumed=new ArrayList<>(f.ranges.subList(before,f.ranges.size()));check(resumed.contains("bytes="+paused.durable[0]+"-"+(DATA.length/2-1))&&resumed.contains("bytes="+(DATA.length/2+paused.durable[1])+"-"+(DATA.length-1)),"Both segments request only missing bytes after restart");
      File legacyDir=directory("legacy");AppUpdateTransfer legacy=transfer(legacyDir,new Factory(f),null);try(FileOutputStream out=new FileOutputStream(legacy.partial())){out.write(DATA,0,100);}legacy.etag=ETAG;legacy.saveMeta();legacy.run(()->false);exact(legacy);check(legacy.parallel,"Existing sequential progress migrates to segment checkpoints");
      File failureDir=directory("failure");Factory revokedFactory=new Factory(f);AppUpdateTransfer revoked=transfer(failureDir,revokedFactory,(bytes,total,speed)->{if(bytes>1024*1024)revokedFactory.available.set(false);});interrupted(revoked,()->false);check(revoked.connections.isEmpty()&&revoked.received()>0,"Route revocation terminates all connections without direct fallback");
      f.mode="unavailable";AppUpdateTransfer unavailable=transfer(failureDir,new Factory(f),null);long preserved=unavailable.received();interrupted(unavailable,()->false);check(unavailable.received()==preserved,"Temporary server error preserves parallel progress");
      f.mode="changed";AppUpdateTransfer changed=transfer(failureDir,new Factory(f),null);try{changed.run(()->false);throw new AssertionError("Accepted changed ETag");}catch(AppUpdateTransfer.InvalidResponse expected){}check(changed.received()==preserved,"Changed release identity cannot append any data");
      f.mode="wrong";AppUpdateTransfer wrong=transfer(directory("wrong"),new Factory(f),null);try{wrong.run(()->false);throw new AssertionError("Accepted incorrect range");}catch(AppUpdateTransfer.InvalidResponse expected){}check(wrong.received()==0&&wrong.connections.isEmpty(),"Wrong range is rejected before either segment writes");
      f.mode="range";File crashDir=directory("crash");AppUpdateTransfer crash=transfer(crashDir,new Factory(f),null);crash.prepareParallel(()->false);try(RandomAccessFile out=new RandomAccessFile(crash.partial(),"rw")){out.setLength(DATA.length);out.seek(DATA.length/2);out.write(DATA,DATA.length/2,10000);out.getFD().sync();}crash.segmentProgress(1,10000,true);
      AppUpdateTransfer afterCrash=transfer(crashDir,new Factory(f),null);check(afterCrash.received()==10000,"Sparse right segment cannot masquerade as a completed APK");afterCrash.run(()->false);exact(afterCrash);
      check(AppUpdatePolicy.hash(Files.readAllBytes(afterCrash.partial().toPath())).equals(AppUpdatePolicy.hash(DATA)),"Final full-file SHA remains authoritative");
      afterCrash.clear();check(!afterCrash.partial().exists()&&!afterCrash.meta.exists()&&afterCrash.received()==0,"Cancel cleanup removes segmented data and checkpoints");
      System.out.println("{\"passed\":"+passed+",\"sequentialMs\":"+serialMs+",\"parallelMs\":"+parallelMs+",\"actualHttp\":true,\"scope\":\"loopback per-connection throttle; not WAN or Android\"}");
    }finally{server.stop(0);threads.shutdownNow();try(java.util.stream.Stream<Path> paths=Files.walk(root)){paths.sorted(Comparator.reverseOrder()).forEach(p->{try{Files.deleteIfExists(p);}catch(IOException ignored){}});}}
  }
}
