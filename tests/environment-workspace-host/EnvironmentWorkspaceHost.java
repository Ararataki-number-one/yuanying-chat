package local.pocketchat;

import java.util.*;
import org.json.*;

public final class EnvironmentWorkspaceHost {
  static int checks;
  static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static JSONObject row(int slot,String name){return J.obj("slot",slot,"name",name,"created",true,"generation",3,"environmentId","environment-"+slot,"pid",slot+100,"seen",100000L);}
  public static void main(String[] args)throws Exception{
    Set<Integer> live=new HashSet<>(Arrays.asList(100,101,102,103,104));long now=120000;
    JSONObject original=row(0,"工作研究"),copy=new JSONObject(original.toString());
    check(EnvironmentWorkspacePolicy.sameIdentity(original,copy),"unchanged identity admitted");
    copy.put("name","Renamed");check(EnvironmentWorkspacePolicy.sameIdentity(original,copy),"rename preserves identity");
    for(String field:new String[]{"deleting","resetting"}){copy=new JSONObject(original.toString()).put(field,true);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),field+" prevents dispatch");}
    copy=new JSONObject(original.toString()).put("created",false);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"deleted prevents dispatch");
    copy=new JSONObject(original.toString()).put("generation",4);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"reset generation rejected");
    copy=new JSONObject(original.toString()).put("environmentId","replacement");check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"slot reuse rejected");
    copy=new JSONObject(original.toString()).put("slot",1);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"different slot rejected");
    for(String field:new String[]{"slot","generation"}){
      copy=new JSONObject(original.toString());copy.remove(field);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"missing "+field+" rejected");
      copy=new JSONObject(original.toString()).put(field,"0");check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"string "+field+" rejected");
      copy=new JSONObject(original.toString()).put(field,0.5);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"fractional "+field+" rejected");
      copy=new JSONObject(original.toString()).put(field,-1);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"negative "+field+" rejected");
    }
    copy=new JSONObject(original.toString()).put("environmentId",JSONObject.NULL);check(!EnvironmentWorkspacePolicy.sameIdentity(original,copy),"null identity rejected");
    original.put("group","Team A").put("notes","WRITE paper");
    check(EnvironmentWorkspacePolicy.matches(original,"01  team WRITE"),"search every token across fields");
    check(EnvironmentWorkspacePolicy.matches(original,"工作 研究"),"Chinese tokens match");
    check(!EnvironmentWorkspacePolicy.matches(original,"team absent"),"all search tokens required");
    check(EnvironmentWorkspacePolicy.matches(original," \n \t "),"blank query includes rows");
    check(!EnvironmentWorkspacePolicy.matches(null,""),"null metadata rejected");
    check(EnvironmentWorkspacePolicy.running(original,live,160000),"freshness inclusive boundary");
    check(!EnvironmentWorkspacePolicy.running(original,live,160001),"stale heartbeat not running");
    check(!EnvironmentWorkspacePolicy.running(original,live,99999),"future heartbeat not running");
    check(!EnvironmentWorkspacePolicy.running(original,Collections.emptySet(),now),"dead process not running");
    check(!EnvironmentWorkspacePolicy.running(new JSONObject(original.toString()).put("seen",0),live,now),"missing heartbeat not running");
    JSONObject problem=row(0,"Issue").put("problem","offline").put("opened",20),draft=row(1,"Draft").put("draft","{}").put("opened",50),waiting=row(2,"Waiting").put("waiting",true).put("opened",90),stale=row(3,"Stale").put("waiting",true).put("seen",1),idle=row(4,"Idle");
    check(EnvironmentWorkspacePolicy.priority(problem,live,now)==0,"issue priority");
    check(EnvironmentWorkspacePolicy.priority(draft,live,now)==1,"configuration draft priority");
    check(EnvironmentWorkspacePolicy.priority(waiting,live,now)==2,"fresh waiting priority");
    check(EnvironmentWorkspacePolicy.priority(stale,live,now)==3,"stale waiting excluded from inbox");
    check(EnvironmentWorkspacePolicy.task(draft,live,now).equals("有配置草稿"),"configuration draft is not chat draft");
    check(EnvironmentWorkspacePolicy.task(stale,live,now).equals("上次等待状态待核对"),"historical waiting labeled explicitly");
    List<JSONObject> inbox=EnvironmentWorkspacePolicy.actionable(J.arr(waiting,idle,stale,draft,problem,new JSONObject(problem.toString()).put("deleting",true)),live,now);
    check(inbox.size()==3,"inbox only contains current eligible actionable records");
    check(inbox.get(0)==problem&&inbox.get(1)==draft&&inbox.get(2)==waiting,"inbox priority ordering");
    JSONObject second=row(1,"Second issue").put("problem","error").put("opened",21);
    check(EnvironmentWorkspacePolicy.actionable(J.arr(problem,second),live,now).get(0)==second,"same priority newest first");
    second.put("opened",20);check(EnvironmentWorkspacePolicy.actionable(J.arr(second,problem),live,now).get(0)==problem,"equal timestamp stable slot order");
    JSONObject view=EnvironmentWorkspacePolicy.view(" Research "," team draft ",null,99,-2);
    check(view.optString("name").equals("Research")&&view.optString("query").equals("team draft"),"saved view trims inputs");
    check(view.isNull("group")&&view.optInt("filter")==4&&view.optInt("sort")==0,"all-groups null and range bounds retained");
    check(EnvironmentWorkspacePolicy.view("No group","","",0,0).optString("group","missing").isEmpty(),"ungrouped remains distinct from all groups");
    check(EnvironmentWorkspacePolicy.view("abcdefghijklmnopqrstuvw😀","","",0,0).optString("name").equals("abcdefghijklmnopqrstuvw"),"bounded name avoids broken surrogate");
    check(EnvironmentWorkspacePolicy.savedViews("not-json").isEmpty(),"damaged saved data handled");
    check(EnvironmentWorkspacePolicy.savedViews(J.arr(J.obj("name","bad"),view,new JSONObject(view.toString()),EnvironmentWorkspacePolicy.view("Other","","",2,2)).toString()).size()==2,"invalid and duplicate views ignored");
    JSONArray many=new JSONArray();for(int i=0;i<12;i++)many.put(EnvironmentWorkspacePolicy.view("View "+i,"",null,0,0));
    check(EnvironmentWorkspacePolicy.savedViews(many.toString()).size()==8,"saved view storage bounded");
    check(EnvironmentWorkspacePolicy.savedViews("x".repeat(16385)).isEmpty(),"oversized preference handled without parsing");
    int adapterChecks=EnvironmentSavedViewsHost.run();
    int navigationChecks=SwitcherOpenHost.run();
    System.out.println("{\"passed\":"+(checks+adapterChecks+navigationChecks)+",\"policyChecks\":"+checks+",\"preferenceAdapterChecks\":"+adapterChecks+",\"navigationBoundaryChecks\":"+navigationChecks+",\"actualAndroidExecution\":false}");
  }
}
