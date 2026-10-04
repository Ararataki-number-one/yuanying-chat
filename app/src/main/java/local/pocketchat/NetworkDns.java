package local.pocketchat;

import android.content.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.nio.charset.StandardCharsets;

/** Route-scoped DoH measurements; a new choice never reloads a healthy core. */
final class NetworkDns {
  static final String[] SERVERS={"https://dns.alidns.com/dns-query","https://doh.pub/dns-query","https://cloudflare-dns.com/dns-query","https://dns.google/dns-query"};
  static final long TTL=86400000L;
  final SharedPreferences prefs;JSONObject samples;String scope,selected;
  NetworkDns(Context c){prefs=c.getSharedPreferences("network-dns",0);scope=prefs.getString("scope","");selected=prefs.getString("selected",SERVERS[0]);samples=J.parse(prefs.getString("samples","{}"));}
  synchronized void configure(String value){if(value.equals(scope))return;scope=value;selected=SERVERS[0];samples=new JSONObject();save();}
  synchronized String next(long now){for(String server:SERVERS){JSONObject s=samples.optJSONObject(server);if(s==null||now-s.optLong("at")>=TTL||now<s.optLong("at")-60000)return server;}return "";}
  synchronized void record(String server,int delay,long now){if(!Arrays.asList(SERVERS).contains(server))return;NetworkCatalog.put(samples,server,J.obj("ms",delay,"at",now));if(next(now).isEmpty()){String best="";int time=Integer.MAX_VALUE;for(String name:SERVERS){JSONObject s=samples.optJSONObject(name);int d=s.optInt("ms",-1);if(d>0&&d<time){best=name;time=d;}}if(!best.isEmpty())selected=best;}save();}
  synchronized String primary(long now){JSONObject s=samples.optJSONObject(selected);return s!=null&&s.optInt("ms")>0&&now-s.optLong("at")<TTL&&now>=s.optLong("at")-60000?selected:SERVERS[0];}
  synchronized String backup(long now){for(String server:SERVERS)if(!server.equals(primary(now)))return server;return SERVERS[1];}
  void save(){prefs.edit().putString("scope",scope).putString("selected",selected).putString("samples",samples.toString()).apply();}
  static byte[] query(){try{ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);out.writeShort(0x5043);out.writeShort(0x0100);out.writeShort(1);out.writeShort(0);out.writeShort(0);out.writeShort(0);for(String label:new String[]{"chatgpt","com"}){byte[] raw=label.getBytes(StandardCharsets.US_ASCII);out.writeByte(raw.length);out.write(raw);}out.writeByte(0);out.writeShort(1);out.writeShort(1);return bytes.toByteArray();}catch(IOException impossible){throw new IllegalStateException(impossible);}}
  static boolean valid(byte[] response){byte[] q=query();if(response.length<q.length+12||response[0]!=q[0]||response[1]!=q[1]||(response[2]&0x80)==0||(response[3]&0x0f)!=0||(response[2]&2)!=0||response[4]!=0||response[5]!=1||((response[6]&255)<<8|(response[7]&255))==0)return false;for(int i=12;i<q.length;i++)if(response[i]!=q[i])return false;
    int pos=q.length,count=((response[6]&255)<<8)|(response[7]&255);
    for(int record=0;record<Math.min(count,64);record++){
      while(pos<response.length){int length=response[pos++]&255;if(length==0)break;if((length&0xc0)==0xc0){if(pos>=response.length)return false;int pointer=((length&63)<<8)|(response[pos++]&255);if(pointer>=response.length)return false;break;}if(length>63||pos+length>=response.length)return false;pos+=length;}
      if(pos+10>response.length)return false;int type=((response[pos]&255)<<8)|(response[pos+1]&255),cls=((response[pos+2]&255)<<8)|(response[pos+3]&255),length=((response[pos+8]&255)<<8)|(response[pos+9]&255);pos+=10;if(pos+length>response.length)return false;if(type==1&&cls==1&&length==4)return true;pos+=length;
    }return false;}
  static int measure(NativeNetwork n,String server)throws Exception{
    n.maintenanceCheck();String epoch=n.token;
    String target=server+"?dns="+Base64.getUrlEncoder().withoutPadding().encodeToString(query());
    HttpURLConnection c=n.openProbeConnection(target,n.proxyPort);n.track(c);boolean reusable=false;
    try{c.setConnectTimeout(2000);c.setReadTimeout(2000);c.setUseCaches(false);c.setInstanceFollowRedirects(false);c.setRequestProperty("Accept","application/dns-message");long began=android.os.SystemClock.elapsedRealtime();if(c.getResponseCode()!=200)return -1;byte[] answer;try(InputStream in=c.getInputStream()){answer=J.read(in,4096);}reusable=true;n.maintenanceCheck();if(!epoch.equals(n.token)||!valid(answer))return -1;return (int)Math.max(1,android.os.SystemClock.elapsedRealtime()-began);}finally{n.untrack(c);if(!reusable)c.disconnect();}
  }
}
