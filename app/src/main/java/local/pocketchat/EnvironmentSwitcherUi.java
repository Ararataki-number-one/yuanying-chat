package local.pocketchat;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Intent;
import android.os.Build;
import android.text.*;
import android.view.View;
import android.widget.*;
import java.util.*;
import org.json.*;

/** Fast navigation reorders the owned activity; it never reloads or replaces its document. */
final class EnvironmentSwitcherUi {
  static Set<Integer> live(Activity activity){
    Set<Integer> ids=new HashSet<>();try{ActivityManager manager=activity.getSystemService(ActivityManager.class);List<ActivityManager.RunningAppProcessInfo> rows=manager==null?null:manager.getRunningAppProcesses();if(rows!=null)for(ActivityManager.RunningAppProcessInfo row:rows)ids.add(row.pid);}catch(RuntimeException unavailable){}return ids;
  }
  static void show(Activity activity){
    if(activity.isFinishing()||activity.isDestroyed())return;
    ReferenceUi.Modal panel=new ReferenceUi.Modal(activity,"快速切换环境").asSheet();
    DesignUi.note(panel.body,"切回原会话，阅读位置和进行中的任务沿用原环境。");
    EditText search=DesignUi.searchInput(panel.body,"搜索名称、分组、备注或编号");search.setContentDescription("搜索要切换的环境");
    TextView message=DesignUi.text(activity,"",13,DesignUi.MUTED);message.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);panel.body.addView(message);
    LinearLayout list=DesignUi.column(activity);panel.body.addView(list);
    Runnable render=()->{
      list.removeAllViews();JSONArray source=ProfileCatalog.get(activity).list();List<JSONObject> rows=new ArrayList<>();
      for(int i=0;i<source.length();i++){JSONObject row=source.optJSONObject(i);if(EnvironmentWorkspacePolicy.eligible(row)&&EnvironmentWorkspacePolicy.matches(row,search.getText().toString()))rows.add(row);}
      rows.sort((left,right)->{int recent=Long.compare(right.optLong("opened"),left.optLong("opened"));return recent!=0?recent:Integer.compare(left.optInt("slot"),right.optInt("slot"));});
      message.setText(rows.isEmpty()?"没有匹配的环境":"最近使用优先 · "+rows.size()+" 个环境");Set<Integer> running=live(activity);long now=System.currentTimeMillis();
      for(JSONObject row:rows){
        int slot=row.optInt("slot");String group=row.optString("group");String detail=(group.isEmpty()?"未分组":group)+" · "+EnvironmentWorkspacePolicy.task(row,running,now);
        boolean current=activity instanceof MainActivity&&Profiles.slot(activity)==slot;
        String label=String.format(Locale.ROOT,"%02d",slot+1)+"  "+row.optString("name")+(current?" · 当前":"")+"\n"+detail;
        Button action=DesignUi.button(activity,label,false,()->{
          if(open(activity,row,"chat",false))panel.dismiss();else message.setText("环境已变化或当前系统不支持，请关闭后重新选择。");
        });action.setSelected(current);action.setGravity(android.view.Gravity.START|android.view.Gravity.CENTER_VERTICAL);action.setContentDescription("切换到 "+row.optString("name")+"，"+detail);list.addView(action,new LinearLayout.LayoutParams(-1,-2));
      }
    };
    search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){render.run();}public void afterTextChanged(Editable value){}});
    render.run();panel.show();
  }
  static boolean open(Activity activity,JSONObject expected,String action,boolean overview){
    if(activity.isFinishing()||activity.isDestroyed()||!EnvironmentWorkspacePolicy.eligible(expected))return false;
    int slot=expected.optInt("slot",-1);if(slot<0||slot>=Profiles.MAX||slot>0&&Build.VERSION.SDK_INT<28)return false;
    ProfileCatalog catalog=ProfileCatalog.get(activity);if(!EnvironmentWorkspacePolicy.sameIdentity(expected,catalog.item(slot)))return false;
    Intent target=overview&&"chat".equals(action)?EnvironmentOverviewUi.opening(activity,slot):new Intent(activity,Profiles.activity(slot)).putExtra("openWindowAction",action).putExtra("returnToEnvironmentList","edit".equals(action)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
    // The catalog row may have changed while preparing the overview intent.
    if(!EnvironmentWorkspacePolicy.sameIdentity(expected,catalog.item(slot)))return false;
    catalog.opened(slot);activity.startActivity(target);return true;
  }
}
