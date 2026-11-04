package local.pocketchat;

import java.io.*;
import java.net.*;

/** A bounded GET on one frozen Chromium route; never selects a replacement. */
final class BrowserDownloadTransfer {
  static final long MAX_BYTES=512L*1024*1024,RESERVE_BYTES=32L*1024*1024;
  interface Route {boolean current();HttpURLConnection open(URL target)throws IOException;}
  interface Cookies {String forUrl(String target)throws IOException;}
  interface Progress {void update(long received,long total);}
  static final class Result {
    final File file;final String url,disposition,mime;final long bytes;
    Result(File file,String url,String disposition,String mime,long bytes){this.file=file;this.url=url;this.disposition=disposition;this.mime=mime;this.bytes=bytes;}
  }
  volatile boolean cancelled;
  volatile HttpURLConnection active;
  void cancel(){cancelled=true;HttpURLConnection connection=active;if(connection!=null){Thread closer=new Thread(connection::disconnect,"browser-download-cancel");closer.setDaemon(true);closer.start();}}
  void check(Route route)throws IOException {if(cancelled||Thread.currentThread().isInterrupted())throw new IOException("下载已取消");if(!route.current())throw new IOException("下载连接已变化，文件未保存，请恢复连接后重新下载");}
  static URL address(String raw)throws IOException {
    try{
      if(raw==null||raw.length()>16384||raw.matches("(?s).*[\\x00-\\x20\\\\].*"))throw new IOException("下载地址无效");
      if(!BrowserAddressPolicy.allowed(raw))throw new IOException("仅支持公共 HTTP 或 HTTPS 下载地址");
      URI uri=new URI(raw);String scheme=uri.getScheme();
      if(uri.isOpaque()||!("https".equalsIgnoreCase(scheme)||"http".equalsIgnoreCase(scheme))||uri.getHost()==null||uri.getHost().isEmpty()||uri.getUserInfo()!=null||uri.getPort()>65535)throw new IOException("此下载地址无法直接保存");
      return uri.toURL();
    }catch(URISyntaxException|IllegalArgumentException error){throw new IOException("下载地址无效",error);}
  }
  static String header(String value,int limit)throws IOException {if(value==null)return "";if(value.length()>limit||value.indexOf('\r')>=0||value.indexOf('\n')>=0||value.indexOf('\0')>=0)throw new IOException("下载请求信息无效");return value;}
  Result fetch(String initial,String agent,String fallbackDisposition,String fallbackMime,long advertised,File cache,Route route,Cookies cookies,Progress progress)throws IOException {
    if(advertised>MAX_BYTES)throw new IOException("文件超过 512 MB 下载限额");
    String ua=header(agent,8192);URL target=address(initial);File partial=null;
    try{
      for(int redirects=0;redirects<=5;redirects++){
        check(route);HttpURLConnection connection=route.open(target);active=connection;
        if(connection==null)throw new IOException("下载连接不可用");
        try{
          check(route);connection.setRequestMethod("GET");connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(20000);connection.setUseCaches(false);
          connection.setRequestProperty("Accept-Encoding","identity");if(!ua.isEmpty())connection.setRequestProperty("User-Agent",ua);
          String cookie=header(cookies.forUrl(target.toExternalForm()),65536);if(!cookie.isEmpty())connection.setRequestProperty("Cookie",cookie);
          check(route);int status=connection.getResponseCode();check(route);
          if(status==301||status==302||status==303||status==307||status==308){
            if(redirects==5)throw new IOException("下载重定向次数过多");
            String location=connection.getHeaderField("Location");if(location==null||location.isEmpty())throw new IOException("下载重定向地址缺失");
            URL next=address(new URL(target,location).toExternalForm());
            if("https".equalsIgnoreCase(target.getProtocol())&&!"https".equalsIgnoreCase(next.getProtocol()))throw new IOException("下载重定向降低了连接安全性，文件未保存");
            target=next;continue;
          }
          if(status<200||status>=300||status==206)throw new IOException("网页未提供完整文件（HTTP "+status+"）");
          String encoding=connection.getHeaderField("Content-Encoding");if(encoding!=null&&!encoding.isEmpty()&&!"identity".equalsIgnoreCase(encoding))throw new IOException("该文件的传输编码暂不支持，请使用外部浏览器下载");
          long total=connection.getContentLengthLong();if(total>MAX_BYTES)throw new IOException("文件超过 512 MB 下载限额");
          if(cache.getUsableSpace()<RESERVE_BYTES+Math.max(0,total))throw new IOException("可用存储空间不足");
          String disposition=connection.getHeaderField("Content-Disposition");if(disposition==null||disposition.isEmpty())disposition=fallbackDisposition;disposition=header(disposition,16384);
          String mime=connection.getContentType();if(mime==null||mime.isEmpty())mime=fallbackMime;if(mime==null||!mime.split(";",2)[0].trim().matches("[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+"))mime="application/octet-stream";else mime=mime.split(";",2)[0].trim();
          partial=File.createTempFile("browser-download-",".part",cache);long received=0,reportedAt=0;
          try(InputStream input=connection.getInputStream();FileOutputStream output=new FileOutputStream(partial)){
            byte[] buffer=new byte[65536];int count;
            while((count=input.read(buffer))!=-1){
              check(route);if(received+count>MAX_BYTES)throw new IOException("文件超过 512 MB 下载限额");if(cache.getUsableSpace()<RESERVE_BYTES)throw new IOException("可用存储空间不足");
              output.write(buffer,0,count);received+=count;long now=System.nanoTime();if(now-reportedAt>=400000000L){reportedAt=now;progress.update(received,total);}
            }
            check(route);output.getFD().sync();
          }
          if(total>=0&&received!=total)throw new IOException("文件未下载完整，未保存");
          check(route);progress.update(received,total);return new Result(partial,target.toExternalForm(),disposition,mime,received);
        }finally{connection.disconnect();if(active==connection)active=null;}
      }
      throw new IOException("下载重定向次数过多");
    }catch(IOException|RuntimeException error){if(partial!=null)partial.delete();throw error;}
  }
}
