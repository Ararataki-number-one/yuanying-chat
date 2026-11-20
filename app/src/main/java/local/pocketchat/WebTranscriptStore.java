package local.pocketchat;

import java.util.concurrent.*;
import java.util.*;
import org.json.*;

/** Coalesces whole-history serialization and SQLite writes off the Android UI thread.
 * SQLite owns transcript content; preferences retain only the current conversation cursor. */
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
  private static boolean conversationUrl(String url){return MainActivity.chatUrl(url)&&android.net.Uri.parse(url).getPath().contains("/c/");}
  void loadIfNeeded(){String url=session.conversation;if(session.entries.length()>0||!conversationUrl(url))return;
    worker.execute(()->{JSONArray saved=session.cache.messages(url);session.handler.post(()->{if(session.entries.length()==0&&url.equals(session.conversation)&&saved.length()>0){session.entries=saved;session.showingCache=session.navigating||session.navigationFailed||session.offline;session.changed();}});});
  }
  void flush(){urgent=true;if(scheduled){session.handler.removeCallbacks(drain);scheduled=false;}schedule(0);}
  void schedule(long delay){if(scheduled||writing||latest==null)return;scheduled=true;session.handler.postDelayed(drain,delay);}
  void drain(){scheduled=false;if(writing||latest==null)return;Snapshot snapshot=latest;queued.remove(snapshot.url);updateLatest();writing=true;urgent=false;
    worker.execute(()->{try{
      if(!current(snapshot))return;
      String serial=snapshot.entries.toString();
      if(current(snapshot)&&(!snapshot.url.equals(savedUrl)||!serial.equals(savedSerial)||snapshot.nativeRevision!=savedNativeRevision)){
        synchronized(session.cache){
          if(!current(snapshot))return;
          if(snapshot.entries.length()>0&&conversationUrl(snapshot.url)){
            String stored=session.cache.readSerializedMessages(snapshot.url);
            if(!serial.equals(stored)){
              JSONArray previous=stored==null?new JSONArray():new JSONArray(stored);
              JSONArray retained=retainHistory(previous,snapshot.entries);
              if(retained!=previous){
                String retainedSerial=retained==snapshot.entries?serial:retained.toString();
                if(!current(snapshot))return;
                if(!retainedSerial.equals(stored))session.cache.saveSerializedMessages(snapshot.url,retainedSerial,title(retained));
              }
            }
          }
        }
        if(!current(snapshot))return;
        session.handler.post(()->{if(current(snapshot)&&snapshot.url.equals(currentUrl)&&snapshot.url.equals(session.conversation)&&!snapshot.url.equals(session.prefs.getString("conversation","")))session.prefs.edit().putString("conversation",snapshot.url).apply();});
        savedUrl=snapshot.url;savedSerial=serial;savedNativeRevision=snapshot.nativeRevision;
      }
    }catch(Exception e){session.handler.post(()->session.setStatus("本地记录保存失败，请保留原网页核对"));}
    finally{session.handler.post(()->{writing=false;if(latest!=null)schedule(urgent?0:2000);});}});
  }

  private static String title(JSONArray entries){
    for(int i=0;i<entries.length();i++){
      JSONObject row=entries.optJSONObject(i);
      if(row!=null&&"user".equals(row.optString("role"))){
        String title=row.optString("text").replaceAll("\\s+"," ").trim();
        return title.length()>80?title.substring(0,80)+"…":title;
      }
    }
    return "未命名对话";
  }

  private static JSONArray retainHistory(JSONArray previous,JSONArray incoming){
    if(previous.length()==0)return incoming;
    Map<String,Integer> savedPositions=new HashMap<>();
    for(int i=0;i<previous.length();i++){
      JSONObject row=previous.optJSONObject(i);
      if(row==null)return previous;
      String id=row.optString("id");
      if(id.isEmpty()||savedPositions.put(id,i)!=null)return previous;
    }
    Set<String> observedIds=new HashSet<>();
    int firstSaved=-1,lastSaved=-1,matches=0;
    boolean stableTail=true;
    for(int i=0;i<incoming.length();i++){
      JSONObject row=incoming.optJSONObject(i);
      if(row==null)return previous;
      String id=row.optString("id");
      if(id.isEmpty()||!observedIds.add(id))return previous;
      stableTail&=WebReplyObserver.stable(id);
      Integer position=savedPositions.get(id);
      if(position==null)continue;
      if(position<=lastSaved||!row.optString("role").equals(previous.optJSONObject(position).optString("role")))return previous;
      if(matches==0)firstSaved=position;
      else stableTail&=position==lastSaved+1;
      stableTail&=i==matches;
      lastSaved=position;
      matches++;
    }
    // DOM snapshots describe what's mounted. Omitted rows do not prove removal.
    if(matches==previous.length())return incoming;
    if(!stableTail||lastSaved!=previous.length()-1)return previous;
    JSONArray restored=new JSONArray();
    for(int i=0;i<firstSaved;i++)restored.put(previous.optJSONObject(i));
    for(int i=0;i<incoming.length();i++)restored.put(incoming.optJSONObject(i));
    return restored;
  }
}
