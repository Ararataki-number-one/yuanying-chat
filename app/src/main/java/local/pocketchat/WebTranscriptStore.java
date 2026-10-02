package local.pocketchat;

import java.util.concurrent.*;
import java.util.*;
import org.json.*;

/** Coalesces whole-history serialization and SQLite writes off the Android UI thread. */
final class WebTranscriptStore {
  final ChatSession session;
  final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"WebTranscriptStore");t.setPriority(Thread.MIN_PRIORITY);return t;});
  volatile String currentUrl="";volatile long generation,nativeRevision;
  Snapshot latest;boolean scheduled,writing,urgent;
  final LinkedHashMap<String,Snapshot> queued=new LinkedHashMap<>();
  final ConcurrentHashMap<String,Long> versions=new ConcurrentHashMap<>();
  String savedUrl="",savedSerial="";long savedNativeRevision=-1;
  static final class Snapshot {final String url;final JSONArray entries;final long generation,nativeRevision;Snapshot(String url,JSONArray entries,long generation,long nativeRevision){this.url=url;this.entries=entries;this.generation=generation;this.nativeRevision=nativeRevision;}}
  WebTranscriptStore(ChatSession session){this.session=session;}
  final Runnable drain=()->drain();
  void offer(String url,JSONArray entries){currentUrl=url;long revision=++generation;versions.put(url,revision);queued.put(url,new Snapshot(url,entries,revision,nativeRevision));updateLatest();schedule(2000);}
  void current(String url){currentUrl=url;}
  void updateLatest(){latest=queued.isEmpty()?null:queued.values().iterator().next();}
  boolean current(Snapshot snapshot){Long value=versions.get(snapshot.url);return value!=null&&value==snapshot.generation;}
  void nativeSnapshot(String url){currentUrl=url;versions.put(url,++generation);nativeRevision++;queued.remove(url);updateLatest();if(scheduled&&latest==null){session.handler.removeCallbacks(drain);scheduled=false;}}
  void loadIfNeeded(){String url=session.conversation;if(session.entries.length()>0||!MainActivity.chatUrl(url)||!android.net.Uri.parse(url).getPath().contains("/c/"))return;
    worker.execute(()->{JSONArray saved=session.cache.messages(url);session.handler.post(()->{if(session.entries.length()==0&&url.equals(session.conversation)&&saved.length()>0){session.entries=saved;session.showingCache=session.navigating||session.navigationFailed||session.offline;session.changed();}});});
  }
  void flush(){urgent=true;if(scheduled){session.handler.removeCallbacks(drain);scheduled=false;}schedule(0);}
  void schedule(long delay){if(scheduled||writing||latest==null)return;scheduled=true;session.handler.postDelayed(drain,delay);}
  void drain(){scheduled=false;if(writing||latest==null)return;Snapshot snapshot=latest;queued.remove(snapshot.url);updateLatest();writing=true;urgent=false;
    worker.execute(()->{try{
      String serial=snapshot.entries.toString();
      if(current(snapshot)&&(!snapshot.url.equals(savedUrl)||!serial.equals(savedSerial)||snapshot.nativeRevision!=savedNativeRevision)){
        String title="未命名对话";for(int i=0;i<snapshot.entries.length();i++){JSONObject row=snapshot.entries.optJSONObject(i);if(row!=null&&"user".equals(row.optString("role"))){title=row.optString("text").replaceAll("\\s+"," ").trim();if(title.length()>80)title=title.substring(0,80)+"…";break;}}
        synchronized(session.cache){if(!current(snapshot))return;if(snapshot.entries.length()>0)session.cache.saveSerializedMessages(snapshot.url,serial,title);}
        session.handler.post(()->{if(current(snapshot)&&snapshot.url.equals(currentUrl)&&snapshot.url.equals(session.conversation))session.prefs.edit().putString("transcript",serial).putString("conversation",snapshot.url).apply();});
        savedUrl=snapshot.url;savedSerial=serial;savedNativeRevision=snapshot.nativeRevision;
      }
    }catch(Exception e){session.handler.post(()->session.setStatus("本地记录保存失败，请保留原网页核对"));}
    finally{session.handler.post(()->{writing=false;if(latest!=null)schedule(urgent?0:2000);});}});
  }
}
