package local.pocketchat;

import android.net.Network;
import android.os.SystemClock;
import java.io.*;
import java.net.*;

/** A small, unauthenticated HEAD over the exact guarded route selected by the caller. */
final class RouteLatency {
  interface Gate{void check()throws IOException;}
  static int measure(String target,Proxy proxy,Network bound,Gate gate)throws IOException{
    gate.check();long began=SystemClock.elapsedRealtime();URL url=new URL(target);
    HttpURLConnection c=(HttpURLConnection)(bound==null?url.openConnection(proxy):bound.openConnection(url,proxy));
    c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setRequestMethod("HEAD");c.setInstanceFollowRedirects(false);c.setUseCaches(false);
    c.setRequestProperty("User-Agent","PocketChat-NetworkCheck");
    try{gate.check();int code=c.getResponseCode();gate.check();if(code!=204)throw new IOException("线路探测未通过");return (int)Math.min(Integer.MAX_VALUE,Math.max(1,SystemClock.elapsedRealtime()-began));}
    finally{c.disconnect();}
  }
}
