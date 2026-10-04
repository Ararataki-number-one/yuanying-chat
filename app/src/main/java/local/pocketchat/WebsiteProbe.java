package local.pocketchat;

import org.json.JSONObject;
import java.net.*;
import java.io.*;

/** No cookies, authentication, redirects or page-body downloads. */
final class WebsiteProbe {
  static JSONObject run(NativeNetwork n,String entry,int port,String target)throws Exception{
    String epoch=n.token;long first=-1,warm=-1;int code=0;
    for(int attempt=0;attempt<2;attempt++){
      n.maintenanceCheck();if(!epoch.equals(n.token))throw new InterruptedIOException("连接已变化");
      HttpURLConnection c=n.openProbeConnection(target,port);
      n.track(c);boolean reusable=false;
      try{
        c.setRequestMethod("HEAD");c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setInstanceFollowRedirects(false);c.setUseCaches(false);
        c.setRequestProperty("User-Agent","PocketChat-NetworkCheck/1.5.14");
        long began=android.os.SystemClock.elapsedRealtime();code=c.getResponseCode();long duration=Math.max(1,android.os.SystemClock.elapsedRealtime()-began);
        if(attempt==0)first=duration;else warm=duration;
        InputStream body=code<400?c.getInputStream():c.getErrorStream();if(body!=null){try(InputStream completed=body){while(completed.read()!=-1){}}}reusable=true;
      }finally{n.untrack(c);if(!reusable)c.disconnect();}
      n.maintenanceCheck();if(!epoch.equals(n.token))throw new InterruptedIOException("连接已变化");
      if(!NetworkOptimizationPolicy.websiteStatus(code).equals("ok"))break;
      if(n.routeBusy())break;
    }
    return J.obj("entry",entry,"at",System.currentTimeMillis(),"firstMs",first,"warmMs",warm,"code",code,"status",NetworkOptimizationPolicy.websiteStatus(code));
  }
  static String line(JSONObject reading,long now){
    long at=reading.optLong("at");if(at<=0)return "网站响应未测";if(now<at-60000||now-at>300000)return "网站响应待更新";
    String status=reading.optString("status");if(status.equals("ok"))return "首响应 "+reading.optLong("firstMs")+" ms"+(reading.optLong("warmMs")>0?" · 复测 "+reading.optLong("warmMs")+" ms":"");
    return status.equals("restricted")?"网站限制检测（"+reading.optInt("code")+"）":status.equals("unsupported")?"网站不支持此检测":status.equals("http-error")?"网站返回 "+reading.optInt("code"):"网站检测未完成";
  }
}
