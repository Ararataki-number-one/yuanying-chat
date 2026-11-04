package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import org.json.*;
import java.util.*;

/** Read only adapters over the existing profile-scoped stores; no second copy of history. */
final class LocalContinuityStore {
  static final class Drafts {
    final List<LocalContinuityPolicy.Draft> rows;final boolean incomplete,more;
    Drafts(List<LocalContinuityPolicy.Draft> rows,boolean incomplete,boolean more){this.rows=rows;this.incomplete=incomplete;this.more=more;}
  }
  static Drafts drafts(Context context,String query,int limit){
    List<LocalContinuityPolicy.Draft> rows=new ArrayList<>();boolean incomplete=false;
    SharedPreferences prefs=context.getSharedPreferences("chat",0);
    rows.add(new LocalContinuityPolicy.Draft(prefs.getString("draft",""),"旧版输入草稿","",0));
    rows.add(new LocalContinuityPolicy.Draft(J.parse(prefs.getString("legacyPending","{}")).optString("prompt"),"旧版待核对提问","",0));
    try(Cursor cursor=DraftArchive.get(context).getReadableDatabase().query("drafts",new String[]{"body","origin","url","created"},null,null,null,null,"created DESC")){
      while(!Thread.currentThread().isInterrupted()&&cursor.moveToNext())rows.add(new LocalContinuityPolicy.Draft(cursor.getString(0),cursor.getString(1),cursor.getString(2),cursor.getLong(3)));
    }catch(RuntimeException failure){incomplete=true;}
    try(ConversationStore store=new ConversationStore(context);Cursor cursor=store.getReadableDatabase().query("conversations",new String[]{"draft","title","url","touched"},"draft<>''",null,null,null,"touched DESC,rank ASC")){
      while(!Thread.currentThread().isInterrupted()&&cursor.moveToNext())rows.add(new LocalContinuityPolicy.Draft(cursor.getString(0),"旧版草稿 · "+cursor.getString(1),cursor.getString(2),cursor.getLong(3)));
    }catch(RuntimeException failure){incomplete=true;}
    for(Map.Entry<String,?> row:prefs.getAll().entrySet())if(row.getKey().startsWith("draftBackup:")&&row.getValue() instanceof String)rows.add(new LocalContinuityPolicy.Draft((String)row.getValue(),"此前暂存草稿","",0));
    List<LocalContinuityPolicy.Draft> selected=LocalContinuityPolicy.drafts(rows,query,limit+1);boolean more=selected.size()>limit;if(more)selected.remove(selected.size()-1);
    return new Drafts(selected,incomplete,more);
  }
  static final class Conversation {
    final String url,title,snippet,readerQuery;final long touched;final List<LocalContinuityPolicy.Message> messages;final LocalMessageIndex index;
    Conversation(String url,String title,long touched,List<LocalContinuityPolicy.Message> messages,String query){
      this(url,title,touched,new LocalMessageIndex(messages),query,null);
    }
    Conversation(String url,String title,long touched,LocalMessageIndex index,String query,LocalMessageIndex.Match supplied){
      this.url=url;this.title=title==null||title.isEmpty()?"未命名对话":title;this.touched=touched;this.index=index;messages=index.messages;
      LocalMessageIndex.Match match=supplied==null?index.document(this.title,query):supplied;
      snippet=LocalMessageIndex.preview(match.first==null?"":match.first.text,120,index.stats);readerQuery=match.messageMatch?query:"";
    }
  }
  static final class History {
    final List<Conversation> rows;final boolean incomplete,more;
    History(List<Conversation> rows,boolean incomplete,boolean more){this.rows=rows;this.incomplete=incomplete;this.more=more;}
  }
  static History history(Context context,String query,int limit){
    return new HistorySession(context).search(query,limit);
  }
  /** One visible dialog owns this snapshot. Existing explicit Refresh invalidates
   * it; typing and growing the result page never reopen the whole SQLite payload. */
  static final class HistorySession {
    static final int CACHE_CHARACTERS=2*1024*1024,CACHE_DOCUMENTS=96;
    static final class Stats {long metadataQueries,documentQueries,jsonDecodes,documentVisits,cacheHits,resultHits;int retainedCharacters;}
    static final class Source {final String url,title;final long touched;Source(String url,String title,long touched){this.url=url;this.title=title;this.touched=touched;}}
    static final class Document {final LocalMessageIndex index;final int characters;Document(LocalMessageIndex index,int characters){this.index=index;this.characters=characters;}}
    static final class Search {final String key;final List<Conversation> rows=new ArrayList<>(),basis;int next;boolean done;Search(String key,List<Conversation> basis){this.key=key;this.basis=basis;done=basis!=null&&basis.isEmpty();}}
    final Context context;final Stats stats=new Stats();List<Source> sources;boolean incomplete;Search selected;long revision=-1;
    final LinkedHashMap<String,Document> cache=new LinkedHashMap<>(16,.75f,true);
    HistorySession(Context context){this.context=context;}
    void invalidate(){sources=null;selected=null;incomplete=false;cache.clear();stats.retainedCharacters=0;}
    void revision(long expected){if(revision!=expected){invalidate();revision=expected;}}
    void snapshot(ConversationStore store){
      if(sources!=null)return;List<Source> next=new ArrayList<>();stats.metadataQueries++;
      try(Cursor cursor=store.getReadableDatabase().query("conversations",new String[]{"url","title","touched"},"messages<>'[]'",null,null,null,"touched DESC,rank ASC")){
        while(cursor.moveToNext()){LocalMessageIndex.interrupted();String url=cursor.getString(0);if(MainActivity.chatUrl(url))next.add(new Source(url,cursor.getString(1),cursor.getLong(2)));}
      }sources=next;
    }
    Document document(ConversationStore store,Source source){
      Document saved=cache.get(source.url);if(saved!=null){stats.cacheHits++;return saved;}LocalMessageIndex.interrupted();stats.documentQueries++;
      try(Cursor cursor=store.getReadableDatabase().query("conversations",new String[]{"messages"},"url=?",new String[]{source.url},null,null,null)){
        if(!cursor.moveToNext())return null;LocalMessageIndex.interrupted();stats.jsonDecodes++;JSONArray entries=new JSONArray(cursor.getString(0));
        List<LocalContinuityPolicy.Message> messages=new ArrayList<>();long characters=0;
        for(int i=0;i<entries.length();i++){LocalMessageIndex.interrupted();JSONObject row=entries.optJSONObject(i);if(row==null)continue;String body=row.optString("text");if(body.trim().isEmpty())continue;messages.add(new LocalContinuityPolicy.Message(row.optString("role"),body,i+1));characters+=body.length();}
        Document result=new Document(new LocalMessageIndex(messages),(int)Math.min(Integer.MAX_VALUE,characters));
        if(result.characters<=CACHE_CHARACTERS){
          while(!cache.isEmpty()&&(cache.size()>=CACHE_DOCUMENTS||stats.retainedCharacters+result.characters>CACHE_CHARACTERS)){Iterator<Map.Entry<String,Document>> iterator=cache.entrySet().iterator();Map.Entry<String,Document> oldest=iterator.next();stats.retainedCharacters-=oldest.getValue().characters;iterator.remove();}
          cache.put(source.url,result);stats.retainedCharacters+=result.characters;
        }return result;
      }catch(JSONException malformed){incomplete=true;return null;}
    }
    History search(String query,int limit){
      LocalMessageIndex.interrupted();String key=new LocalMessageIndex.Query(query).key;limit=Math.max(1,limit);
      if(selected==null||!selected.key.equals(key)){List<Conversation> basis=selected!=null&&selected.done&&new LocalMessageIndex.Query(query).refines(new LocalMessageIndex.Query(selected.key))?selected.rows:null;selected=new Search(key,basis);}
      if(selected.done||selected.rows.size()>limit){stats.resultHits++;return page(limit);}
      try(ConversationStore store=new ConversationStore(context)){
        snapshot(store);
        int size=selected.basis==null?sources.size():selected.basis.size();
        while(selected.next<size&&selected.rows.size()<=limit){
          LocalMessageIndex.interrupted();Conversation basis=selected.basis==null?null:selected.basis.get(selected.next);Source source=basis==null?sources.get(selected.next):new Source(basis.url,basis.title,basis.touched);Document document=basis==null?document(store,source):new Document(basis.index,0);stats.documentVisits++;
          if(document!=null){LocalMessageIndex.Match match=document.index.document(source.title,query);if(match.matched)selected.rows.add(new Conversation(source.url,source.title,source.touched,document.index,query,match));}
          // A cancelled normalization leaves this source unconsumed for the next search.
          selected.next++;
        }
        selected.done=selected.next>=size;
      }catch(java.util.concurrent.CancellationException cancelled){throw cancelled;}catch(RuntimeException failure){incomplete=true;}
      LocalMessageIndex.interrupted();return page(limit);
    }
    History page(int limit){int count=Math.min(limit,selected.rows.size());return new History(new ArrayList<>(selected.rows.subList(0,count)),incomplete,selected.rows.size()>limit);}
  }
}
