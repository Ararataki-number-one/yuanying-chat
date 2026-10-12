package local.pocketchat;

import java.io.*;
import java.net.*;
import java.util.Properties;
import java.util.function.BooleanSupplier;
import java.util.regex.*;

/** A release-bound resumable transfer. It never decides whether an APK is safe to install. */
final class AppUpdateTransfer {
  interface ConnectionFactory { HttpURLConnection open(String url)throws IOException;default void check()throws IOException{}default void finished(){} }
  interface Listener { void progress(long received,long total,long bytesPerSecond); }
  static final ConnectionFactory OFFICIAL=url->(HttpURLConnection)new URL(url).openConnection();
  static final class Request {
    final long code,bytes;final String sha,url;
    Request(long code,String sha,long bytes,String url){this.code=code;this.sha=sha;this.bytes=bytes;this.url=url;}
    String identity(){return code+":"+sha+":"+bytes;}
  }
  static final class Stopped extends IOException { Stopped(){super("下载已暂停，已保留下载进度");} }
  static final class InvalidResponse extends IOException { InvalidResponse(String message){super(message);} }
  final File part,meta;final Request request;final ConnectionFactory factory;final Listener listener;
  volatile HttpURLConnection active;volatile boolean cancelled;String etag="";
  AppUpdateTransfer(File root,Request request,ConnectionFactory factory,Listener listener)throws IOException {
    this.request=request;this.factory=factory;this.listener=listener;
    if(!officialOrigin(request.url)||request.code<=0||request.bytes<=0||request.bytes>AppUpdatePolicy.MAX_APK||request.sha==null||!request.sha.matches("[a-f0-9]{64}"))throw new IOException("更新文件身份无效");
    if(!root.isDirectory()&&!root.mkdirs())throw new IOException("无法创建更新下载目录");
    String name="transfer-"+request.code+"-"+request.sha+"-"+request.bytes;
    part=new File(root,name+".part");meta=new File(root,name+".resume");load();
  }
  File partial(){return part;}
  long received(){return part.isFile()?part.length():0;}
  static final java.util.concurrent.ExecutorService closers=java.util.concurrent.Executors.newCachedThreadPool(task->{Thread t=new Thread(task,"app-update-close");t.setDaemon(true);t.setPriority(Thread.MIN_PRIORITY);return t;});
  static void disconnectLater(HttpURLConnection connection){closers.execute(connection::disconnect);}
  void cancel(){cancelled=true;factory.finished();HttpURLConnection connection=active;if(connection!=null)disconnectLater(connection);}
  void clear(){part.delete();meta.delete();new File(meta.getPath()+".tmp").delete();etag="";}
  void load()throws IOException {
    boolean valid=false;
    if(meta.isFile())try(InputStream in=new FileInputStream(meta)){Properties p=new Properties();p.load(in);valid=request.identity().equals(p.getProperty("identity"));String saved=p.getProperty("etag","");if(strong(saved))etag=saved;}catch(IOException ignored){}
    if(!valid||received()>request.bytes){clear();saveMeta();}
  }
  void saveMeta()throws IOException {
    Properties p=new Properties();p.setProperty("identity",request.identity());p.setProperty("etag",etag);File temp=new File(meta.getPath()+".tmp");
    try(FileOutputStream out=new FileOutputStream(temp)){p.store(out,"Release-bound update transfer");out.getFD().sync();}
    if(!temp.renameTo(meta)){temp.delete();throw new IOException("无法保存下载进度，请检查存储空间");}
  }
  static boolean strong(String value){if(value==null||value.length()<2||value.charAt(0)!='"'||value.charAt(value.length()-1)!='"')return false;for(int i=1;i<value.length()-1;i++){char c=value.charAt(i);if(c=='"'||c<0x21||c==0x7f)return false;}return true;}
  static boolean officialOrigin(String url){if(url==null)return false;Matcher release=Pattern.compile("https://github[.]com/"+AppUpdatePolicy.REPO+"/releases/download/v([0-9]+[.][0-9]+[.][0-9]+)-gecko/PocketChat-.*").matcher(url);return release.matches()&&AppUpdatePolicy.asset(release.group(1)).equals(url);}
  static boolean trusted(String url,String origin){try{URI u=new URI(url);if(!"https".equals(u.getScheme())||u.getUserInfo()!=null||u.getFragment()!=null||u.getPort()!=-1&&u.getPort()!=443)return false;String host=u.getHost();return "github.com".equals(host)?url.equals(origin):("release-assets.githubusercontent.com".equals(host)||"objects.githubusercontent.com".equals(host))&&u.getRawPath()!=null&&u.getRawPath().startsWith("/github-production-release-asset");}catch(Exception e){return false;}}
  void checkStopped(BooleanSupplier stopped)throws IOException {if(cancelled||stopped.getAsBoolean()||Thread.currentThread().isInterrupted())throw new Stopped();factory.check();}
  HttpURLConnection connect(long offset,BooleanSupplier stopped)throws IOException {
    String url=request.url;for(int redirects=0;redirects<5;redirects++){
      checkStopped(stopped);if(!trusted(url,request.url))throw new InvalidResponse("更新下载地址不受信任，已停止下载");
      HttpURLConnection connection=factory.open(url);active=connection;connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(20000);connection.setUseCaches(false);connection.setRequestProperty("Accept-Encoding","identity");connection.setRequestProperty("User-Agent","PocketChat-update");
      if(offset>0){connection.setRequestProperty("Range","bytes="+offset+"-");if(!etag.isEmpty())connection.setRequestProperty("If-Range",etag);}
      int code;try{checkStopped(stopped);code=connection.getResponseCode();checkStopped(stopped);}catch(IOException|RuntimeException error){connection.disconnect();active=null;throw error;}
      if(code==301||code==302||code==303||code==307||code==308){String location=connection.getHeaderField("Location");connection.disconnect();active=null;if(location==null)throw new InvalidResponse("更新服务器跳转异常");url=new URL(new URL(url),location).toString();continue;}
      return connection;
    }throw new InvalidResponse("更新服务器跳转次数过多");
  }
  static long number(String value)throws InvalidResponse {try{return Long.parseLong(value);}catch(Exception e){throw new InvalidResponse("更新服务器续传范围无效");}}
  void run(BooleanSupplier stopped)throws IOException {try{
    long sampleTime=System.nanoTime(),sampleBytes=received(),lastSync=sampleTime;long speed=0;
    if(listener!=null)listener.progress(received(),request.bytes,0);
    while(received()<request.bytes){
      checkStopped(stopped);long offset=received();HttpURLConnection connection=null;
      try{
        connection=connect(offset,stopped);int code=connection.getResponseCode();long expectedEnd=request.bytes-1;
        String encoding=connection.getHeaderField("Content-Encoding");if(encoding!=null&&!encoding.isEmpty()&&!"identity".equalsIgnoreCase(encoding))throw new InvalidResponse("更新服务器使用了无法续传的压缩格式");
        if(code==416){String range=connection.getHeaderField("Content-Range");if(offset==request.bytes&&("bytes */"+request.bytes).equals(range))return;throw new InvalidResponse("更新服务器拒绝续传范围，请重试");}
        if(code!=200&&code!=206)throw new IOException("更新下载暂不可用（"+code+"），已保留进度");
        long length=connection.getContentLengthLong();String responseEtag=connection.getHeaderField("ETag");
        if(code==206){
          Matcher range=Pattern.compile("bytes ([0-9]+)-([0-9]+)/([0-9]+)").matcher(String.valueOf(connection.getHeaderField("Content-Range")));
          if(!range.matches())throw new InvalidResponse("更新服务器续传范围无效");
          long start=number(range.group(1)),end=number(range.group(2)),total=number(range.group(3));
          if(start!=offset||total!=request.bytes||end<start||end>=total||length>=0&&length!=end-start+1)throw new InvalidResponse("更新服务器续传范围与下载进度不符");
          if(!etag.isEmpty()&&!etag.equals(responseEtag))throw new InvalidResponse("更新文件标识发生变化，已停止续传");
          expectedEnd=end;
        }else{
          if(connection.getHeaderField("Content-Range")!=null||length>=0&&length!=request.bytes)throw new InvalidResponse("更新服务器返回的文件大小不符");
          if(offset>0){try(FileOutputStream reset=new FileOutputStream(part)){reset.getFD().sync();}offset=0;sampleBytes=0;sampleTime=System.nanoTime();speed=0;}
          etag="";
        }
        if(strong(responseEtag))etag=responseEtag;saveMeta();
        long count=offset;
        try(InputStream in=connection.getInputStream();FileOutputStream out=new FileOutputStream(part,true)){
          byte[] buffer=new byte[65536];int read;
          try{while((read=in.read(buffer))!=-1){
            checkStopped(stopped);if(read==0)continue;if(read>expectedEnd+1-count)throw new InvalidResponse("更新服务器返回的数据超出声明范围");out.write(buffer,0,read);count+=read;
            long now=System.nanoTime();if(now-sampleTime>=500000000L){long next=(long)((count-sampleBytes)*1000000000.0/(now-sampleTime));speed=speed==0?next:(speed*3+next)/4;sampleBytes=count;sampleTime=now;if(listener!=null)listener.progress(count,request.bytes,speed);}
            if(now-lastSync>=1000000000L){out.getFD().sync();lastSync=now;}
          }}finally{out.getFD().sync();if(listener!=null)listener.progress(count,request.bytes,speed);}
        }
        checkStopped(stopped);if(count!=expectedEnd+1)throw new EOFException("网络中断，已保留进度，连接恢复后继续下载");
      }catch(IOException error){if(cancelled||stopped.getAsBoolean()||Thread.currentThread().isInterrupted())throw new Stopped();factory.check();throw error;}
      finally{HttpURLConnection opened=active;if(connection!=null)connection.disconnect();if(opened!=null&&opened!=connection)opened.disconnect();active=null;}
    }
    checkStopped(stopped);
  }finally{factory.finished();}}
}
