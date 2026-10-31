package local.pocketchat;

import android.app.*;
import android.widget.*;
import android.view.WindowManager;
import java.util.concurrent.*;

final class ProfileUi {
  static void manage(MainActivity a){a.startActivity(new android.content.Intent(a,WindowHomeActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  static ReferenceUi.Modal show(MainActivity a){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(a,"切换环境").asSheet();
    org.json.JSONArray rows=ProfileCatalog.get(a).list();
    LinearLayout list=DesignUi.group(a);dialog.body.addView(list);
    int current=Profiles.slot(a);
    for(int i=0;i<rows.length();i++){
      org.json.JSONObject item=rows.optJSONObject(i);if(item==null||!item.optBoolean("created")||item.optBoolean("deleting")||item.optBoolean("resetting"))continue;
      int slot=item.optInt("slot");String group=item.optString("group");
      String detail=(group.isEmpty()?"未分组":group)+(slot==AppSettings.defaultSlot(a)?" · 默认启动":"");
      LinearLayout choice=DesignUi.setting(a,"window",item.optString("name"),detail,slot==current?"当前":"",()->{dialog.dismiss();if(slot!=current)activate(a,slot);});
      choice.setSelected(slot==current);choice.setContentDescription(item.optString("name")+(slot==current?"，当前环境":"，切换到此环境"));
      DesignUi.groupedRow(list,choice);
    }
    dialog.buttons("",dialog::dismiss,"管理全部环境",()->{dialog.dismiss();manage(a);});
    dialog.show();return dialog;
  }
  static void activate(MainActivity a,int target){if(target==Profiles.slot(a))return;if(android.os.Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}android.content.Context dest=Profiles.context(a,target);if(ProfileCatalog.get(a).item(target).optBoolean("created")&&dest.getSharedPreferences("chat",0).getBoolean("environmentInitialized",target==0)){openManual(a,target);return;}
    CheckBox copy=new CheckBox(a);copy.setText("复制当前网络配置，不复制登录和聊天数据");copy.setChecked(true);copy.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(8));
    AppAppearance.dialog(a).setTitle("准备 "+Profiles.display(a,target)).setView(copy).setPositiveButton("打开",(dialog,which)->{boolean clone=copy.isChecked();a.loading.task("正在准备独立环境…");ExecutorService worker=Executors.newSingleThreadExecutor();worker.execute(()->{String error="";try{Profiles.prepare(a,target,clone);}catch(Exception e){error="独立环境网络配置准备失败，请稍后重试";}String failure=error;a.handler.post(()->{a.loading.dismissTask();if(!failure.isEmpty())a.status(failure);else openManual(a,target);});worker.shutdown();});}).setNegativeButton("取消",null).show();}
  /** Only the user's environment chooser requests an overview, never generic launches. */
  static void openManual(MainActivity a,int target){
    if(a.isDestroyed()||a.isFinishing()||!ProfileCatalog.get(a).available(target)||target==Profiles.slot(a))return;
    android.content.Intent opening=new android.content.Intent(a,Profiles.activity(target)).putExtra("openWindowAction","chat").addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK|android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
    EnvironmentOverviewUi.mark(opening,a,target);a.startActivity(opening);
  }
  static void rename(MainActivity a,int slot){EditText name=new EditText(a);name.setSingleLine(true);name.setText(Profiles.display(a,slot));AppAppearance.dialog(a).setTitle("环境名称（最多 24 字）").setView(name).setPositiveButton("保存",(d,w)->Profiles.rename(a,slot,name.getText().toString())).setNegativeButton("取消",null).show();}
  static boolean working(ChatSession s){return s.pending!=null||s.submitting||s.operation||s.transferActive||s.fileWorkActive();}
  static void privacy(MainActivity a){EnvironmentEditorUi.editTab(a,EnvironmentEditorUi.BROWSER);}
  static void status(MainActivity a){TextView info=a.label(a.session.privacy.summary(),14,Ui.INK);info.setPadding(a.dp(20),a.dp(10),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(info);AppAppearance.dialog(a).setTitle("网络与保护状态").setView(scroll).setPositiveButton("保护设置",(d,w)->privacy(a)).setNegativeButton("关闭",null).show();}
}
