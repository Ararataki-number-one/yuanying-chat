package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Integration-only loopback documents and bounded native CPU observations. */
final class NativeHardwareProbeServer implements AutoCloseable {
  static final List<String> PHASES=Arrays.asList("baseline","cap2","cap1","reset");
  static final List<String> ROLES=Arrays.asList("page","dedicated","blob","shared","service");
  interface Observation {void receive(JSONObject packet);}
  final ServerSocket socket;final ExecutorService clients=Executors.newFixedThreadPool(4);
  final String nonce,source;final byte[] script;final Observation observation;
  volatile boolean closed;Thread listener;int accepted;
  final JSONArray events=new JSONArray();int requests,responses,rejectedRequests,transportErrors;
  static String safePath(String path){
    if("/bootstrap".equals(path))return "bootstrap";
    for(String phase:PHASES)for(String file:Arrays.asList("probe","probe.js","worker.js","report"))
      if(("/"+phase+"/"+file).equals(path))return phase+"/"+file;
    return "other";
  }
  synchronized void record(String event,String method,String path,Integer status,String error){try{
    if("request".equals(event))requests++;if("response".equals(event))responses++;
    if("rejected".equals(event))rejectedRequests++;if("error".equals(event))transportErrors++;
    if(events.length()<256)events.put(new JSONObject().put("event",event)
      .put("method",Arrays.asList("GET","POST").contains(method)?method:"other").put("path",safePath(path))
      .put("status",status==null?JSONObject.NULL:status).put("error",error==null?JSONObject.NULL:error));
  }catch(JSONException ignored){}}
  synchronized JSONObject snapshot()throws JSONException{return new JSONObject().put("schema",1).put("requests",requests)
    .put("responses",responses).put("rejectedRequests",rejectedRequests).put("transportErrors",transportErrors)
    .put("events",new JSONArray(events.toString())).put("eventsTruncated",requests+responses+rejectedRequests+transportErrors>events.length());}
  NativeHardwareProbeServer(Context context,String nonce,String source,Observation observation)throws Exception{
    this.nonce=nonce;this.source=source;this.observation=observation;
    try(InputStream input=context.getAssets().open("native-hardware-probe.js")){script=read(input,32768);}
    socket=new ServerSocket(0,16,InetAddress.getByName("127.0.0.1"));
  }
  int port(){return socket.getLocalPort();}
  String url(String path){return "http://127.0.0.1:"+port()+path+"?nonce="+nonce;}
  void start(){listener=new Thread(()->{while(!closed){try{
    Socket client=socket.accept();synchronized(this){if(++accepted>512){client.close();continue;}}
    clients.execute(()->serve(client));
  }catch(IOException|RejectedExecutionException error){if(!closed)close();}}},"native-hardware-loopback");listener.setDaemon(true);listener.start();}
  static byte[] read(InputStream input,int limit)throws IOException{
    ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[2048];int count;
    while((count=input.read(bytes))!=-1){if(out.size()+count>limit)throw new IOException("Bounded synthetic input exceeded");out.write(bytes,0,count);}return out.toByteArray();
  }
  static String line(InputStream input)throws IOException{
    ByteArrayOutputStream out=new ByteArrayOutputStream();int value;
    while((value=input.read())!=-1){if(value==10)break;if(out.size()>=4096)throw new IOException("Header bound");if(value!=13)out.write(value);}
    return out.toString("US-ASCII");
  }
  void serve(Socket client){String method="other",path="other";try(Socket ignored=client){
    client.setSoTimeout(5000);InputStream in=client.getInputStream();String[] first=line(in).split(" ");
    if(first.length!=3){record("rejected",method,path,null,"request-line");respond(client,400,"text/plain",new byte[0]);return;}
    method=first[0];String target=first[1];int length=0,headers=0;String row;
    while(!(row=line(in)).isEmpty()){if(++headers>64)throw new IOException("Header count");
      if(row.toLowerCase(Locale.ROOT).startsWith("content-length:")){length=Integer.parseInt(row.substring(row.indexOf(':')+1).trim());}}
    if(length<0||length>16384)throw new IOException("Body bound");
    URI uri=new URI(target);path=uri.getPath();record("request",method,path,null,null);
    if(uri.isAbsolute()||!("nonce="+nonce).equals(uri.getRawQuery())){record("rejected",method,path,null,"origin-or-nonce");send(client,method,path,403,"text/plain",new byte[0]);return;}
    String safe=safePath(path),phase=safe.contains("/")?safe.substring(0,safe.indexOf('/')):"";
    if("POST".equals(method)&&safe.endsWith("/report")&&PHASES.contains(phase)){
      byte[] body=new byte[length];int at=0,count;while(at<body.length&&(count=in.read(body,at,body.length-at))>0)at+=count;
      if(at!=body.length)throw new EOFException("Short report");
      JSONObject value=new JSONObject(new String(body,StandardCharsets.UTF_8));
      Set<String> keys=new HashSet<>();Iterator<String> names=value.keys();while(names.hasNext())keys.add(names.next());
      if(!keys.equals(new HashSet<>(Arrays.asList("schema","nonce","sourceCommit","role","phase","status","observation","error")))
          ||!(value.get("schema") instanceof Integer)||value.getInt("schema")!=1
          ||!nonce.equals(value.getString("nonce"))||!source.equals(value.getString("sourceCommit"))
          ||!phase.equals(value.getString("phase"))||!ROLES.contains(value.getString("role"))
          ||!Arrays.asList("observed","unsupported","failed").contains(value.getString("status")))throw new IOException("Unbound report");
      observation.receive(new JSONObject(value.toString()));send(client,method,path,200,"text/plain","ok".getBytes(StandardCharsets.US_ASCII));return;
    }
    if(!"GET".equals(method)){send(client,method,path,405,"text/plain",new byte[0]);return;}
    if("/bootstrap".equals(path)){send(client,method,path,200,"text/html","<!doctype html><meta charset=utf-8><title>Native hardware bootstrap</title><p>Controlled bootstrap</p>".getBytes(StandardCharsets.UTF_8));return;}
    if(safe.equals(phase+"/probe")&&PHASES.contains(phase)){
      String config=new JSONObject().put("schema",1).put("nonce",nonce).put("source",source).put("phase",phase).toString();
      String html="<!doctype html><meta charset=utf-8><title>Native CPU observation</title><script>globalThis.__nativeHardwareProbe="+config+";</script><script src='/"+phase+"/probe.js?nonce="+nonce+"'></script>";
      send(client,method,path,200,"text/html",html.getBytes(StandardCharsets.UTF_8));return;
    }
    if(PHASES.contains(phase)&&(safe.endsWith("/worker.js")||safe.endsWith("/probe.js"))){send(client,method,path,200,"application/javascript",script);return;}
    send(client,method,path,404,"text/plain",new byte[0]);
  }catch(Exception rejected){String error=rejected instanceof SocketTimeoutException?"timeout":rejected instanceof EOFException?"short-read":rejected instanceof JSONException?"json-shape":rejected instanceof URISyntaxException?"uri-shape":rejected instanceof IOException?"bounded-io":"request-shape";
    record("error",method,path,null,error);/* Never export raw URL, request body, headers or exception text. */}}
  void send(Socket client,String method,String path,int status,String type,byte[] body)throws IOException{
    respond(client,status,type,body);record("response",method,path,status,null);
  }
  static void respond(Socket client,int status,String type,byte[] body)throws IOException{
    OutputStream out=client.getOutputStream();String headers="HTTP/1.1 "+status+" Response\r\nContent-Type: "+type+"; charset=utf-8\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n";
    out.write(headers.getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();
  }
  public void close(){closed=true;try{socket.close();}catch(IOException ignored){}clients.shutdownNow();}
}
