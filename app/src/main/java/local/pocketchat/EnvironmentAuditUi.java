package local.pocketchat;

import android.app.*;
import android.content.*;
import android.widget.*;

final class EnvironmentAuditUi {
  static void show(MainActivity a){EnvironmentAudit audit=a.session.audit;LinearLayout box=new LinearLayout(a);box.setOrientation(1);box.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(12));TextView info=a.label(audit.summary(),14,Ui.INK);info.setLineSpacing(a.dp(4),1);
    TextView explanation=a.label("\n网络检查会访问 ipify 和 httpbin，检测服务能看到出口 IP 和必要请求信息。检查请求不主动携带 Cookie、密码或聊天内容。确认基线只更新变化参照，不会修复检查发现的问题。",13,Ui.MUTED);box.addView(explanation);
    Button local=new Button(a);local.setText("检查浏览器信息（本机）");box.addView(local);CheckBox consent=new CheckBox(a);consent.setText("仅本次允许向 ipify / httpbin 发送出口 IP 与必要请求信息");consent.setChecked(false);box.addView(consent);Button network=new Button(a);network.setText("检查实际网络出口");network.setEnabled(false);box.addView(network);Button baseline=new Button(a);baseline.setText("确认当前环境，更新基线");box.addView(baseline);box.addView(info);ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("环境自检与变更").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("复制简要结果",(d,w)->{((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("环境自检",audit.safeCopy()));}).create();Runnable update=()->{if(!dialog.isShowing()||a.destroyed)return;info.setText(audit.summary());local.setEnabled(!audit.running);network.setEnabled(!audit.running&&consent.isChecked());baseline.setEnabled(!audit.running);};
    consent.setOnCheckedChangeListener((button,checked)->{if(!checked&&audit.running&&audit.networkRun)audit.cancel();update.run();});local.setOnClickListener(v->{audit.start(false,update);update.run();});network.setOnClickListener(v->{if(!consent.isChecked())return;if(ProfileUi.working(a.session)){info.setText("当前有回复、上传或下载任务，请完成后再进行网络检查。");return;}audit.start(true,update);update.run();});baseline.setOnClickListener(v->{audit.acceptBaseline();update.run();NetworkMetricsUi.update(a);});dialog.setOnDismissListener(d->audit.cancel());dialog.show();
  }
}
