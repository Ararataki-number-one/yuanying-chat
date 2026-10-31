package local.pocketchat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** The app-wide optional detector is never copied into an environment's preferences. */
final class BackgroundReplySettingsUi {
  static String summary(Context c){return summary(BackgroundReplyPolicy.refresh(c));}
  static String summary(BackgroundReplyPolicy.Snapshot value){return !value.known?"暂未读取 · 按关闭处理":value.enabled?"已开启 · 所有环境":"已关闭 · 所有环境";}
  static void open(Activity activity,Runnable refresh){
    LinearLayout box=DesignUi.column(activity);box.setPadding(DesignUi.dp(activity,18),0,DesignUi.dp(activity,18),DesignUi.dp(activity,14));
    Switch enabled=new Switch(activity);enabled.setText("后台回复检测");NativeControls.prepare(enabled);
    BackgroundReplyPolicy.Snapshot initial=BackgroundReplyPolicy.refresh(activity);enabled.setChecked(initial.enabled);box.addView(enabled);
    DesignUi.note(box,"此开关对所有环境生效，默认关闭。关闭后，前台聊天、网页正在生成的回复、文件任务和代理连接继续运行。回复完成提醒需另行开启。");
    TextView status=ReferenceUi.text(activity,summary(initial),13,DesignUi.MUTED,false);box.addView(status);
    AlertDialog dialog=AppAppearance.dialog(activity).setTitle("后台回复检测").setView(box).setPositiveButton("完成",null).create();
    ExecutorService worker=Executors.newSingleThreadExecutor();Handler main=new Handler(Looper.getMainLooper());boolean[] binding={false};
    enabled.setOnCheckedChangeListener((button,value)->{
      if(binding[0])return;enabled.setEnabled(false);status.setText("正在保存…");
      worker.execute(()->{
        BackgroundReplyPolicy.Snapshot saved;boolean failed=false;
        try{saved=BackgroundReplyPolicy.setEnabled(activity,value);}catch(RuntimeException unavailable){failed=true;saved=BackgroundReplyPolicy.refresh(activity);}
        BackgroundReplyPolicy.Snapshot actual=saved;boolean saveFailed=failed;
        main.post(()->{
          if(activity.isFinishing()||activity.isDestroyed())return;
          if(dialog.isShowing()){
            binding[0]=true;enabled.setChecked(actual.enabled);binding[0]=false;enabled.setEnabled(true);
            status.setText(saveFailed?"保存失败，请重试。"+summary(actual):summary(actual));
          }
          refresh.run();
        });
      });
    });
    dialog.setOnDismissListener(ignored->worker.shutdown());dialog.show();
  }
}
