package local.pocketchat;

import android.app.ActivityManager;
import android.content.Context;
import android.os.SystemClock;

/** Fresh platform pressure controls new optional work, never eviction or a capacity claim. */
final class ResourcePressureController {
  static final long FRESH_MS=5000;
  static final String DEFERRED_MESSAGE="手机内存暂时紧张，当前环境尚未打开。关闭其他应用后可重试；已打开的环境和进行中的任务会保留。";
  static final class MemorySample {
    final boolean known,lowMemory;final long availableBytes,totalBytes,thresholdBytes,sampledAt;
    final String source;
    MemorySample(boolean known,boolean low,long available,long total,long threshold,long at,String source){
      this.known=known;lowMemory=low;availableBytes=available;totalBytes=total;thresholdBytes=threshold;sampledAt=at;this.source=source;
    }
    static MemorySample unknown(long now){return new MemorySample(false,false,-1,-1,-1,now,"unavailable");}
    boolean fresh(long now){return known&&sampledAt>=0&&now>=sampledAt&&now-sampledAt<=FRESH_MS&&availableBytes>=0&&totalBytes>0&&availableBytes<=totalBytes&&thresholdBytes>=0;}
  }
  enum Admission { EXISTING, RECOVERY, START, DEFER }
  final Context context;MemorySample last;long samples,attempts,deferred,created;
  ResourcePressureController(Context context){this.context=context;}
  MemorySample sample(){last=read(context);samples++;return last;}
  static MemorySample read(Context context){
    long now=SystemClock.elapsedRealtime();
    try{
      ActivityManager manager=context.getSystemService(ActivityManager.class);
      if(manager==null)return MemorySample.unknown(now);
      ActivityManager.MemoryInfo info=new ActivityManager.MemoryInfo();manager.getMemoryInfo(info);
      MemorySample value=new MemorySample(true,info.lowMemory,info.availMem,info.totalMem,info.threshold,now,"android-ActivityManager.MemoryInfo");
      return value.fresh(now)?value:MemorySample.unknown(now);
    }catch(RuntimeException unavailable){return MemorySample.unknown(now);}
  }
  static Admission admission(boolean existing,boolean recovery,MemorySample memory,long now){
    if(existing)return Admission.EXISTING;
    if(recovery)return Admission.RECOVERY;
    return memory!=null&&memory.fresh(now)&&memory.lowMemory?Admission.DEFER:Admission.START;
  }
  static boolean automaticWarmup(MemorySample memory,long now){return memory!=null&&memory.fresh(now)&&!memory.lowMemory;}
  Admission request(boolean existing,boolean recovery,MemorySample memory){
    last=memory;attempts++;Admission result=admission(existing,recovery,memory,SystemClock.elapsedRealtime());if(result==Admission.DEFER)deferred++;return result;
  }
  void runtimeCreated(){created++;}
}
