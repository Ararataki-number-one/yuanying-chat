package local.pocketchat;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BooleanSupplier;
import java.util.function.LongSupplier;

/** Frozen, explicitly selected native observations. No page/network strings enter this type. */
final class AiDiagnosticEvidence {
  private final List<Entry> entries;
  AiDiagnosticEvidence(List<Entry> value){entries=Collections.unmodifiableList(new ArrayList<>(value));}
  List<Entry> entries(){return entries;}

  static final class Entry {
    private final String label,payload;
    private final BooleanSupplier valid;
    Entry(String label,JSONObject value,BooleanSupplier valid){this.label=label;payload=value.toString();this.valid=valid;}
    String label(){return label;}
    // A fresh object prevents preview consumers from changing the send payload.
    JSONObject json(){return J.parse(payload);}
    boolean current(){return valid.getAsBoolean();}
  }

  enum Kind {LOAD_START,LOCATION_CHANGED,LOAD_ERROR,PAGE_STOP_SUCCESS,PAGE_STOP_FAILURE,CONTENT_CRASH,CONTENT_KILL}
  enum Signal {DNS_FAILURE,TIMEOUT,CERTIFICATE_REJECTED,TLS_FAILURE,CONTENT_CRASH,CONTENT_KILL,UNKNOWN}

  /** Main-thread adapter supplies opaque keys; they are never serialized. */
  static final class Journal {
    static final int MAX_EVENTS=16;
    static final long MAX_ELAPSED_MS=3600000;
    private final LongSupplier clock;
    private final Map<Object,Tab> tabs=new IdentityHashMap<>();
    private int nextTab;
    private static final class Tab {
      final int number;
      final List<JSONObject> events=new ArrayList<>();
      long revision,sequence,origin;
      boolean started;
      Tab(int number,long now){this.number=number;origin=now;}
    }
    Journal(LongSupplier clock){this.clock=clock;}
    void register(Object key){
      if(key==null||tabs.containsKey(key))return;
      if(nextTab==Integer.MAX_VALUE)throw new IllegalStateException("Anonymous tab evidence exhausted");
      tabs.put(key,new Tab(++nextTab,clock.getAsLong()));
    }
    void forget(Object key){tabs.remove(key);}
    void replace(Object previous,Object replacement){
      Tab old=tabs.remove(previous);if(old==null)return;
      Tab fresh=new Tab(old.number,clock.getAsLong());fresh.sequence=old.sequence;
      tabs.put(replacement,fresh);
    }
    void clear(){tabs.clear();}
    void reset(Object key){Tab tab=tabs.get(key);if(tab!=null){tab.events.clear();tab.started=false;tab.origin=clock.getAsLong();tab.revision++;}}
    void start(Object key){
      reset(key);Tab tab=tabs.get(key);if(tab==null)return;
      tab.started=true;append(tab,Kind.LOAD_START,Signal.UNKNOWN,null,null);
    }
    void location(Object key){
      Tab tab=tabs.get(key);if(tab==null)return;
      // History/BFCache/same-document notifications need not have onPageStart.
      // Retire the former window instead of presenting its errors as this page's.
      if(!tab.started)reset(key);
      append(tab,Kind.LOCATION_CHANGED,Signal.UNKNOWN,null,null);
    }
    void error(Object key,Signal signal,Integer code,Integer category){
      Tab tab=tabs.get(key);if(tab==null)return;
      if(code==null||category==null||code<0||category<0){code=null;category=null;signal=Signal.UNKNOWN;}
      if(signal!=Signal.DNS_FAILURE&&signal!=Signal.TIMEOUT&&signal!=Signal.CERTIFICATE_REJECTED&&signal!=Signal.TLS_FAILURE)signal=Signal.UNKNOWN;
      append(tab,Kind.LOAD_ERROR,signal,code,category);
    }
    void stop(Object key,boolean success){
      Tab tab=tabs.get(key);if(tab==null)return;
      append(tab,success?Kind.PAGE_STOP_SUCCESS:Kind.PAGE_STOP_FAILURE,Signal.UNKNOWN,null,null);tab.started=false;
    }
    void contentStopped(Object key,boolean killed){
      Tab tab=tabs.get(key);if(tab==null)return;
      append(tab,killed?Kind.CONTENT_KILL:Kind.CONTENT_CRASH,killed?Signal.CONTENT_KILL:Signal.CONTENT_CRASH,null,null);tab.started=false;
    }
    private void append(Tab tab,Kind kind,Signal signal,Integer code,Integer category){
      if(tab.sequence==Long.MAX_VALUE){tab.events.clear();tab.sequence=0;}
      long now=clock.getAsLong();if(tab.events.isEmpty())tab.origin=now;
      long delta=now<tab.origin?0:now-tab.origin;
      if(delta<0||delta>MAX_ELAPSED_MS)delta=MAX_ELAPSED_MS;
      tab.events.add(J.obj("id","E"+(++tab.sequence),"kind",kind.name(),"signal",signal.name(),
        "code",code==null?JSONObject.NULL:code,"category",category==null?JSONObject.NULL:category,"elapsedMs",delta));
      if(tab.events.size()>MAX_EVENTS)tab.events.remove(0);
      tab.revision++;
    }
    Entry snapshot(Object key,BooleanSupplier fence){
      Tab tab=tabs.get(key);if(tab==null)return null;
      long version=tab.revision;
      JSONArray events=new JSONArray();for(JSONObject event:tab.events)events.put(J.parse(event.toString()));
      JSONObject value=J.obj("schema",1,"engine","GECKO","tabEvidenceId","T"+tab.number,
        "scope","TAB_CALLBACK_OBSERVATIONS","navigationAttribution","UNKNOWN","events",events);
      // Gecko callbacks have no app request/document token. Even same-URL callbacks
      // may be late: these observations never assert ownership of a current request.
      return new Entry("标签页 "+tab.number,value,()->fence.getAsBoolean()&&tabs.get(key)==tab&&tab.revision==version);
    }
  }
}
