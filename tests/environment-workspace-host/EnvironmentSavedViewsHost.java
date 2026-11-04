package local.pocketchat;

import org.json.*;

/** Executes the complete production preference adapter against controlled host storage. */
final class EnvironmentSavedViewsHost {
  static int checks;
  static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static int run()throws Exception {
    PreferenceAdapters.MemoryContext root=new PreferenceAdapters.MemoryContext(),child=new PreferenceAdapters.MemoryContext(root);
    EnvironmentSavedViews store=new EnvironmentSavedViews();
    check(store.list(child).length()==0,"new preference store contains no saved views");
    JSONObject initial=store.current(child);
    check(initial.isNull("group")&&initial.optInt("filter")==0&&initial.optInt("sort")==0,"new current scope uses all groups and default order");
    JSONObject all=EnvironmentSavedViews.view("Work","study",null,1,2);
    check(store.save(child,all),"named view saved through real adapter");
    check(root.files.containsKey("environment-workspace-views")&&child.files.isEmpty(),"profile context resolves global preference file");
    check(store.list(root).length()==1&&EnvironmentSavedViews.sameSettings(store.current(root),all),"saved current scope and named scope persist together");
    EnvironmentSavedViews reopened=new EnvironmentSavedViews();
    check(EnvironmentSavedViews.sameSettings(reopened.find(child,"Work"),all),"fresh store instance reloads named scope");
    check(reopened.find(child,"missing")==null&&reopened.find(child,"")==null&&reopened.find(child,null)==null,"unknown names have no implicit scope");
    JSONObject ungrouped=EnvironmentSavedViews.view("Work","draft","",4,1);
    check(reopened.save(child,ungrouped),"existing name replaced");
    check(reopened.list(root).length()==1&&reopened.find(root,"Work").optString("query").equals("draft"),"replacement does not append duplicate");
    check(!reopened.current(root).isNull("group")&&reopened.current(root).optString("group").isEmpty(),"reloaded ungrouped scope stays distinct");
    check(!EnvironmentSavedViews.sameSettings(all,ungrouped),"scope comparison includes group and query");
    JSONObject sameNameDifferent=EnvironmentSavedViews.view("Other name","draft","",4,1);
    check(EnvironmentSavedViews.sameSettings(ungrouped,sameNameDifferent),"scope comparison ignores label");
    reopened.remember(child,all);
    check(reopened.current(root).isNull("group")&&EnvironmentSavedViews.sameSettings(reopened.current(root),all),"remember restores all-groups null after ungrouped view");
    check(reopened.list(root).length()==1&&EnvironmentSavedViews.sameSettings(reopened.find(root,"Work"),ungrouped),"remember changes current scope only");
    for(int i=0;i<7;i++)check(reopened.save(root,EnvironmentSavedViews.view("View "+i,"query "+i,null,i%5,i%3)),"save additional named scope "+i);
    String before=reopened.list(root).toString(),currentBefore=reopened.current(root).toString();
    check(!reopened.save(root,EnvironmentSavedViews.view("Overflow","",null,0,0)),"ninth distinct view refused");
    check(before.equals(reopened.list(root).toString())&&currentBefore.equals(reopened.current(root).toString()),"full-store refusal preserves named and current scopes");
    check(reopened.save(root,all)&&reopened.list(root).length()==8,"replacement remains available at full capacity");
    reopened.remove(child,"View 3");
    check(reopened.list(root).length()==7&&reopened.find(root,"View 3")==null,"remove persists to global preference file");
    check(EnvironmentSavedViews.sameSettings(reopened.current(root),all),"remove does not rewrite current scope");
    reopened.remove(root,"not-present");check(reopened.list(root).length()==7,"removing unknown name preserves remaining scopes");
    check(reopened.save(root,EnvironmentSavedViews.view("After removal","",null,0,0)),"removed slot can be reused");
    check(!reopened.save(root,EnvironmentSavedViews.view("","",null,0,0)),"empty named scope refused");
    PreferenceAdapters.MemoryPreferences prefs=root.getSharedPreferences("environment-workspace-views",0);
    before=reopened.list(root).toString();currentBefore=reopened.current(root).toString();prefs.failNextCommit=true;
    check(!reopened.save(root,EnvironmentSavedViews.view("Work","changed",null,0,0)),"failed synchronous commit reported");
    check(before.equals(reopened.list(root).toString())&&currentBefore.equals(reopened.current(root).toString()),"failed commit preserves persisted scopes in host adapter");
    prefs.values.put("saved","damaged-json");prefs.values.put("current","damaged-json");
    check(reopened.list(root).length()==0,"corrupt named scope preference recovers to empty list");
    JSONObject recovered=reopened.current(root);
    check(recovered.isNull("group")&&recovered.optString("query").isEmpty()&&recovered.optInt("filter")==0&&recovered.optInt("sort")==0,"corrupt current scope recovers default all-groups view");
    check(reopened.save(root,all)&&reopened.find(root,"Work")!=null,"save repairs corrupt named scope preference");
    prefs.values.put("saved",J.arr(J.obj("name","bad"),all,all).toString());
    check(reopened.list(root).length()==1,"production adapter excludes malformed and duplicate saved rows");
    prefs.values.put("current",EnvironmentSavedViews.view("","x".repeat(200),null,99,99).toString());
    check(reopened.current(root).optString("query").length()==120&&reopened.current(root).optInt("filter")==4&&reopened.current(root).optInt("sort")==2,"reloaded current scope obeys production bounds");
    return checks;
  }
}
