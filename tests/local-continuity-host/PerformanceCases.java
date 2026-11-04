package local.pocketchat;

import android.content.Context;
import java.util.*;
import java.util.concurrent.CancellationException;
import org.json.*;

/** Deterministic workloads count actual production work, rather than wall time. */
final class PerformanceCases {
  static JSONObject metrics=new JSONObject();
  static Map<String,Object> conversation(int number,String title,JSONArray messages){return ContinuityHost.row("url","https://chatgpt.com/c/perf-"+number,"title",title,"messages",messages.toString(),"touched",number);}
  static JSONObject message(String text)throws JSONException{return new JSONObject().put("role","assistant").put("text",text);}
  static void verify()throws Exception{
    Context context=new Context();
    for(int i=0;i<80;i++){JSONArray messages=new JSONArray();for(int j=0;j<40;j++)messages.put(message((j==0&&i%8==0?"marker ":"")+(i==0&&j==0?"rare ":"")+"saved body "+i+" "+j+" content "+"details ".repeat(8)));context.conversations.add(conversation(i,"local topic "+i,messages));}
    LocalContinuityStore.HistorySession session=new LocalContinuityStore.HistorySession(context);session.revision(0);
    LocalContinuityStore.History initial=session.search("marker",30);
    ContinuityHost.check("P7 initial full-text workload decodes eighty documents once",initial.rows.size()==10&&session.stats.metadataQueries==1&&session.stats.jsonDecodes==80);
    long decodes=session.stats.jsonDecodes,visits=session.stats.documentVisits;
    LocalContinuityStore.History refined=session.search("marker rare",30);
    ContinuityHost.check("P7 refinement reuses complete previous candidates without SQLite/JSON",refined.rows.size()==1&&session.stats.jsonDecodes==decodes&&session.stats.documentQueries==80&&session.stats.documentVisits-visits==10);
    session.search("absent",30);long sql=session.stats.documentQueries;decodes=session.stats.jsonDecodes;visits=session.stats.documentVisits;
    for(int i=0;i<20;i++)session.search("absent",30);
    ContinuityHost.check("P7 repeated same-query results perform zero SQL/JSON and candidate visits",session.stats.documentQueries==sql&&session.stats.jsonDecodes==decodes&&session.stats.documentVisits==visits);
    ContinuityHost.check("P7 changed query reuses bounded decoded documents",session.stats.cacheHits>=80&&session.stats.metadataQueries==1&&session.stats.jsonDecodes==80);
    session.search("",30);visits=session.stats.documentVisits;session.search("",60);
    ContinuityHost.check("P7 growing page scans only thirty new candidates",session.stats.documentVisits-visits==30&&session.stats.documentQueries==sql);
    LocalContinuityStore.History complete=session.search("",100);
    ContinuityHost.check("P7 incremental paging preserves original conversation order",complete.rows.size()==80&&complete.rows.get(79).url.endsWith("perf-79")&&!complete.more);
    context.conversations.add(0,conversation(1000,"new saved topic",new JSONArray().put(message("newly saved body"))));
    ContinuityHost.check("P7 typing/paging reuses the explicit local snapshot",session.search("",100).rows.size()==80&&session.stats.metadataQueries==1);
    session.revision(1);LocalContinuityStore.History fresh=session.search("newly saved",30);
    ContinuityHost.check("P7 existing Refresh revision invalidates data and search cache",fresh.rows.size()==1&&fresh.rows.get(0).url.endsWith("perf-1000")&&session.stats.metadataQueries==2);
    Context other=new Context();other.conversations.add(conversation(7,"separate",new JSONArray().put(message("other profile"))));
    ContinuityHost.check("P7 workspace snapshots never cross profile contexts",new LocalContinuityStore.HistorySession(other).search("newly saved",30).rows.isEmpty());
    Thread.currentThread().interrupt();boolean cancelled=false;try{session.search("newly saved",30);}catch(CancellationException expected){cancelled=true;}finally{Thread.interrupted();}
    ContinuityHost.check("P7 cancellation also rejects a cached result",cancelled);
    Context large=new Context();String text="x".repeat(30000);
    for(int i=0;i<120;i++)large.conversations.add(conversation(i,"large "+i,new JSONArray().put(message(text+(i==119?" finalneedle":"")))));
    LocalContinuityStore.HistorySession bounded=new LocalContinuityStore.HistorySession(large);bounded.search("missing",30);
    ContinuityHost.check("P7 decoded snapshot cache respects count and character budgets",bounded.cache.size()<=LocalContinuityStore.HistorySession.CACHE_DOCUMENTS&&bounded.stats.retainedCharacters<=LocalContinuityStore.HistorySession.CACHE_CHARACTERS);
    ContinuityHost.check("P7 cache overflow preserves searching older uncached records",bounded.search("finalneedle",30).rows.size()==1);

    List<LocalContinuityPolicy.Message> messages=new ArrayList<>();
    for(int i=0;i<1000;i++)messages.add(new LocalContinuityPolicy.Message("assistant",(i%10==0?"target ":"")+(i==0?"rare ":"")+"message "+i+" "+"visible detail ".repeat(5),i+1));
    LocalMessageIndex index=new LocalMessageIndex(messages);List<LocalContinuityPolicy.Message> found=index.search("target");
    ContinuityHost.check("P8 initial index returns exact original positions",found.size()==100&&found.get(99).position==991);
    long normalization=index.stats.normalizations,messageVisits=index.stats.visits,characters=index.stats.normalizedCharacters;
    boolean same=true;for(int i=0;i<20;i++)same&=index.search("ＴＡＲＧＥＴ")==found;
    ContinuityHost.check("P8 same-query pages share the immutable result after Unicode normalization",same);
    ContinuityHost.check("P8 twenty message-page requests add zero normalize/filter work",index.stats.normalizations==normalization&&index.stats.visits==messageVisits&&index.stats.normalizedCharacters==characters);
    List<LocalContinuityPolicy.Message> narrow=index.search("target rare");
    ContinuityHost.check("P8 refining message query checks prior matches only",narrow.size()==1&&index.stats.visits-messageVisits==100&&index.stats.normalizations==normalization);
    ContinuityHost.check("P8 broadening remains correct with reused normalized strings",index.search("target").size()==100&&index.stats.normalizations==normalization);
    LocalMessageIndex across=new LocalMessageIndex(Arrays.asList(new LocalContinuityPolicy.Message("user","alpha",1),new LocalContinuityPolicy.Message("assistant","gamma",2)));
    ContinuityHost.check("P8 document search preserves tokens across title and separate messages",across.document("header","header alpha gamma").matched);
    ContinuityHost.check("P8 within-conversation message search requires all tokens in one message",across.search("alpha gamma").isEmpty());
    ContinuityHost.check("P8 normalized index retains bounded characters",index.stats.retainedCharacters<=LocalMessageIndex.NORMALIZED_LIMIT);
    LocalMessageIndex overflow=new LocalMessageIndex(Arrays.asList(new LocalContinuityPolicy.Message("assistant","x".repeat(LocalMessageIndex.NORMALIZED_LIMIT+100)+" tailneedle",1)));
    ContinuityHost.check("P8 oversized messages remain fully searchable without permanent oversized index",overflow.search("tailneedle").size()==1&&overflow.stats.retainedCharacters==0);
    LocalMessageIndex.Stats preview=new LocalMessageIndex.Stats();String prefix=LocalMessageIndex.preview("😀".repeat(500000),120,preview);
    ContinuityHost.check("P8 million-UTF16-unit preview inspects only required Unicode prefix",preview.previewCodePoints==121&&prefix.codePointCount(0,prefix.length())==121&&prefix.endsWith("…"));
    Random random=new Random(19);String[] tokens={"a","😀","\u0301","\n","\t","\u0000","\u001f"," ","\u3000"};boolean equivalent=true;
    for(int sample=0;sample<1000;sample++){StringBuilder value=new StringBuilder();for(int i=0;i<80;i++)value.append(tokens[random.nextInt(tokens.length)]);int limit=random.nextInt(30);String old=value.toString().replaceAll("\\s+"," ").trim();if(old.codePointCount(0,old.length())>limit)old=old.substring(0,old.offsetByCodePoints(0,limit))+"…";equivalent&=old.equals(LocalMessageIndex.preview(value.toString(),limit,null));}
    ContinuityHost.check("P8 streaming preview preserves previous Unicode/whitespace behavior",equivalent);
    Thread.currentThread().interrupt();cancelled=false;try{index.search("target");}catch(CancellationException expected){cancelled=true;}finally{Thread.interrupted();}
    ContinuityHost.check("P8 cancelled cached search never publishes a result",cancelled);
    metrics.put("P7",new JSONObject().put("workloadDocuments",80).put("messagesPerDocument",40).put("initialJsonDecodes",80).put("repeatedQueryAdditionalSql",0).put("repeatedQueryAdditionalJsonDecodes",0).put("refinementVisitedDocuments",10).put("nextThirtyResultsVisitedDocuments",30).put("cacheBudgetCharacters",LocalContinuityStore.HistorySession.CACHE_CHARACTERS).put("overflowRetainedCharacters",bounded.stats.retainedCharacters));
    metrics.put("P8",new JSONObject().put("workloadMessages",1000).put("initialNormalizations",normalization).put("repeatedPageRequests",20).put("additionalPageNormalizations",0).put("additionalPageMessageVisits",0).put("refinementMessageVisits",100).put("previewInputUtf16Units",1000000).put("previewCodePointsInspected",preview.previewCodePoints).put("normalizedCacheBudgetCharacters",LocalMessageIndex.NORMALIZED_LIMIT));
  }
}
