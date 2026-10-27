package local.pocketchat;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import java.io.IOException;
import java.net.InetAddress;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only TUN sink. It records IP headers and never forwards a byte. */
public final class NetworkProtectionFixtureVpnService extends VpnService {
  private static final Object STATE=new Object();
  private static String ownerRun="",ownerSource="",mode="",error="",lastRejected="";
  private static long generation,startedAt,stoppedAt,packets,bytes,ipv4Packets,ipv6Packets,targetIpv4Packets;
  private static boolean running,fdCloseSucceeded;
  private static JSONArray events=new JSONArray(),headers=new JSONArray(),configuredRoutes=new JSONArray();
  private static int eventsDropped,headersDropped;
  private Tunnel active;

  static JSONObject snapshot(){synchronized(STATE){
    // JSON cloning keeps the service's bounded mutable records out of callers.
    return J.parse(J.obj("running",running,"tunEstablished",running,"runNonce",ownerRun,
      "sourceCommit",ownerSource,"mode",mode,"generation",generation,"startedAt",startedAt,
      "stoppedAt",stoppedAt,"packetCount",packets,"packetBytes",bytes,"ipv4Packets",ipv4Packets,
      "ipv6Packets",ipv6Packets,"targetIpv4Packets",targetIpv4Packets,"fdCloseSucceeded",fdCloseSucceeded,
      "configuredRoutes",configuredRoutes,"error",error,"lastRejected",lastRejected,
      "ipHeaders",headers,"headersDropped",headersDropped,"events",events,"eventsDropped",eventsDropped,
      "forwardsTraffic",false,"scope","Real test-package TUN sink; no CM/VPN coverage or public IPv6 acceptance inferred").toString());
  }}
  private static void event(String kind,String detail){
    if(events.length()<48)events.put(J.obj("kind",kind,"detail",detail,"at",SystemClock.elapsedRealtime(),"generation",generation));
    else eventsDropped++;
  }
  private static boolean valid(String run,String source){return run!=null&&run.matches("[0-9a-f]{32}")&&source!=null&&source.matches("[0-9a-f]{40}");}
  private static void rejected(String reason){synchronized(STATE){lastRejected=reason;event("rejected",reason);}}

  @Override public int onStartCommand(Intent intent,int flags,int startId){
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    if(intent==null){stopSelf(startId);return START_NOT_STICKY;}
    String run=intent.getStringExtra("runNonce"),source=intent.getStringExtra("sourceCommit"),action=intent.getAction();
    if(!valid(run,source)){rejected("Exact run/source required");if(active==null)stopSelf(startId);return START_NOT_STICKY;}
    if("STOP".equals(action)){
      synchronized(STATE){if(!run.equals(ownerRun)||!source.equals(ownerSource)||intent.getLongExtra("generation",-1)!=generation){rejected("STOP owner/generation mismatch");return START_NOT_STICKY;}}
      closeTunnel("requested-stop");stopSelf(startId);return START_NOT_STICKY;
    }
    String requested=intent.getStringExtra("mode");
    if(!"START".equals(action)||!("full".equals(requested)||"split".equals(requested))){rejected("Exact START mode required");return START_NOT_STICKY;}
    synchronized(STATE){if(!ownerRun.isEmpty()&&(!run.equals(ownerRun)||!source.equals(ownerSource))){rejected("START owner mismatch");return START_NOT_STICKY;}}
    try{beginTunnel(run,source,requested);}catch(Exception failure){
      synchronized(STATE){error=failure.getClass().getSimpleName()+": "+String.valueOf(failure.getMessage());event("start-error",error);}
      closeTunnel("start-error");stopSelf(startId);
    }
    return START_NOT_STICKY;
  }

  private synchronized void beginTunnel(String run,String source,String requested)throws Exception{
    closeTunnel("same-owner-replacement");
    final long serial;
    synchronized(STATE){
      ownerRun=run;ownerSource=source;mode=requested;serial=++generation;running=false;
      startedAt=SystemClock.elapsedRealtime();stoppedAt=0;packets=bytes=ipv4Packets=ipv6Packets=targetIpv4Packets=0;
      error=lastRejected="";fdCloseSucceeded=false;headers=new JSONArray();headersDropped=0;
      configuredRoutes=new JSONArray().put("full".equals(requested)?"0.0.0.0/0":"198.18.0.0/15");
      if("full".equals(requested))configuredRoutes.put("::/0");event("starting",requested);
    }
    if(prepare(this)!=null)throw new IllegalStateException("Test VPN consent not prepared");
    Builder builder=new Builder().setSession("PocketChat controlled VPN "+run.substring(0,8))
      .setMtu(1280).setBlocking(false).addAddress("10.77.0.2",32).addAllowedApplication(getPackageName());
    if("full".equals(requested))builder.addRoute("0.0.0.0",0).addAddress("fd77::2",128).addRoute("::",0);
    else builder.addRoute("198.18.0.0",15);
    ParcelFileDescriptor descriptor=builder.establish();
    if(descriptor==null)throw new IOException("VPN establish returned null");
    Tunnel tunnel=new Tunnel(descriptor,serial);active=tunnel;
    synchronized(STATE){running=true;event("tun-established",requested);}
    tunnel.reader=new Thread(()->read(tunnel),"protection-vpn-sink-"+serial);tunnel.reader.start();
  }

  private void read(Tunnel tunnel){
    byte[] data=new byte[32768];
    while(!tunnel.closed){
      try{int count=Os.read(tunnel.descriptor.getFileDescriptor(),data,0,data.length);if(count>0)record(tunnel,data,count);else Thread.sleep(20);}
      catch(ErrnoException failure){
        if(tunnel.closed)break;
        if(failure.errno==OsConstants.EAGAIN||failure.errno==OsConstants.EINTR){try{Thread.sleep(20);}catch(InterruptedException end){Thread.currentThread().interrupt();break;}continue;}
        synchronized(STATE){if(tunnel.serial==generation){error="TUN read errno="+failure.errno;event("read-error",error);}}
        closeTunnel("read-error",tunnel);break;
      }catch(IOException failure){
        if(tunnel.closed)break;
        synchronized(STATE){if(tunnel.serial==generation){error="TUN read: "+failure.getClass().getSimpleName();event("read-error",error);}}
        closeTunnel("read-error",tunnel);break;
      }catch(RuntimeException failure){
        if(tunnel.closed)break;
        synchronized(STATE){if(tunnel.serial==generation){error="TUN descriptor: "+failure.getClass().getSimpleName();event("read-error",error);}}
        closeTunnel("read-error",tunnel);break;
      }catch(InterruptedException end){Thread.currentThread().interrupt();break;}
    }
  }
  private static void record(Tunnel tunnel,byte[] data,int count){synchronized(STATE){
    if(tunnel.closed||tunnel.serial!=generation||!running)return;
    packets++;bytes+=count;int version=(data[0]>>>4)&15;
    if(version==4)ipv4Packets++;else if(version==6)ipv6Packets++;
    if(version==4&&count>=20&&(data[16]&255)==10&&(data[17]&255)==0&&(data[18]&255)==2&&(data[19]&255)==2)targetIpv4Packets++;
    if(headers.length()>=16){headersDropped++;return;}
    try{
      int address=version==4&&count>=20?12:version==6&&count>=40?8:-1,length=version==4?4:16;
      if(address<0)return;
      String from=InetAddress.getByAddress(Arrays.copyOfRange(data,address,address+length)).getHostAddress();
      String to=InetAddress.getByAddress(Arrays.copyOfRange(data,address+length,address+length*2)).getHostAddress();
      int protocol=data[version==4?9:6]&255,offset=version==4?(data[0]&15)*4:40;
      boolean ports=(protocol==6||protocol==17)&&offset>=(version==4?20:40)&&count>=offset+4
        &&(version!=4||((data[6]&31)==0&&data[7]==0));
      headers.put(J.obj("version",version,"from",from,"to",to,"bytes",count,"nextHeader",protocol,
        "sourcePort",ports?((data[offset]&255)<<8)|(data[offset+1]&255):-1,
        "destinationPort",ports?((data[offset+2]&255)<<8)|(data[offset+3]&255):-1,
        "at",SystemClock.elapsedRealtime()));
    }catch(Exception malformed){event("header-unavailable",malformed.getClass().getSimpleName());}
  }}

  private synchronized void closeTunnel(String reason){closeTunnel(reason,null);}
  private synchronized void closeTunnel(String reason,Tunnel expected){
    if(expected!=null&&active!=expected)return;
    Tunnel tunnel=active;if(tunnel==null)return;active=null;tunnel.closed=true;
    boolean closed=false;String closeError="";
    try{tunnel.descriptor.close();closed=true;}catch(IOException failure){closeError="TUN close: "+failure.getClass().getSimpleName();}
    if(tunnel.reader!=null)tunnel.reader.interrupt();
    synchronized(STATE){if(tunnel.serial==generation){running=false;stoppedAt=SystemClock.elapsedRealtime();fdCloseSucceeded=closed;if(!closeError.isEmpty())error=closeError;event("tun-closed",reason);}}
  }
  @Override public void onRevoke(){closeTunnel("system-revoke");super.onRevoke();}
  @Override public void onDestroy(){closeTunnel("service-destroy");super.onDestroy();}
  private static final class Tunnel {
    final ParcelFileDescriptor descriptor;final long serial;volatile boolean closed;Thread reader;
    Tunnel(ParcelFileDescriptor descriptor,long serial){this.descriptor=descriptor;this.serial=serial;}
  }
}
