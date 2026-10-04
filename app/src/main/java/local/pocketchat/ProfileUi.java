package local.pocketchat;

import android.app.*;
import android.widget.*;
import android.view.WindowManager;
import java.util.concurrent.*;

final class ProfileUi {
  static void show(MainActivity a){a.startActivity(new android.content.Intent(a,WindowHomeActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  static void activate(MainActivity a,int target){if(target==Profiles.slot(a))return;if(android.os.Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}android.content.Context dest=Profiles.context(a,target);if(ProfileCatalog.get(a).item(target).optBoolean("created")&&dest.getSharedPreferences("chat",0).getBoolean("environmentInitialized",target==0)){Profiles.open(a,target);return;}
    CheckBox copy=new CheckBox(a);copy.setText("复制当前网络配置，不复制登录和聊天数据");copy.setChecked(true);copy.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(8));
    new AlertDialog.Builder(a).setTitle("准备 "+Profiles.display(a,target)).setView(copy).setPositiveButton("打开",(dialog,which)->{boolean clone=copy.isChecked();a.loading.task("正在准备独立环境…");ExecutorService worker=Executors.newSingleThreadExecutor();worker.execute(()->{String error="";try{Profiles.prepare(a,target,clone);}catch(Exception e){error="独立环境网络配置准备失败，请稍后重试";}String failure=error;a.handler.post(()->{a.loading.dismissTask();if(!failure.isEmpty())a.status(failure);else Profiles.open(a,target);});worker.shutdown();});}).setNegativeButton("取消",null).show();}
  static void rename(MainActivity a,int slot){EditText name=new EditText(a);name.setSingleLine(true);name.setText(Profiles.display(a,slot));new AlertDialog.Builder(a).setTitle("环境名称（最多 24 字）").setView(name).setPositiveButton("保存",(d,w)->Profiles.rename(a,slot,name.getText().toString())).setNegativeButton("取消",null).show();}
  static boolean working(ChatSession s){return s.pending!=null||s.submitting||s.operation||s.transferActive||s.uploading();}
  static void privacy(MainActivity a){EnvironmentEditorUi.editTab(a,EnvironmentEditorUi.BROWSER);}
  static void status(MainActivity a){TextView info=a.label(a.session.privacy.summary(),14,Ui.INK);info.setPadding(a.dp(20),a.dp(10),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(info);new AlertDialog.Builder(a).setTitle("网络与保护状态").setView(scroll).setPositiveButton("保护设置",(d,w)->privacy(a)).setNegativeButton("关闭",null).show();}
}
