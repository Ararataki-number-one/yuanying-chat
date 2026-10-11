package local.pocketchat;

import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Real HTTP regression for the production range reader; no mock response streams. */
public final class AppUpdateTransferTest {
  static final byte[] DATA=new byte[192*1024];static final String ETAG="\"release-fixture-1\"";
  static final List<String> passed=new ArrayList<>();static Path root;static HttpServer server;
  static {new Random(7654321).nextBytes(DATA);}
  static final class Fixture implements HttpHandler {
    final String mode;int requests;long served;final List<String> ranges=new ArrayList<>(),ifRanges=new ArrayList<>();
    Fixture(String mode){this.mode=mode;}
    public synchronized void handle(HttpExchange x)throws IOException {requests++;String range=x.getRequestHeaders().getFirst("Range"),ifRange=x.getRequestHeaders().getFirst("If-Range");ranges.add(range==null?"":range);ifRanges.add(ifRange==null?"":ifRange);
      int offset=range==null?0:Integer.parseInt(range.substring(6,range.length()-1));boolean first=requests==1;
      if("redirect".equals(mode)){x.getResponseHeaders().add("Location","http://release-assets.githubusercontent.com/github-production-release-asset/fixture");x.sendResponseHeaders(302,-1);x.close();return;}
      if("status".equals(mode)){x.sendResponseHeaders(503,-1);x.close();return;}
      if("416".equals(mode)){x.getResponseHeaders().add("Content-Range","bytes */"+DATA.length);x.sendResponseHeaders(416,-1);x.close();return;}
      boolean ignore="ignore".equals(mode)&&!first;int start=ignore?0:offset,code=first||ignore?200:206;
      x.getResponseHeaders().add("ETag",!first&&"etag".equals(mode)?"\"different-release\"":ETAG);
      if(!first&&"encoding".equals(mode))x.getResponseHeaders().add("Content-Encoding","gzip");
      if(code==206){int headerStart="start".equals(mode)?start+1:start,total="total".equals(mode)?DATA.length+1:DATA.length,end=DATA.length-1;String header="malformed".equals(mode)?"bytes garbage":"bytes "+headerStart+"-"+end+"/"+total;x.getResponseHeaders().add("Content-Range",header);}
      if("zeroLength".equals(mode)){x.sendResponseHeaders(200,1);x.getResponseBody().write(0);served++;x.close();return;}
      int length=DATA.length-start;if(!first&&"length".equals(mode))length--;
      x.sendResponseHeaders(code,length);
      int send=first?DATA.length/2:DATA.length-start;if(!first&&"length".equals(mode))send--;
      try{x.getResponseBody().write(DATA,start,send);x.getResponseBody().flush();served+=send;}finally{x.close();}
    }
  }
  static void check(boolean condition,String name){if(!condition)throw new AssertionError(name);passed.add(name);}
  static AppUpdateTransfer transfer(File dir,Fixture fixture)throws IOException {return new AppUpdateTransfer(dir,new AppUpdateTransfer.Request(99,AppUpdatePolicy.hash(DATA),DATA.length,AppUpdatePolicy.asset("99.0.0")),url->(HttpURLConnection)new URL("http://127.0.0.1:"+server.getAddress().getPort()+"/"+fixture.mode).openConnection(),null);}
  static File dir(String name)throws IOException{return Files.createDirectory(root.resolve(name)).toFile();}
  static void interrupted(AppUpdateTransfer t)throws IOException {try{t.run(()->false);throw new AssertionError("Expected interrupted body");}catch(IOException expected){if(expected instanceof AppUpdateTransfer.InvalidResponse)throw expected;}}
  static void invalid(AppUpdateTransfer t)throws IOException {try{t.run(()->false);throw new AssertionError("Expected invalid server response");}catch(AppUpdateTransfer.InvalidResponse expected){}}
  static Fixture fixture(String mode){Fixture f=new Fixture(mode);server.createContext("/"+mode,f);return f;}
  static void rejection(String mode,String label)throws IOException {Fixture f=fixture(mode);File dir=dir(mode);AppUpdateTransfer first=transfer(dir,f);interrupted(first);long have=first.received();AppUpdateTransfer resumed=transfer(dir,f);invalid(resumed);check(resumed.received()==have,label);check(f.ranges.get(1).equals("bytes="+have+"-")&&ETAG.equals(f.ifRanges.get(1)),label+" uses the persisted Range and If-Range");}
  static String quote(String value){return "\""+value.replace("\\","\\\\").replace("\"","\\\"")+"\"";}
  public static void main(String[] args)throws Exception {root=Files.createTempDirectory("pocket-update-range-");server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);ExecutorService executor=Executors.newCachedThreadPool();server.setExecutor(executor);server.start();
    try{
      Fixture good=fixture("resume");File goodDir=dir("resume");AppUpdateTransfer first=transfer(goodDir,good);interrupted(first);long have=first.received();check(have>0&&have<DATA.length,"A real interrupted HTTP body preserves its partial bytes");
      AppUpdateTransfer resumed=transfer(goodDir,good);check(resumed.received()==have,"A reconstructed transfer recovers release-bound durable progress");resumed.run(()->false);
      check(AppUpdatePolicy.hash(Files.readAllBytes(resumed.partial().toPath())).equals(AppUpdatePolicy.hash(DATA)),"A resumed real HTTP response reconstructs the exact expected payload");check(good.requests==2&&good.served==DATA.length,"Successful resume transfers only the missing bytes without redownloading the first half");check(good.ranges.get(1).equals("bytes="+have+"-")&&ETAG.equals(good.ifRanges.get(1)),"Resume sends the exact persisted Range offset and strong If-Range validator");
      Fixture ignore=fixture("ignore");File ignoredir=dir("ignore");AppUpdateTransfer beforeIgnore=transfer(ignoredir,ignore);interrupted(beforeIgnore);AppUpdateTransfer ignored=transfer(ignoredir,ignore);ignored.run(()->false);check(ignored.received()==DATA.length&&AppUpdatePolicy.hash(Files.readAllBytes(ignored.partial().toPath())).equals(AppUpdatePolicy.hash(DATA)),"A server ignoring Range with 200 restarts safely instead of appending duplicate bytes");check(ignore.served==DATA.length+DATA.length/2,"Ignoring Range restarts exactly one full body after the partial attempt");
      rejection("start","A wrong Content-Range start is rejected before appending");rejection("total","A Content-Range total different from release metadata is rejected");rejection("malformed","A malformed Content-Range is rejected");rejection("etag","A changed ETag in a 206 response is rejected before appending");rejection("length","A 206 Content-Length inconsistent with its range is rejected");rejection("encoding","Compressed range responses are rejected before appending");
      Fixture unavailable=fixture("status");AppUpdateTransfer unavailableTransfer=transfer(dir("status"),unavailable);interrupted(unavailableTransfer);check(unavailableTransfer.received()==0,"An unavailable server cannot create unverified progress");
      Fixture wrong416=fixture("416");AppUpdateTransfer incomplete=transfer(dir("416"),wrong416);invalid(incomplete);check(incomplete.received()==0,"A 416 response cannot declare an incomplete file complete");
      Fixture wrongLength=fixture("zeroLength");AppUpdateTransfer shortFile=transfer(dir("zeroLength"),wrongLength);invalid(shortFile);check(shortFile.received()==0,"A 200 length different from release metadata is rejected before writing");
      Fixture redirect=fixture("redirect");AppUpdateTransfer unsafe=transfer(dir("redirect"),redirect);invalid(unsafe);check(redirect.requests==1,"A redirect from the official request to plaintext HTTP is rejected before connecting");
      check(!AppUpdateTransfer.trusted("https://example.org/a",AppUpdatePolicy.asset("99.0.0"))&&!AppUpdateTransfer.trusted("https://github.com/evil/project/releases/download/a",AppUpdatePolicy.asset("99.0.0"))&&!AppUpdateTransfer.trusted("https://user@release-assets.githubusercontent.com/github-production-release-asset/x",AppUpdatePolicy.asset("99.0.0")),"Download trust rejects unrelated repositories, external hosts and embedded credentials");
      check(AppUpdateTransfer.trusted("https://release-assets.githubusercontent.com/github-production-release-asset/1/asset?se=expires",AppUpdatePolicy.asset("99.0.0")),"Official HTTPS release asset redirects remain supported");
      File identityDir=dir("identity");AppUpdateTransfer original=transfer(identityDir,good);try(FileOutputStream out=new FileOutputStream(original.partial())){out.write(DATA,0,100);}Properties corrupted=new Properties();corrupted.setProperty("identity","another-release");try(FileOutputStream out=new FileOutputStream(original.meta)){corrupted.store(out,"");}AppUpdateTransfer recovered=transfer(identityDir,good);check(recovered.received()==0,"Mismatched release metadata cannot reuse existing partial bytes");
      AtomicBoolean disconnected=new AtomicBoolean();AppUpdateTransfer socketFailure=new AppUpdateTransfer(dir("disconnect"),new AppUpdateTransfer.Request(99,AppUpdatePolicy.hash(DATA),DATA.length,AppUpdatePolicy.asset("99.0.0")),url->new HttpURLConnection(new URL(url)){public int getResponseCode()throws IOException{throw new IOException("connect failed");}public void disconnect(){disconnected.set(true);}public boolean usingProxy(){return false;}public void connect(){}},null);interrupted(socketFailure);check(disconnected.get()&&socketFailure.active==null,"A response-code exception disconnects its unreturned connection and clears ownership");
      AppUpdateTransfer stopped=transfer(dir("stop"),good);stopped.cancel();try{stopped.run(()->false);throw new AssertionError("Stopped transfer ran");}catch(AppUpdateTransfer.Stopped expected){}check(stopped.received()==0&&stopped.active==null,"A cancelled generation opens no new transfer connection");
      StringBuilder json=new StringBuilder("{\"passed\":").append(passed.size()).append(",\"total\":").append(passed.size()).append(",\"actualHttpRequests\":true,\"checks\":[");for(int i=0;i<passed.size();i++){if(i>0)json.append(',');json.append("{\"name\":").append(quote(passed.get(i))).append(",\"passed\":true}");}System.out.println(json.append("]}"));
    }finally{server.stop(0);executor.shutdownNow();try(java.util.stream.Stream<Path> paths=Files.walk(root)){paths.sorted(Comparator.reverseOrder()).forEach(p->{try{Files.deleteIfExists(p);}catch(IOException ignored){}});}}
  }
}
