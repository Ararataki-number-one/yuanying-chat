package local.pocketchat;

import org.json.*;
import java.util.function.*;

public class WebPerformanceTestActivity extends WebReplyFixtureActivity {
  final WebTranscriptMirror mirror=new WebTranscriptMirror();JSONArray snapshot=new JSONArray();int builtBefore;
  @Override void begin(){session.handler.removeCallbacks(session.tick);session.syncRun++;session.inFlight=false;session.remove(sessionObserver);handler.removeCallbacks(ticker);
    check("Web mode does not load the hidden reader",pageMode&&!readerLoaded&&!readerReady);
    check("Application has the requested name",getPackageManager().getApplicationLabel(getApplicationInfo()).toString().equals("元婴期院士测试"));
    js("fixture.reset({url:'/c/cache-test'});for(let i=0;i<100;i++){if(i%2){const e=fixture.answer('cache-'+i,'回复 '+i);e.querySelector('.markdown').innerHTML='<p>公式 <span class=katex><annotation encoding=\"application/x-tex\">x^2+1</annotation></span></p><pre><code class=language-python>print('+i+')</code></pre>';}else fixture.user('cache-'+i,'提问 '+i)}",()->read(data->{
      check("Initial delta contains every loaded message",data.optBoolean("reset")&&data.optJSONArray("changes").length()==100);
      apply(data);check("Mirror retains all messages",snapshot.length()==100);String text=snapshot.optJSONObject(1).optString("text");
      check("Cached extraction preserves formula source",text.contains("$x^2+1$"));check("Cached extraction preserves fenced code",text.contains("```python")&&text.contains("print(1)"));
      built(d->{builtBefore=d.optInt("entriesBuilt");unchanged();});
    }));
  }
  void read(Consumer<JSONObject> cb){session.runDriver("web-transcript",mirror.arguments(),cb::accept);}
  void apply(JSONObject data){JSONArray next=mirror.accept(data,snapshot,mirror.url);if(next!=null)snapshot=next;}
  void built(Consumer<JSONObject> cb){remote.evaluateJavascript("window.__pocketWebPerformance.stats()",raw->cb.accept(J.parse(raw)));}
  void unchanged(){read(data->{check("Unchanged transcript has no repeated payload",!data.optBoolean("changed")&&!data.has("changes")&&!data.has("order"));built(d->{check("Unchanged snapshot does not rebuild old messages",d.optInt("entriesBuilt")==builtBefore);editOne();});});}
  void editOne(){String previous=snapshot.toString();js("document.querySelector('[data-message-id=cache-99] .markdown p').textContent='新追加的内容'",()->read(data->{
    check("One edited reply transfers only one message",data.optJSONArray("changes").length()==1&&!data.has("order"));apply(data);
    check("Only the latest reply is updated",snapshot.optJSONObject(99).optString("text").contains("新追加")&&snapshot.optJSONObject(1).optString("text").contains("print(1)"));
    built(d->{check("One edit rebuilds one entry rather than the entire history",d.optInt("entriesBuilt")==builtBefore+1);removeOlder();});
  }));}
  void removeOlder(){js("for(let i=0;i<20;i++)turns.firstElementChild.remove()",()->read(data->{check("Virtualized history sends a new order without re-extracting old messages",data.has("order")&&data.optJSONArray("changes").length()==0&&data.optJSONArray("order").length()==80);apply(data);check("Previously cached earlier messages remain available",snapshot.length()==100&&snapshot.optJSONObject(0).optString("id").equals("id:cache-0"));removeMiddle();}));}
  void removeMiddle(){js("document.querySelector('[data-message-id=cache-25]').remove()",()->read(data->{apply(data);boolean removed=true;for(int i=0;i<snapshot.length();i++)if(snapshot.optJSONObject(i).optString("id").equals("id:cache-25"))removed=false;check("Removed middle messages are not kept in the visible sequence",removed&&snapshot.length()==99);route();}));}
  void route(){js("fixture.reset({url:'/c/another-cache'});fixture.user('cache-0','另一对话的正文')",()->read(data->{check("Route change forces a coherent snapshot",data.optBoolean("reset"));apply(data);check("Reused IDs on another route do not mix histories",snapshot.length()==1&&snapshot.optJSONObject(0).optString("text").equals("另一对话的正文"));coalesce();}));}
  void coalesce(){WebPerfStats.reset();String url=ORIGIN+"c/background-cache-"+System.currentTimeMillis();JSONArray last=null;
    for(int version=0;version<40;version++){JSONArray data=new JSONArray();for(int i=0;i<100;i++)data.put(J.obj("id","store-"+i,"role",i%2==0?"user":"assistant","text","Version "+version+" row "+i));last=data;session.webStore.offer(url,data);}
    session.conversation=url;session.entries=last;session.webStore.flush();String expected=url;
    waitFor("Coalesced snapshot is saved",()->!session.webStore.writing&&!session.webStore.scheduled&&session.webStore.latest==null,40,()->{
      JSONObject stats=WebPerfStats.snapshot();check("Burst updates produce one history write",stats.optLong("messageWrites")==1);check("History is saved outside the UI thread",stats.optLong("mainThreadWrites")==0);
      JSONArray saved=session.cache.messages(expected);check("The final version wins over queued older snapshots",saved.length()==100&&saved.optJSONObject(99).optString("text").startsWith("Version 39"));
      session.webStore.offer(expected,session.entries);session.webStore.flush();handler.postDelayed(()->{check("Repeated identical snapshot does not write again",WebPerfStats.snapshot().optLong("messageWrites")==1);WebPerfStats.enabled=false;cancelOlderSnapshot(expected);},800);
    });
  }
  void cancelOlderSnapshot(String url){JSONArray stale=new JSONArray();stale.put(J.obj("id","stale","role","user","text","stale version"));session.webStore.offer(url,stale);session.webStore.nativeSnapshot(url);handler.postDelayed(()->{
    JSONArray saved=session.cache.messages(url);check("Cancelled background snapshots do not overwrite a newer native view",saved.length()==100&&saved.optJSONObject(99).optString("text").startsWith("Version 39"));cancelInFlight(url);
  },2300);}
  void cancelInFlight(String url){java.util.concurrent.CountDownLatch gate=new java.util.concurrent.CountDownLatch(1);session.webStore.worker.execute(()->{try{gate.await(5,java.util.concurrent.TimeUnit.SECONDS);}catch(Exception ignored){}});JSONArray stale=new JSONArray();stale.put(J.obj("id","stale-active","role","user","text","stale active write"));session.webStore.offer(url,stale);session.webStore.flush();handler.postDelayed(()->{
    session.webStore.nativeSnapshot(url);JSONArray newest=new JSONArray();newest.put(J.obj("id","new-native","role","user","text","newer native snapshot"));session.cache.saveMessages(url,newest);gate.countDown();handler.postDelayed(()->{JSONArray saved=session.cache.messages(url);check("An already queued writer cannot overwrite a newer native snapshot",saved.length()==1&&saved.optJSONObject(0).optString("text").equals("newer native snapshot"));session.cache.saveMessages(url,session.entries);differentConversations(url);},600);
  },150);}
  void differentConversations(String url){String other=url+"-other";JSONArray a=new JSONArray(),b=new JSONArray();a.put(J.obj("id","first","role","user","text","first conversation"));b.put(J.obj("id","second","role","user","text","second conversation"));session.webStore.offer(url,a);session.webStore.offer(other,b);session.webStore.flush();waitFor("Different conversations each finish their queued save",()->!session.webStore.writing&&!session.webStore.scheduled&&session.webStore.latest==null,40,()->{JSONArray first=session.cache.messages(url),second=session.cache.messages(other);check("Switching conversations does not discard the previous unsaved snapshot",first.length()==1&&second.length()==1&&first.optJSONObject(0).optString("text").equals("first conversation")&&second.optJSONObject(0).optString("text").equals("second conversation"));session.cache.saveMessages(url,session.entries);navigationCache(url);});}
  void navigationCache(String url){session.offline=true;session.navigate(url,"测试缓存读取");check("Web navigation avoids synchronous full-history loading",session.entries.length()==0&&!session.showingCache);session.webStore.loadIfNeeded();waitFor("Previously saved messages load asynchronously for offline reading",()->session.entries.length()==100&&session.showingCache,30,()->{session.offline=false;session.navigating=false;session.navigationFailed=false;nativeReader();});}
  void nativeReader(){showPage(false);showPage(true);waitFor("Reader is loaded only when switching to simple mode",()->readerLoaded&&readerReady,40,()->{
    check("Mode switch leaves the original webpage intact",remote.getUrl().endsWith("/c/another-cache"));showPage(false);handler.postDelayed(()->reader.evaluateJavascript("window.chat.debug().count",raw->{check("A reader loaded while hidden replays messages when reopened",Integer.parseInt(raw)>0);showPage(true);check("Return to webpage mode hides native reader",reader.getVisibility()==android.view.View.GONE&&composer.getVisibility()==android.view.View.GONE);noResend("Performance observation never sends a message",0,()->report("web-performance-results.json"));}),300);
  });}
}
