package local.pocketchat;

import java.util.*;
import org.json.*;

/** Deterministic workloads execute production presentation/search policies, without Android layout claims. */
public final class PresentationHost {
  static int checks;static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static JSONObject row(int slot){return J.obj("slot",slot,"generation",3,"environmentId","env-"+slot,"created",true,"name","Work "+slot,"group","Research","notes","Write paper","seen",110000L,"pid",100+slot,"mode","应用代理","connected",true);}
  static final class Bound {final EnvironmentPresentation.Binding binding=new EnvironmentPresentation.Binding();int binds;void apply(JSONObject row,Set<Integer> running,long now){if(binding.changed(EnvironmentPresentation.stamp(row,running,now,0,false,false)))binds++;}}
  public static void main(String[] args)throws Exception {
    JSONArray rows=new JSONArray();Set<Integer> running=new HashSet<>();Map<String,Bound> holders=new LinkedHashMap<>();
    for(int i=0;i<8;i++){JSONObject row=row(i);rows.put(row);running.add(100+i);Bound holder=new Bound();holder.apply(row,running,120000);holders.put(EnvironmentPresentation.key(row),holder);}
    int baselineRawSignatures=0,heartbeatRebinds=0;String before=rows.toString();
    for(int frame=0;frame<100;frame++){
      for(int i=0;i<8;i++)rows.getJSONObject(i).put("seen",110001L+frame).put("privacy",frame).put("page","invisible-"+frame);
      if(!before.equals(rows.toString()))baselineRawSignatures++;before=rows.toString();
      for(int i=0;i<8;i++){JSONObject row=rows.getJSONObject(i);Bound holder=holders.get(EnvironmentPresentation.key(row));int prior=holder.binds;holder.apply(row,running,120000);heartbeatRebinds+=holder.binds-prior;}
    }
    check(baselineRawSignatures==100,"old raw metadata signature invalidates each heartbeat workload");check(heartbeatRebinds==0,"100 heartbeat updates cause zero production row rebinds");
    for(int i=0;i<8;i++)check(holders.get(EnvironmentPresentation.key(rows.getJSONObject(i))).binds==1,"initial keyed row reused without replacing holder");
    JSONObject first=rows.getJSONObject(0);first.put("name","Renamed work");int changed=0;for(int i=0;i<8;i++){JSONObject row=rows.getJSONObject(i);Bound holder=holders.get(EnvironmentPresentation.key(row));int prior=holder.binds;holder.apply(row,running,120000);changed+=holder.binds-prior;}check(changed==1,"one visible metadata change binds only its row");
    Bound original=holders.get(EnvironmentPresentation.key(first));String stamp=EnvironmentPresentation.stamp(first,running,120000,0,false,false);first.put("notes","invisible search note").put("draft","payload-v1");String draft=EnvironmentPresentation.stamp(first,running,120000,0,false,false);check(!stamp.equals(draft),"draft availability changes visible marker");first.put("draft","payload-v2");check(draft.equals(EnvironmentPresentation.stamp(first,running,120000,0,false,false)),"hidden draft payload update does not invalidate card");
    check(!draft.equals(EnvironmentPresentation.stamp(first,running,120000,1,false,false)),"default environment marker updates");check(!draft.equals(EnvironmentPresentation.stamp(first,running,120000,0,true,true)),"selection presentation updates");
    first.put("seen",1);check(!draft.equals(EnvironmentPresentation.stamp(first,running,120000,0,false,false)),"freshness expiration updates card");first.put("seen",110000L);
    check(!draft.equals(EnvironmentPresentation.stamp(first,Collections.emptySet(),120000,0,false,false)),"process exit updates current state");
    String oldKey=EnvironmentPresentation.key(first);first.put("generation",4);check(!oldKey.equals(EnvironmentPresentation.key(first)),"reset generation cannot reuse a prior row holder");first.put("generation",3);
    check(EnvironmentPresentation.visible(first,running,0,"rename",null),"search term matches current metadata");check(!EnvironmentPresentation.visible(first,running,1,"",null),"favorite filter excludes unstarred");check(EnvironmentPresentation.visible(first,running,2,"",null),"running filter uses captured processes");check(!EnvironmentPresentation.visible(first,running,3,"",null),"waiting filter excludes idle");check(!EnvironmentPresentation.visible(first,running,0,"","other"),"group filter preserved");
    JSONObject hidden=new JSONObject(first.toString()).put("mode","").put("pid",999).put("waiting",false).put("problem","");String hiddenStamp=EnvironmentPresentation.stamp(hidden,running,120000,0,false,false);hidden.put("connected",false).put("waiting",true);check(hiddenStamp.equals(EnvironmentPresentation.stamp(hidden,running,120000,0,false,false)),"inactive invisible connection and waiting fields do not rebind");
    JSONObject withProblem=new JSONObject(first.toString()).put("problem","offline").put("connected",true);String problemStamp=EnvironmentPresentation.stamp(withProblem,running,120000,0,false,false);withProblem.put("connected",false);check(problemStamp.equals(EnvironmentPresentation.stamp(withProblem,running,120000,0,false,false)),"connection bit masked by displayed problem does not rebind");
    JSONObject hugeDraft=new JSONObject(first.toString()).put("draft","x".repeat(100000));String compact=EnvironmentPresentation.stamp(hugeDraft,running,120000,0,false,false);check(compact.length()<500,"display signature never serializes large hidden draft payloads");
    EnvironmentSearchIndex index=new EnvironmentSearchIndex(rows);int queries=0;
    for(int i=0;i<100;i++){String[] tokens=EnvironmentSearchIndex.tokens(i%2==0?"Renamed 01":"Research paper");for(int j=0;j<8;j++)index.matches(rows.getJSONObject(j),tokens);queries++;}
    check(queries==100&&index.text.size()==8,"100 query events reuse one normalized eight-row index");check(index.matches(first,EnvironmentSearchIndex.tokens("renamed 01")),"indexed search ANDs normalized terms");
    check(!index.matches(first,EnvironmentSearchIndex.tokens("renamed absent")),"indexed search requires every token");check(index.matches(rows.getJSONObject(1),EnvironmentSearchIndex.tokens("02 research PAPER")),"indexed search combines number group notes and case");
    first.put("notes","Changed later");check(index.matches(first,EnvironmentSearchIndex.tokens("invisible search note")),"worker snapshot search remains stable until next snapshot");check(!new EnvironmentSearchIndex(rows).matches(first,EnvironmentSearchIndex.tokens("invisible search note")),"fresh snapshot replaces changed searchable metadata");
    System.out.println(J.obj("passed",checks,"baselineRawHeartbeatInvalidations",baselineRawSignatures,"optimizedHeartbeatRowRebinds",heartbeatRebinds,"initialRows",8,"singleRowChangeRebinds",changed,"searchEvents",queries,"normalizedIndexBuilds",1,"actualAndroidExecution",false));
  }
}
