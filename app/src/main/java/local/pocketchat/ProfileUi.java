package local.pocketchat;

import android.app.*;
import android.widget.*;
import android.view.WindowManager;
import java.util.concurrent.*;

final class ProfileUi {
  static void show(MainActivity a){int current=Profiles.slot(a);String[] entries=new String[Profiles.MAX+5];for(int i=0;i<Profiles.MAX;i++)entries[i]=(i==current?"✓ ":"")+Profiles.display(a,i)+(i==0?" · 保留原有登录":" · 独立登录");entries[Profiles.MAX]="当前环境隐私保护";entries[Profiles.MAX+1]="重命名当前环境";entries[Profiles.MAX+2]="网络与保护状态";entries[Profiles.MAX+3]="环境自检与变更"+(a.session.audit.hasChanges()?" · 需要核对":"");
    entries[Profiles.MAX+4]="编辑当前环境与偏好";new AlertDialog.Builder(a).setTitle("独立环境与隐私").setItems(entries,(dialog,index)->{if(index<Profiles.MAX){activate(a,index);return;}if(index==Profiles.MAX)privacy(a);if(index==Profiles.MAX+1)rename(a,current);if(index==Profiles.MAX+2)status(a);if(index==Profiles.MAX+3)EnvironmentAuditUi.show(a);if(index==Profiles.MAX+4)EnvironmentEditorUi.show(a);}).setNegativeButton("关闭",null).show();}
  static void activate(MainActivity a,int target){if(target==Profiles.slot(a))return;if(android.os.Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}android.content.Context dest=Profiles.context(a,target);if(dest.getSharedPreferences("chat",0).getBoolean("environmentInitialized",target==0)){Profiles.open(a,target);return;}
    CheckBox copy=new CheckBox(a);copy.setText("复制当前网络配置，不复制登录和聊天数据");copy.setChecked(true);copy.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(8));
    new AlertDialog.Builder(a).setTitle("准备 "+Profiles.display(a,target)).setView(copy).setPositiveButton("打开",(dialog,which)->{boolean clone=copy.isChecked();a.loading.task("正在准备独立环境…");ExecutorService worker=Executors.newSingleThreadExecutor();worker.execute(()->{String error="";try{Profiles.prepare(a,target,clone);}catch(Exception e){error="独立环境网络配置准备失败，请稍后重试";}String failure=error;a.handler.post(()->{a.loading.dismissTask();if(!failure.isEmpty())a.status(failure);else Profiles.open(a,target);});worker.shutdown();});}).setNegativeButton("取消",null).show();}
  static void rename(MainActivity a,int slot){EditText name=new EditText(a);name.setSingleLine(true);name.setText(Profiles.display(a,slot));new AlertDialog.Builder(a).setTitle("环境名称（最多 24 字）").setView(name).setPositiveButton("保存",(d,w)->Profiles.rename(a,slot,name.getText().toString())).setNegativeButton("取消",null).show();}
  static boolean working(ChatSession s){return s.pending!=null||s.submitting||s.operation||s.transferActive||s.uploading();}
  static void privacy(MainActivity a){ChatSession s=a.session;if(working(s)){a.status("当前有未完成任务，结束后再修改保护等级");return;}String[] modes={"兼容：系统 UA，保留原有权限限制","标准：防泄漏，限制 WebRTC 与电量、网络信息","强化：限制 Canvas / 音频读取，可能影响图片、朗读或验证"};int[] selected={s.privacy.level()};
    new AlertDialog.Builder(a).setTitle("当前环境保护等级").setSingleChoiceItems(modes,selected[0],(d,w)->selected[0]=w).setPositiveButton("应用并重新加载",(d,w)->{if(working(s)){a.status("当前有未完成任务，请稍后再改");return;}if(selected[0]>0&&(!s.privacy.earlySupported()||!s.guard.workerProtection)){a.status("标准 / 强化保护需要更新 Android System WebView；当前设置未改动");return;}s.prefs.edit().putInt("privacyLevel",selected[0]).apply();s.invalidateConnection();s.privacy.apply();s.openConnection(true,true);}).setNegativeButton("取消",null).show();}
  static void status(MainActivity a){TextView info=a.label(a.session.privacy.summary(),14,Ui.INK);info.setPadding(a.dp(20),a.dp(10),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(info);new AlertDialog.Builder(a).setTitle("网络与保护状态").setView(scroll).setPositiveButton("保护设置",(d,w)->privacy(a)).setNegativeButton("关闭",null).show();}
}
