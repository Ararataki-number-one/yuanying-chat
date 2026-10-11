package local.pocketchat;

import android.os.Looper;
import java.util.concurrent.atomic.AtomicLong;
import org.json.JSONArray;
import org.json.JSONObject;

/** Local regression counters; completely disabled during ordinary application use. */
final class UiPerfStats {
  static volatile boolean enabled;
  static final AtomicLong mainSealedReads=new AtomicLong(),mainSealedWrites=new AtomicLong(),mainCatalogReads=new AtomicLong(),mainHeartbeatWrites=new AtomicLong();
  static final AtomicLong chromeUpdates=new AtomicLong(),chromeTextChanges=new AtomicLong(),chromeBackgroundChanges=new AtomicLong(),metricsRefreshes=new AtomicLong(),starDraws=new AtomicLong();
  static JSONArray mainIoCalls=new JSONArray();
  static void main(AtomicLong counter){if(enabled&&Looper.myLooper()==Looper.getMainLooper()){
    long count=counter.incrementAndGet();if(count>2)return;
    String kind=counter==mainSealedReads?"sealedRead":counter==mainSealedWrites?"sealedWrite":counter==mainCatalogReads?"catalogRead":"heartbeatWrite";
    JSONArray stack=new JSONArray();StackTraceElement[] frames=new Throwable().getStackTrace();for(int i=1;i<Math.min(frames.length,17);i++)stack.put(frames[i].toString());
    mainIoCalls.put(J.obj("kind",kind,"stack",stack));
  }}
  static void sealedRead(){main(mainSealedReads);}
  static void sealedWrite(){main(mainSealedWrites);}
  static void catalogRead(){main(mainCatalogReads);}
  static void heartbeatWrite(){main(mainHeartbeatWrites);}
  static void chromeUpdate(){if(enabled)chromeUpdates.incrementAndGet();}
  static void textChange(){if(enabled)chromeTextChanges.incrementAndGet();}
  static void backgroundChange(){if(enabled)chromeBackgroundChanges.incrementAndGet();}
  static void metricsRefresh(){if(enabled)metricsRefreshes.incrementAndGet();}
  static void starDraw(){if(enabled)starDraws.incrementAndGet();}
  static void begin(){enabled=false;mainIoCalls=new JSONArray();for(AtomicLong value:new AtomicLong[]{mainSealedReads,mainSealedWrites,mainCatalogReads,mainHeartbeatWrites,chromeUpdates,chromeTextChanges,chromeBackgroundChanges,metricsRefreshes,starDraws})value.set(0);enabled=true;}
  static JSONObject snapshot(){return J.obj("mainSealedReads",mainSealedReads.get(),"mainSealedWrites",mainSealedWrites.get(),"mainCatalogReads",mainCatalogReads.get(),"mainHeartbeatWrites",mainHeartbeatWrites.get(),"chromeUpdates",chromeUpdates.get(),"chromeTextChanges",chromeTextChanges.get(),"chromeBackgroundChanges",chromeBackgroundChanges.get(),"metricsRefreshes",metricsRefreshes.get(),"starDraws",starDraws.get(),"mainIoCalls",mainIoCalls);}
  static JSONObject end(){enabled=false;return snapshot();}
}
