package local.pocketchat;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public final class TransferCases {
  static final List<String> checks=new ArrayList<>();
  static void yes(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  interface Work {void run()throws Exception;}
  static void rejects(String name,Work work)throws Exception {try{work.run();}catch(IOException expected){checks.add(name);return;}throw new AssertionError(name);}
  static final class Connection extends HttpURLConnection {
    final Map<String,String> headers=new HashMap<>(),sent=new HashMap<>();
    byte[] payload="actual complete bytes".getBytes(StandardCharsets.UTF_8);
    long declared=payload.length;int status=200,streamReads,disconnects;Runnable afterHeaders,afterRead;
    Connection(String target)throws Exception{super(new URL(target));headers.put("Content-Type","text/plain");}
    public void connect(){} public boolean usingProxy(){return true;} public void disconnect(){disconnects++;}
    public void setRequestProperty(String name,String value){sent.put(name,value);}
    public int getResponseCode(){if(afterHeaders!=null)afterHeaders.run();return status;}
    public String getHeaderField(String name){return headers.get(name);}
    public long getContentLengthLong(){return declared;}
    public String getContentType(){return headers.get("Content-Type");}
    public InputStream getInputStream(){streamReads++;return new ByteArrayInputStream(payload){@Override public synchronized int read(byte[] b,int off,int len){int result=super.read(b,off,len);if(afterRead!=null){Runnable work=afterRead;afterRead=null;work.run();}return result;}};}
  }
  static final class Route implements BrowserDownloadTransfer.Route {
    boolean current=true;final List<String> opened=new ArrayList<>();final Deque<Connection> queue=new ArrayDeque<>();
    public boolean current(){return current;}
    public HttpURLConnection open(URL target)throws IOException {if(!current)throw new IOException("route changed");opened.add(target.toString());Connection c=queue.poll();if(c==null)throw new IOException("no route connection");return c;}
  }
  static BrowserDownloadTransfer.Result run(File cache,BrowserDownloadTransfer transfer,Route route,BrowserDownloadTransfer.Cookies cookies)throws IOException {
    return transfer.fetch("https://first.example/file","actual-user-agent","attachment; filename=original.txt","application/octet-stream",-1,cache,route,cookies,(received,total)->{});
  }
  static boolean empty(File cache){String[] names=cache.list();return names!=null&&names.length==0;}
  public static void main(String[] args)throws Exception {
    File cache=Files.createTempDirectory("browser-transfer-").toFile();
    try{
      for(String invalid:new String[]{"file:///data/private","content://private/file","javascript:alert(1)","data:text/plain,a","blob:https://first.example/id","intent://first.example/#Intent;scheme=https;end","https://user:secret@first.example/file","https://first.example/with space","https://first.example/\\evil","https://first.example/\nsecret","https://first.example:99999/file","http:///missing-host","http://127.0.0.1/file","https://192.168.1.1/file","https://localhost/file","https://[::1]/file","http://2130706433/file"})
        rejects("Reject download address "+invalid.replace('\n','_'),()->BrowserDownloadTransfer.address(invalid));
      yes("Normal HTTPS target is accepted",BrowserDownloadTransfer.address("https://first.example/file?q=1").getHost().equals("first.example"));
      Route route=new Route();Connection connection=new Connection("https://first.example/file");route.queue.add(connection);
      BrowserDownloadTransfer.Result saved=run(cache,new BrowserDownloadTransfer(),route,target->"session=first");
      yes("Result contains exactly the complete response bytes",Arrays.equals(Files.readAllBytes(saved.file.toPath()),connection.payload)&&saved.bytes==connection.payload.length);
      yes("Only requested agent and target cookie are installed",connection.sent.get("User-Agent").equals("actual-user-agent")&&connection.sent.get("Cookie").equals("session=first")&&!connection.sent.containsKey("Authorization")&&!connection.sent.containsKey("Referer"));
      yes("GET keeps manual redirects and identity encoding",connection.getRequestMethod().equals("GET")&&!connection.getInstanceFollowRedirects()&&connection.sent.get("Accept-Encoding").equals("identity"));
      yes("Completed connection is always disconnected",connection.disconnects==1);saved.file.delete();
      route=new Route();Connection first=new Connection("https://first.example/file"),second=new Connection("https://second.example/file");first.status=302;first.headers.put("Location","https://second.example/file");second.headers.put("Content-Disposition","attachment; filename=final.txt");route.queue.add(first);route.queue.add(second);List<String> cookieTargets=new ArrayList<>();
      saved=run(cache,new BrowserDownloadTransfer(),route,target->{cookieTargets.add(target);return target.contains("first.example")?"session=first":"session=second";});
      yes("Redirect obtains fresh cookies separately for each target",cookieTargets.equals(Arrays.asList("https://first.example/file","https://second.example/file"))&&first.sent.get("Cookie").equals("session=first")&&second.sent.get("Cookie").equals("session=second"));
      yes("Final response metadata wins over initial hints",saved.disposition.contains("final.txt")&&saved.url.equals("https://second.example/file")&&saved.mime.equals("text/plain"));saved.file.delete();
      for(String location:new String[]{"http://first.example/plain","file:///data/private","https://user:password@second.example/file","https://127.0.0.1/private","https://192.168.1.1/private"}){
        Route selected=new Route();Connection redirect=new Connection("https://first.example/file");redirect.status=302;redirect.headers.put("Location",location);selected.queue.add(redirect);
        rejects("Reject unsafe redirect "+location,()->run(cache,new BrowserDownloadTransfer(),selected,target->"cookie"));
        yes("Unsafe redirect never opens replacement connection "+location,selected.opened.size()==1&&redirect.disconnects==1);
      }
      Route tooMany=new Route();for(int index=0;index<6;index++){Connection redirect=new Connection("https://first.example/file");redirect.status=302;redirect.headers.put("Location","/again"+index);tooMany.queue.add(redirect);}
      rejects("Redirect chain has a hard six-request bound",()->run(cache,new BrowserDownloadTransfer(),tooMany,target->""));yes("Redirect limit never tries a seventh route open",tooMany.opened.size()==6);
      for(int code:new int[]{206,400,403,404,500}){Route selected=new Route();Connection failure=new Connection("https://first.example/file");failure.status=code;selected.queue.add(failure);rejects("HTTP "+code+" cannot manufacture a complete file",()->run(cache,new BrowserDownloadTransfer(),selected,target->""));yes("Rejected status reads no response body "+code,failure.streamReads==0&&failure.disconnects==1);}
      Route unavailable=new Route();unavailable.current=false;rejects("Lost route refuses the first open",()->run(cache,new BrowserDownloadTransfer(),unavailable,target->""));yes("No direct fallback exists after route loss",unavailable.opened.isEmpty());
      Route headersChanged=new Route();Connection duringHeaders=new Connection("https://first.example/file");duringHeaders.afterHeaders=()->headersChanged.current=false;headersChanged.queue.add(duringHeaders);
      rejects("Route loss during headers aborts before body",()->run(cache,new BrowserDownloadTransfer(),headersChanged,target->""));yes("Lost-header attempt closes without reading",duringHeaders.streamReads==0&&duringHeaders.disconnects==1);
      Route bodyChanged=new Route();Connection duringBody=new Connection("https://first.example/file");duringBody.afterRead=()->bodyChanged.current=false;bodyChanged.queue.add(duringBody);
      rejects("Route loss during body prevents publication",()->run(cache,new BrowserDownloadTransfer(),bodyChanged,target->""));yes("Failed body removes its private partial",empty(cache));
      Route cookieChanged=new Route();Connection afterCookie=new Connection("https://first.example/file");cookieChanged.queue.add(afterCookie);
      rejects("Cookie lookup cannot bridge a route epoch change",()->run(cache,new BrowserDownloadTransfer(),cookieChanged,target->{cookieChanged.current=false;return "cookie";}));yes("Route change during cookie lookup closes before body",afterCookie.streamReads==0&&afterCookie.disconnects==1);
      Route cookieFailure=new Route();cookieFailure.queue.add(new Connection("https://first.example/file"));rejects("Injected cookie headers are rejected",()->run(cache,new BrowserDownloadTransfer(),cookieFailure,target->"a=1\r\nX-Leak: yes"));
      for(long length:new long[]{1,1000}){Route selected=new Route();Connection truncated=new Connection("https://first.example/file");truncated.declared=length;selected.queue.add(truncated);rejects("Incorrect advertised bytes "+length+" cannot succeed",()->run(cache,new BrowserDownloadTransfer(),selected,target->""));yes("Truncated/extra body leaves no partial "+length,empty(cache));}
      Route oversized=new Route();Connection huge=new Connection("https://first.example/file");huge.declared=BrowserDownloadTransfer.MAX_BYTES+1;oversized.queue.add(huge);rejects("Response size limit is enforced before body",()->run(cache,new BrowserDownloadTransfer(),oversized,target->""));yes("Oversized body is never opened",huge.streamReads==0);
      Route advertised=new Route();rejects("Listener size limit is enforced before route open",()->new BrowserDownloadTransfer().fetch("https://first.example/file","ua","","",BrowserDownloadTransfer.MAX_BYTES+1,cache,advertised,target->"",(a,b)->{}));yes("Oversized listener value opens no connection",advertised.opened.isEmpty());
      Route encoded=new Route();Connection gzip=new Connection("https://first.example/file");gzip.headers.put("Content-Encoding","gzip");encoded.queue.add(gzip);rejects("Unsupported response encoding cannot save corrupted bytes",()->run(cache,new BrowserDownloadTransfer(),encoded,target->""));
      BrowserDownloadTransfer cancelled=new BrowserDownloadTransfer();cancelled.cancel();Route cancelRoute=new Route();rejects("Cancel before execution prevents opening",()->run(cache,cancelled,cancelRoute,target->""));yes("Precancel opens no connection",cancelRoute.opened.isEmpty());
      Route unknown=new Route();Connection chunked=new Connection("https://first.example/file");chunked.declared=-1;unknown.queue.add(chunked);saved=run(cache,new BrowserDownloadTransfer(),unknown,target->null);yes("Unknown total succeeds only after EOF with actual counted bytes",saved.bytes==chunked.payload.length&&!chunked.sent.containsKey("Cookie"));saved.file.delete();
      yes("All successful and failed cases clean their private files",empty(cache));
      System.out.println("{\"status\":\"passed\",\"checks\":"+checks.size()+",\"scope\":\"Complete production BrowserDownloadTransfer with explicit frozen-route and HttpURLConnection boundaries; no Android or real proxy execution\"}");
    }finally{File[] remaining=cache.listFiles();if(remaining!=null)for(File file:remaining)file.delete();cache.delete();}
  }
}
