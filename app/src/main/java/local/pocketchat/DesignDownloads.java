package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.text.DateFormat;
import java.util.*;

/** Shared download presentation keeps live rows in place while progress changes. */
final class DesignDownloads {
  static JSONArray rows(Context c){DownloadLibrary library=DownloadLibrary.get(c);return ordered(library.list(),library.tasks());}
  static JSONArray ordered(JSONArray files,JSONArray tasks){
    return DownloadListPolicy.ordered(files,tasks);
  }
  static String key(JSONObject row){return DownloadListPolicy.key(row);}
  static boolean busy(String state){return DownloadListPolicy.busy(state);}
  static boolean matches(JSONObject row,int filter){return DownloadListPolicy.matches(row,filter);}
  static String timeLabel(JSONObject row){long time=row.optLong("time");if(time<=0)return "时间未记录";return ("saved".equals(row.optString("state"))?"保存于 ":"开始于 ")+DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,Locale.getDefault()).format(new Date(time));}
  static String updateKey(Context context){Bundle b=AppUpdates.call(context,"status",null);return b.getString("state","")+":"+b.getLong("packageStoredBytes")+":"+b.getBoolean("packageDeleteRetry");}
  static void updatePackage(Activity a,LinearLayout box){
    Bundle update=AppUpdates.call(a,"status",null);long bytes=update.getLong("packageStoredBytes");
    if(bytes<=0&&!update.getBoolean("packageDeleteRetry"))return;
    LinearLayout row=DesignUi.row(a);TextView label=DesignUi.text(a,"更新安装包 · "+DownloadTasks.amount(bytes),12,DesignUi.MUTED);
    row.addView(label,new LinearLayout.LayoutParams(0,-2,1));Button manage=DesignUi.button(a,"管理",false,()->AppUpdates.open(a));manage.setTextSize(12);manage.setContentDescription("管理更新安装包");
    row.addView(manage,new LinearLayout.LayoutParams(DesignUi.dp(a,64),DesignUi.dp(a,44)));box.addView(row,new LinearLayout.LayoutParams(-1,-2));
  }
  static void open(Activity a,JSONObject r,SavedFileActions actions){if("saved".equals(r.optString("state"))){actions.show(r);return;}int slot=r.optInt("slot");if(a instanceof MainActivity&&slot==Profiles.slot(a)){MainActivity main=(MainActivity)a;for(int i=0;i<main.downloads.tasks.rows.length();i++){JSONObject actual=main.downloads.tasks.rows.optJSONObject(i);if(actual.optString("id").equals(r.optString("id"))){main.downloads.taskActions(actual);return;}}}a.startActivity(new Intent(a,Profiles.activity(slot)).putExtra("openDownload",r.optString("id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  static void render(Activity a,LinearLayout box,int filter,java.util.function.IntConsumer choose,SavedFileActions actions){new Controller(a,box,filter,choose,actions);}

  /** One controller per visible workspace; byte changes never replace its scroll view. */
  static final class Controller {
    final Activity a;final LinearLayout box,packages,list,empty;final java.util.function.IntConsumer choose;final SavedFileActions actions;
    final Map<String,Row> views=new LinkedHashMap<>();int filter=-1;String packageKey="";LinearLayout tabs;
    Controller(Activity a,LinearLayout box,int filter,java.util.function.IntConsumer choose,SavedFileActions actions){
      this.a=a;this.box=box;this.choose=choose;this.actions=actions;
      tabs=DesignUi.tabs(a,new String[]{"全部","进行中","已完成","失败"},filter,choose);box.addView(tabs);
      LinearLayout link=DesignUi.row(a);TextView scope=DesignUi.text(a,"全部环境",12,DesignUi.MUTED);link.addView(scope,new LinearLayout.LayoutParams(0,-2,1));Button folder=DesignUi.button(a,"保存位置",false,()->folder(a));folder.setTextSize(12);link.addView(folder,new LinearLayout.LayoutParams(DesignUi.actionWidth(folder,88),android.view.ViewGroup.LayoutParams.WRAP_CONTENT));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.topMargin=DesignUi.dp(a,10);box.addView(link,lp);
      packages=DesignUi.column(a);box.addView(packages);list=DesignUi.column(a);box.addView(list);empty=DesignUi.column(a);box.addView(empty);
      this.filter=filter;refresh(filter);
    }
    void refresh(int selected){apply(rows(a),selected,System.currentTimeMillis());String next=updateKey(a);if(!next.equals(packageKey)){packageKey=next;packages.removeAllViews();updatePackage(a,packages);}}
    void apply(JSONArray data,int selected,long now){
      boolean changedFilter=selected!=filter;if(changedFilter){filter=selected;box.removeView(tabs);tabs=DesignUi.tabs(a,new String[]{"全部","进行中","已完成","失败"},filter,choose);box.addView(tabs,0);}
      ScrollView scroll=box.getParent() instanceof ScrollView?(ScrollView)box.getParent():null;int oldY=scroll==null?0:scroll.getScrollY();
      View anchor=null;int anchorTop=0;if(oldY>0&&!changedFilter){for(int i=0;i<list.getChildCount();i++){View card=list.getChildAt(i);int top=list.getTop()+card.getTop();if(top+card.getHeight()>oldY){anchor=card;anchorTop=top-oldY;break;}}}
      Set<String> visible=new HashSet<>();int index=0;boolean structure=changedFilter;
      for(int i=0;i<data.length();i++){
        JSONObject value=data.optJSONObject(i);if(value==null||!matches(value,filter))continue;String key=key(value);if(!visible.add(key))continue;
        Row row=views.get(key);if(row==null){row=new Row(a,actions);views.put(key,row);}row.bind(value,now);
        if(index>=list.getChildCount()||list.getChildAt(index)!=row.card){structure=true;if(row.card.getParent()==list)list.removeView(row.card);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=DesignUi.dp(a,10);list.addView(row.card,index,p);}index++;
      }
      for(Iterator<Map.Entry<String,Row>> it=views.entrySet().iterator();it.hasNext();){Map.Entry<String,Row> entry=it.next();if(!visible.contains(entry.getKey())){list.removeView(entry.getValue().card);it.remove();structure=true;}}
      if(index==0){if(empty.getChildCount()==0||changedFilter){empty.removeAllViews();String[] titles={"还没有下载文件","没有进行中的下载","还没有已完成的下载","没有失败的下载"};String[] details={"在会话中保存文件后，可在这里打开、分享或删除。","开始下载后，这里会显示实际进度。","文件保存完成后会自动出现在这里。","下载失败时，这里会显示原因和可用操作。"};DesignUi.empty(empty,titles[filter],details[filter],"查看全部下载",filter==0?null:()->choose.accept(0));}}else if(empty.getChildCount()>0)empty.removeAllViews();
      if(scroll!=null&&structure){View kept=anchor;int offset=anchorTop;scroll.post(()->{if(changedFilter)scroll.scrollTo(0,0);else if(kept!=null&&kept.getParent()==list)scroll.scrollTo(0,list.getTop()+kept.getTop()-offset);else scroll.scrollTo(0,oldY);});}
    }
  }
  static final class Row {
    final Activity a;final LinearLayout card;final ImageView icon;final TextView name,status,time,progressText,reason,stale,location,arrow;final Button menu;final ProgressBar progress;JSONObject value;String appearance="";
    Row(Activity a,SavedFileActions actions){
      this.a=a;card=DesignUi.card(a);LinearLayout top=DesignUi.row(a);icon=DesignUi.icon(a,"download",DesignUi.GREEN,36);top.addView(icon);LinearLayout labels=DesignUi.column(a);labels.setPadding(DesignUi.dp(a,12),0,DesignUi.dp(a,8),0);name=ReferenceUi.text(a,"",16,DesignUi.TEXT,true);name.setMaxLines(3);name.setEllipsize(android.text.TextUtils.TruncateAt.END);labels.addView(name);status=DesignUi.text(a,"",13,DesignUi.MUTED);status.setPadding(0,DesignUi.dp(a,5),0,0);labels.addView(status);time=DesignUi.text(a,"",12,DesignUi.MUTED);time.setPadding(0,DesignUi.dp(a,5),0,0);labels.addView(time);top.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
      menu=ReferenceUi.more(a,()->actions.show(value));top.addView(menu,new LinearLayout.LayoutParams(DesignUi.dp(a,48),DesignUi.dp(a,48)));arrow=DesignUi.text(a,"",22,DesignUi.GREEN);Ui.Icon disclosure=new Ui.Icon("chevron-right",DesignUi.MUTED);disclosure.setBounds(0,0,DesignUi.dp(a,18),DesignUi.dp(a,18));arrow.setCompoundDrawables(disclosure,null,null,null);arrow.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);top.addView(arrow);card.addView(top);
      progress=new ProgressBar(a,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(DesignUi.BLUE));progress.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(DesignUi.LINE));LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,DesignUi.dp(a,6));pp.topMargin=DesignUi.dp(a,14);card.addView(progress,pp);progressText=DesignUi.text(a,"",13,DesignUi.MUTED);progressText.setPadding(0,DesignUi.dp(a,8),0,0);card.addView(progressText);reason=DesignUi.text(a,"",13,DesignUi.RED);reason.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);card.addView(reason);stale=DesignUi.text(a,"记录待刷新，点按核对任务",13,DesignUi.MUTED);card.addView(stale);location=DesignUi.text(a,"",12,DesignUi.MUTED);location.setMaxLines(3);location.setPadding(0,DesignUi.dp(a,8),0,0);card.addView(location);
      card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->open(a,value,actions));
    }
    void bind(JSONObject row,long now){
      value=row;String state=row.optString("state");boolean saved="saved".equals(state);int color="failed".equals(state)?DesignUi.RED:saved?DesignUi.CYAN:DesignUi.GREEN;
      String next=(saved?"file":"download")+":"+color;if(!next.equals(appearance)){appearance=next;icon.setImageDrawable(new Ui.Icon(saved?"file":"download",color));icon.setBackground(DesignUi.surface(a,(color&0xffffff)|0x11000000,10,android.graphics.Color.TRANSPARENT));arrow.setTextColor(color);}
      text(name,row.optString("name","文件"));text(status,Profiles.display(a,row.optInt("slot"))+" · "+DownloadTasks.label(state));text(time,timeLabel(row));menu.setContentDescription("管理 "+row.optString("name","文件"));visible(menu,saved);visible(arrow,!saved);
      visible(progress,!saved);visible(progressText,!saved);visible(reason,!saved&&!row.optString("reason").isEmpty());visible(stale,!saved&&busy(state)&&row.optLong("updated")>0&&now-row.optLong("updated")>15000);visible(location,saved);
      long total=row.optLong("total",-1),received=row.optLong("received");boolean indefinite=total<=0&&busy(state);if(progress.isIndeterminate()!=indefinite)progress.setIndeterminate(indefinite);int percent=total>0?(int)Math.min(100,received*100/total):0;if(progress.getProgress()!=percent)progress.setProgress(percent);text(progressText,DownloadTasks.progress(row));text(reason,row.optString("reason"));text(location,row.optString("location","原先选择的保存位置"));
    }
    static void text(TextView view,String value){if(!android.text.TextUtils.equals(view.getText(),value))view.setText(value);}
    static void visible(View view,boolean value){int visibility=value?View.VISIBLE:View.GONE;if(view.getVisibility()!=visibility)view.setVisibility(visibility);}
  }
  static AlertDialog folder(Activity a){return DesignUi.message(a,"保存位置","默认位置："+(Build.VERSION.SDK_INT>=29?"Download/元婴期院士/窗口_编号/":"各窗口的应用内文件目录")+"\n\n点文件右侧菜单可打开、分享、另存为或删除。每个文件卡片显示它实际的保存位置。");}
}
