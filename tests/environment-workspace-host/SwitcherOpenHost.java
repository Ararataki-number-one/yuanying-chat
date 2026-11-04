package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import org.json.JSONObject;

/** The runner extracts the production open method verbatim, with navigation-only doubles. */
final class SwitcherOpenHost {
  static int checks;
  static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static JSONObject row(int slot){return J.obj("slot",slot,"generation",3,"environmentId","environment-"+slot,"created",true);}
  static Activity reset(JSONObject current){ProfileCatalog.instance.reset(current);EnvironmentOverviewUi.openings=0;Build.VERSION.SDK_INT=35;return new Activity();}
  static int run()throws Exception{
    JSONObject expected=row(1);Activity caller=reset(new JSONObject(expected.toString()));
    check(EnvironmentSwitcherUi.open(caller,expected,"chat",false),"unchanged switch target opens");
    check(caller.starts==1&&caller.started.target==Profiles.activity(1),"exact requested environment activity started once");
    check(caller.started.caller==caller&&"chat".equals(caller.started.extras.get("openWindowAction")),"switch dispatch keeps caller and original chat target");
    check(caller.started.flags==(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),"switch reorders persistent environment activity");
    check(EnvironmentOverviewUi.openings==0&&!caller.started.extras.containsKey("hostOverviewMarker"),"instant switch does not insert overview");
    check(Boolean.FALSE.equals(caller.started.extras.get("returnToEnvironmentList")),"instant switch does not ask for editor return");
    check(ProfileCatalog.instance.opened==1&&ProfileCatalog.instance.openedSlot==1&&ProfileCatalog.instance.reads==2,"success stamps recent use only after second identity read");
    caller=reset(row(1));check(EnvironmentSwitcherUi.open(caller,expected,"chat",true),"explicit home overview opening supported");
    check(EnvironmentOverviewUi.openings==1&&Boolean.TRUE.equals(caller.started.extras.get("hostOverviewMarker")),"overview intent retained only for explicit chat opening");
    caller=reset(row(1));check(EnvironmentSwitcherUi.open(caller,expected,"edit",true),"editor opening supported");
    check(EnvironmentOverviewUi.openings==0&&Boolean.TRUE.equals(caller.started.extras.get("returnToEnvironmentList"))&&"edit".equals(caller.started.extras.get("openWindowAction")),"edit goes directly to editor and preserves return request");
    caller=reset(row(1));check(EnvironmentSwitcherUi.open(caller,expected,"network",true),"network opening supported");
    check(EnvironmentOverviewUi.openings==0&&"network".equals(caller.started.extras.get("openWindowAction")),"network action never creates overview");
    for(String state:new String[]{"deleting","resetting"}){
      caller=reset(new JSONObject(expected.toString()).put(state,true));
      check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0&&ProfileCatalog.instance.opened==0,state+" target rejected without dispatch or recent-use write");
    }
    caller=reset(row(1).put("environmentId","replacement"));
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0,"reused slot identity rejected");
    caller=reset(row(1).put("generation",4));
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0,"new generation rejected");
    caller=reset(row(1).put("created",false));
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0,"deleted target rejected");
    caller=reset(row(1));ProfileCatalog.instance.replaceOnSecondRead=row(1).put("environmentId","changed during intent preparation");
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",true)&&caller.starts==0&&ProfileCatalog.instance.opened==0&&EnvironmentOverviewUi.openings==1,"second identity check rejects changes during overview preparation");
    caller=reset(row(1));caller.destroyed=true;
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0&&ProfileCatalog.instance.reads==0,"destroyed caller rejected before metadata access");
    caller=reset(row(1));caller.finishing=true;
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0&&ProfileCatalog.instance.reads==0,"finishing caller rejected before metadata access");
    caller=reset(row(1));Build.VERSION.SDK_INT=26;
    check(!EnvironmentSwitcherUi.open(caller,expected,"chat",false)&&caller.starts==0&&ProfileCatalog.instance.reads==0,"Android 8 independent environment rejected");
    caller=reset(row(0));Build.VERSION.SDK_INT=26;
    check(EnvironmentSwitcherUi.open(caller,row(0),"chat",false)&&caller.started.target==Profiles.activity(0),"Android 8 default environment remains available");
    for(int slot:new int[]{-1,8}){
      caller=reset(row(slot));check(!EnvironmentSwitcherUi.open(caller,row(slot),"chat",false)&&caller.starts==0&&ProfileCatalog.instance.reads==0,"out-of-range slot rejected "+slot);
    }
    caller=reset(row(1));check(!EnvironmentSwitcherUi.open(caller,null,"chat",false)&&caller.starts==0,"missing expected environment rejected");
    return checks;
  }
}
