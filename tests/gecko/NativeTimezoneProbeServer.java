package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Integration-only loopback documents and bounded synthetic observation sink. */
final class NativeTimezoneProbeServer implements AutoCloseable {
  static final List<String> ROLES=Arrays.asList("page","dedicated","blob","shared","service");
  interface Observation {void receive(JSONObject packet);}
  final ServerSocket socket;final ExecutorService clients=Executors.newFixedThreadPool(4);
  final String nonce,source;final byte[] script;final Observation observation;
  volatile boolean closed;Thread listener;int accepted;
  NativeTimezoneProbeServer(Context context,String nonce,String source,Observation observation)throws Exception{
    this.nonce=nonce;this.source=source;this.observation=observation;
    try(InputStream input=context.getAssets().open("native-timezone-probe.js")){script=read(input,32768);}
    socket=new ServerSocket(0,16,InetAddress.getByName("127.0.0.1"));
  }
  int port(){return socket.getLocalPort();}
  String url(String path){return "http://127.0.0.1:"+port()+path+"?nonce="+nonce;}
  void start(){listener=new Thread(()->{while(!closed){try{
    Socket client=socket.accept();synchronized(this){if(++accepted>128){client.close();continue;}}
    clients.execute(()->serve(client));
  }catch(IOException|RejectedExecutionException error){if(!closed)close();}}},"native-timezone-loopback");listener.setDaemon(true);listener.start();}
  static byte[] read(InputStream input,int limit)throws IOException{
    ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[2048];int count;
    while((count=input.read(bytes))!=-1){if(out.size()+count>limit)throw new IOException("Bounded synthetic input exceeded");out.write(bytes,0,count);}return out.toByteArray();
  }
  static String line(InputStream input)throws IOException{
    ByteArrayOutputStream out=new ByteArrayOutputStream();int value;
    while((value=input.read())!=-1){if(value==10)break;if(out.size()>=4096)throw new IOException("Header bound");if(value!=13)out.write(value);}
    return out.toString("US-ASCII");
  }
  void serve(Socket client){try(Socket ignored=client){
    client.setSoTimeout(5000);InputStream in=client.getInputStream();
    String[] first=line(in).split(" ");if(first.length!=3){respond(client,400,"text/plain",new byte[0]);return;}
    String method=first[0],target=first[1];int length=0,headers=0;String row;
    while(!(row=line(in)).isEmpty()){if(++headers>64)throw new IOException("Header count");
      if(row.toLowerCase(Locale.ROOT).startsWith("content-length:")){length=Integer.parseInt(row.substring(row.indexOf(':')+1).trim());}}
    if(length<0||length>16384)throw new IOException("Body bound");
    URI uri=new URI(target);String path=uri.getPath();
    if(uri.isAbsolute()||!("nonce="+nonce).equals(uri.getRawQuery())){respond(client,403,"text/plain",new byte[0]);return;}
    if("POST".equals(method)&&"/report".equals(path)){
      byte[] body=new byte[length];int at=0,count;while(at<body.length&&(count=in.read(body,at,body.length-at))>0)at+=count;
      if(at!=body.length)throw new EOFException("Short report");
      JSONObject value=new JSONObject(new String(body,StandardCharsets.UTF_8));
      Set<String> keys=new HashSet<>();Iterator<String> names=value.keys();while(names.hasNext())keys.add(names.next());
      if(!keys.equals(new HashSet<>(Arrays.asList("schema","nonce","sourceCommit","role","status","observation","error")))
          ||!(value.get("schema") instanceof Integer)||value.getInt("schema")!=1
          ||!nonce.equals(value.getString("nonce"))||!source.equals(value.getString("sourceCommit"))
          ||!ROLES.contains(value.getString("role"))
          ||!Arrays.asList("observed","unsupported","failed").contains(value.getString("status")))throw new IOException("Unbound report");
      observation.receive(new JSONObject(value.toString()));respond(client,200,"text/plain","ok".getBytes(StandardCharsets.US_ASCII));return;
    }
    if(!"GET".equals(method)){respond(client,405,"text/plain",new byte[0]);return;}
    if("/bootstrap".equals(path)){respond(client,200,"text/html","<!doctype html><meta charset=utf-8><title>Native timezone bootstrap</title><p>Controlled bootstrap</p>".getBytes(StandardCharsets.UTF_8));return;}
    if("/probe".equals(path)){
      String config=new JSONObject().put("schema",1).put("nonce",nonce).put("source",source).toString();
      String html="<!doctype html><meta charset=utf-8><title>Native timezone observation</title><script>globalThis.__nativeTimezoneProbe="+config+";</script><script src='/probe.js?nonce="+nonce+"'></script>";
      respond(client,200,"text/html",html.getBytes(StandardCharsets.UTF_8));return;
    }
    if("/worker.js".equals(path)||"/probe.js".equals(path)){respond(client,200,"application/javascript",script);return;}
    respond(client,404,"text/plain",new byte[0]);
  }catch(Exception rejected){/* Invalid synthetic requests never become observations. */}}
  static void respond(Socket client,int status,String type,byte[] body)throws IOException{
    OutputStream out=client.getOutputStream();String headers="HTTP/1.1 "+status+" Response\r\nContent-Type: "+type+"; charset=utf-8\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nService-Worker-Allowed: /\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n";
    out.write(headers.getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();
  }
  public void close(){closed=true;try{socket.close();}catch(IOException ignored){}clients.shutdownNow();}
}
