package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.net.*;

/** HTTPS source retrieval only. This never changes a browser route or starts a proxy core. */
final class ExitSubscriptionFetcher {
  static byte[] read(Context profile,String address)throws IOException{
    HttpURLConnection connection=null;
    try{
      URI uri=new URI(address);if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||uri.getRawUserInfo()!=null||uri.getRawFragment()!=null)throw new IOException("出口订阅需要 HTTPS 地址");
      NativeNetwork network=NativeNetwork.get(profile);boolean internal="internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external"));
      // Reuse an already verified app route when present. Initial source download has
      // the same explicit HTTPS bootstrap behavior as entry subscriptions; it is
      // never a direct fallback for ChatGPT or other browser requests.
      Proxy proxy=internal&&network.ready&&network.coreAlive()?new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",network.proxyPort)):Proxy.NO_PROXY;
      connection=(HttpURLConnection)uri.toURL().openConnection(proxy);connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(20000);connection.setRequestProperty("User-Agent","PocketChat-ExitSubscription/1");connection.setRequestProperty("Accept","application/yaml, text/yaml, text/plain");connection.setUseCaches(false);
      if(connection.getResponseCode()!=200)throw new IOException("出口订阅返回失败或重定向");long size=connection.getContentLengthLong();if(size>ExitSubscriptionParser.MAX_BYTES)throw new IOException("出口订阅超过 1 MiB");
      try(InputStream input=connection.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int length;while((length=input.read(buffer))!=-1){if(bytes.size()+length>ExitSubscriptionParser.MAX_BYTES)throw new IOException("出口订阅超过 1 MiB");bytes.write(buffer,0,length);}return bytes.toByteArray();}
    }catch(Exception failure){throw new IOException("出口订阅读取失败；旧缓存和当前连接已保留");}finally{if(connection!=null)connection.disconnect();}
  }
}
