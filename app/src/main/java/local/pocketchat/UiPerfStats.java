package local.pocketchat;

import android.os.Looper;
import java.util.concurrent.atomic.AtomicLong;
import org.json.JSONObject;

/** Local regression counters; completely disabled during ordinary application use. */
final class UiPerfStats {
  static volatile boolean enabled;
  static final AtomicLong mainSealedReads=new AtomicLong(),mainSealedWrites=new AtomicLong(),mainCatalogReads=new AtomicLong(),mainHeartbeatWrites=new AtomicLong();
  static final AtomicLong chromeUpdates=new AtomicLong(),chromeTextChanges=new AtomicLong(),chromeBackgroundChanges=new AtomicLong(),metricsRefreshes=new AtomicLong(),starDraws=new AtomicLong();
  static void main(AtomicLong counter){if(enabled&&Looper.myLooper()==Looper.getMainLooper())counter.incrementAndGet();}
  static void sealedRead(){main(mainSealedReads);}
  static void sealedWrite(){main(mainSealedWrites);}
  static void catalogRead(){main(mainCatalogReads);}
  static void heartbeatWrite(){main(mainHeartbeatWrites);}
  static void chromeUpdate(){if(enabled)chromeUpdates.incrementAndGet();}
  static void textChange(){if(enabled)chromeTextChanges.incrementAndGet();}
  static void backgroundChange(){if(enabled)chromeBackgroundChanges.incrementAndGet();}
  static void metricsRefresh(){if(enabled)metricsRefreshes.incrementAndGet();}
  static void starDraw(){if(enabled)starDraws.incrementAndGet();}
  static void begin(){enabled=false;for(AtomicLong value:new AtomicLong[]{mainSealedReads,mainSealedWrites,mainCatalogReads,mainHeartbeatWrites,chromeUpdates,chromeTextChanges,chromeBackgroundChanges,metricsRefreshes,starDraws})value.set(0);enabled=true;}
  static JSONObject snapshot(){return J.obj("mainSealedReads",mainSealedReads.get(),"mainSealedWrites",mainSealedWrites.get(),"mainCatalogReads",mainCatalogReads.get(),"mainHeartbeatWrites",mainHeartbeatWrites.get(),"chromeUpdates",chromeUpdates.get(),"chromeTextChanges",chromeTextChanges.get(),"chromeBackgroundChanges",chromeBackgroundChanges.get(),"metricsRefreshes",metricsRefreshes.get(),"starDraws",starDraws.get());}
  static JSONObject end(){enabled=false;return snapshot();}
}
