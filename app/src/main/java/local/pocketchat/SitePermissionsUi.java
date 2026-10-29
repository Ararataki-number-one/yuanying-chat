package local.pocketchat;

import android.app.*;
import android.os.Bundle;
import android.widget.*;

/** On-demand controls for the current environment and exact HTTPS origin. No navigation or probes. */
final class SitePermissionsUi {
  private SitePermissionsUi() {}
  static void show(MainActivity activity) {
    ChatSession owner=activity.session;
    if(owner==null||!EnvironmentIdentityUi.current(activity,owner))return;
    GeckoSitePermissions backend=new GeckoSitePermissions(owner.web,activity);
    SitePermissions.Scope scope=backend.current();
    LinearLayout body=new LinearLayout(activity);body.setOrientation(LinearLayout.VERTICAL);
    body.setPadding(activity.dp(18),activity.dp(10),activity.dp(18),activity.dp(16));
    TextView environment=activity.label(Profiles.display(activity,Profiles.slot(activity))
        +(scope==null?"":scope.privateMode?" · 隐私浏览":" · 普通浏览"),13,Ui.MUTED);body.addView(environment);
    TextView heading=activity.label(scope==null?"当前网页尚未就绪。打开此环境中的 HTTPS 网页后，可查看该站点的权限。":scope.origin,16,Ui.INK);
    heading.setTextIsSelectable(true);body.addView(heading);
    TextView capability=activity.label("摄像头、麦克风、位置获取：当前版本不提供。选择系统文件不等于授予这些权限。",13,Ui.MUTED);
    capability.setPadding(0,activity.dp(10),0,activity.dp(8));body.addView(capability);
    TextView info=activity.label(scope==null?"环境未运行、页面切换或不支持的地址时，不读取其他环境的记录。":"正在读取此站点的原生权限…",14,Ui.INK);
    info.setLineSpacing(activity.dp(3),1);body.addView(info);
    Button refresh=EnvironmentAuditUi.button(activity,body,"重新读取权限");
    LinearLayout rows=new LinearLayout(activity);rows.setOrientation(LinearLayout.VERTICAL);body.addView(rows);
    TextView note=activity.label("仅管理内核已保存的记录，不新增允许。恢复默认由内核决定后续行为；已进行中的网站操作不一定立即停止。不会刷新聊天或清除登录。",12,Ui.MUTED);
    note.setPadding(0,activity.dp(12),0,0);body.addView(note);
    ScrollView scroll=new ScrollView(activity);scroll.addView(body);
    AlertDialog dialog=AppAppearance.dialog(activity).setTitle("站点权限").setView(scroll).setPositiveButton("关闭",null).create();
    SitePermissions.Manager manager=new SitePermissions.Manager(backend,scope);
    AlertDialog[] confirmation={null};
    Application.ActivityLifecycleCallbacks lifecycle=new Application.ActivityLifecycleCallbacks(){
      public void onActivityPaused(Activity changed){if(changed==activity){manager.close();dialog.dismiss();}}
      public void onActivityDestroyed(Activity changed){if(changed==activity){manager.close();dialog.dismiss();}}
      public void onActivityCreated(Activity changed,Bundle state){}
      public void onActivityStarted(Activity changed){}
      public void onActivityResumed(Activity changed){}
      public void onActivityStopped(Activity changed){}
      public void onActivitySaveInstanceState(Activity changed,Bundle state){}
    };
    class Panel {
      boolean available(){return dialog.isShowing()&&activity.active&&owner.uiVisible&&EnvironmentIdentityUi.current(activity,owner)&&activity.remote==owner.web;}
      void busy(String message){rows.removeAllViews();refresh.setEnabled(false);info.setText(message);}
      void display(SitePermissions.Result result) {
        if(!available())return;
        info.setText(result.message);rows.removeAllViews();refresh.setEnabled(manager.current());
        for(SitePermissions.Entry row:result.entries) {
          TextView title=activity.label(row.title()+" · "+row.valueLabel(),15,Ui.INK);
          title.setPadding(0,activity.dp(14),0,activity.dp(4));rows.addView(title);
          if(row.thirdPartyOrigin!=null) {
            TextView third=activity.label("第三方来源："+row.thirdPartyOrigin,12,Ui.MUTED);third.setTextIsSelectable(true);rows.addView(third);
          }
          if(row.permits(SitePermissions.DENY)&&row.value!=SitePermissions.DENY) {
            Button deny=EnvironmentAuditUi.button(activity,rows,row.type==7?"取消跟踪保护例外":"拒绝此权限");
            deny.setOnClickListener(v->confirm(row,SitePermissions.DENY));
          }
          if(row.permits(SitePermissions.DEFAULT)&&row.value!=SitePermissions.DEFAULT) {
            Button reset=EnvironmentAuditUi.button(activity,rows,"恢复内核默认");reset.setOnClickListener(v->confirm(row,SitePermissions.DEFAULT));
          }
          if(!row.permits(SitePermissions.DENY)&&!row.permits(SitePermissions.DEFAULT)) {
            rows.addView(activity.label(row.type==2?"内核不支持撤销已授予的持久存储；此处只读。":"此项保持现有内核策略，此处只读。",12,Ui.MUTED));
          }
        }
      }
      void confirm(SitePermissions.Entry row,int value) {
        if(!available())return;
        if(!manager.current()){manager.refresh(this::display);return;}
        String action=value==SitePermissions.DEFAULT?"恢复内核默认":row.type==7?"取消跟踪保护例外":"拒绝此权限";
        String detail=scope.origin+"\n"+row.title()+(row.thirdPartyOrigin==null?"":"\n第三方来源："+row.thirdPartyOrigin)
            +"\n\n仅改变当前环境的这条原生记录。第三方存储变化可能影响网站登录；不会自动重新加载页面。";
        if(confirmation[0]!=null)confirmation[0].dismiss();
        confirmation[0]=AppAppearance.dialog(activity).setTitle(action).setMessage(detail).setNegativeButton("取消",null)
            .setPositiveButton(action,(d,w)->{if(!available())return;busy("正在请求设置并核对原生回读…");manager.change(row,value,this::display);}).create();
        confirmation[0].show();
      }
      void read(){if(!available()||!manager.current())return;busy("正在读取此站点的原生权限…");manager.refresh(this::display);}
    }
    Panel panel=new Panel();refresh.setEnabled(scope!=null);refresh.setOnClickListener(v->panel.read());
    dialog.setOnDismissListener(d->{manager.close();if(confirmation[0]!=null)confirmation[0].dismiss();activity.getApplication().unregisterActivityLifecycleCallbacks(lifecycle);});
    activity.getApplication().registerActivityLifecycleCallbacks(lifecycle);dialog.show();
    if(scope!=null)panel.read();
  }
}
