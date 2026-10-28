package local.pocketchat;

import android.app.*;
import android.content.*;
import android.widget.*;

/** Explicit local reports and self-reported checks; never runs probes or changes templates. */
final class FingerprintComparisonUi {
  private static final String[] SLOTS={"standard","enhanced"},SLOT_NAMES={"标准模式","强化模式"};
  private static final String[] MANUAL_KEYS={"login","input","attachment","drawing","recovery","restart","background"};
  private static final String[] MANUAL_LABELS={"账号登录","输入与输入法（含百度输入法）","添加与上传附件","页面绘图","页面恢复","重启后保持","后台返回后保持"};
  private static final String[] STATES={"not-tested","pass","fail","not-applicable"};
  private static final String[] STATE_LABELS={"尚未测试","人工操作正常","人工操作异常","本次不适用"};

  static void show(MainActivity a,EnvironmentAudit audit){
    ChatSession edited=a.session;if(!EnvironmentAuditUi.current(a,edited,audit))return;
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(16));
    TextView explanation=a.label("在同一手机、同一来源和版本下固定语言与网络，分别完成标准模式和已确认强化模式的深检，再主动保存到对应栏。此页只比较本地观测；不会切换模板、运行检测、打开网页或生成保护分数。",13,Ui.MUTED);box.addView(explanation);
    LinearLayout columns=new LinearLayout(a);columns.setOrientation(LinearLayout.HORIZONTAL);box.addView(columns);
    TextView[] slotInfo=new TextView[2],eligibility=new TextView[2];Button[] capture=new Button[2],clear=new Button[2],manual=new Button[2];
    for(int i=0;i<SLOTS.length;i++){
      LinearLayout column=new LinearLayout(a);column.setOrientation(LinearLayout.VERTICAL);column.setPadding(i==0?0:a.dp(6),a.dp(8),i==0?a.dp(6):0,a.dp(8));columns.addView(column,new LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1));
      column.addView(a.label(SLOT_NAMES[i],16,Ui.INK));slotInfo[i]=a.label("",13,Ui.INK);slotInfo[i].setLineSpacing(a.dp(3),1);column.addView(slotInfo[i]);
      capture[i]=EnvironmentAuditUi.button(a,column,"保存本次深检");eligibility[i]=a.label("",12,Ui.MUTED);column.addView(eligibility[i]);
      manual[i]=EnvironmentAuditUi.button(a,column,"记录人工兼容结果");clear[i]=EnvironmentAuditUi.button(a,column,"清除此栏记录");
    }
    TextView summary=a.label("",14,Ui.INK);summary.setLineSpacing(a.dp(4),1);summary.setPadding(0,a.dp(8),0,a.dp(8));box.addView(summary);
    TextView result=a.label("人工兼容记录默认“尚未测试”，仅代表你主动填写的操作结果，不等于软件已完成真机验收。可以保留未知，或只更新其中一项。",13,Ui.MUTED);box.addView(result);
    Button rawToggle=EnvironmentAuditUi.button(a,box,"展开原始对照记录");LinearLayout rawSection=EnvironmentAuditUi.section(a,box);TextView raw=a.label("",13,Ui.MUTED);rawSection.addView(raw);Button copy=EnvironmentAuditUi.button(a,rawSection,"复制本地双报告");
    ScrollView scroll=new ScrollView(a);scroll.addView(box);AlertDialog dialog=AppAppearance.dialog(a).setTitle("标准／强化本地对照").setView(scroll).setPositiveButton("关闭",null).create();
    Runnable update=()->{
      if(!EnvironmentAuditUi.current(a,edited,audit))return;
      for(int i=0;i<SLOTS.length;i++){
        String slot=SLOTS[i],issue=audit.comparisonCaptureIssue(slot);boolean has=audit.comparisonHas(slot);
        slotInfo[i].setText(audit.comparisonSlotSummary(slot));capture[i].setEnabled(!audit.running&&issue.isEmpty());
        eligibility[i].setText(audit.running?"当前检查正在进行，请完成后保存。":issue.isEmpty()?"本次有效深检可保存到此栏。":issue);
        clear[i].setEnabled(!audit.running&&has);manual[i].setEnabled(!audit.running&&has);
      }
      summary.setText(audit.comparisonSummary());copy.setEnabled(audit.comparisonHas("standard")||audit.comparisonHas("enhanced"));
      if(rawSection.getVisibility()==android.view.View.VISIBLE)raw.setText(audit.comparisonCopy());
    };
    for(int i=0;i<SLOTS.length;i++){
      final String slot=SLOTS[i],label=SLOT_NAMES[i];
      capture[i].setOnClickListener(v->{if(!EnvironmentAuditUi.current(a,edited,audit))return;Runnable save=()->{if(!EnvironmentAuditUi.current(a,edited,audit))return;String issue=audit.captureComparison(slot);result.setText(issue.isEmpty()?label+"本地深检已保存。人工兼容项目仍需你逐项操作和记录。":issue);update.run();};if(!audit.comparisonHas(slot))save.run();else AppAppearance.dialog(a).setTitle("替换"+label+"报告？").setMessage("将替换此栏已保存的报告及其人工兼容记录，另一栏与独立深检参照会保留。").setNegativeButton("取消",null).setPositiveButton("替换",(d,w)->save.run()).show();});
      clear[i].setOnClickListener(v->{if(!EnvironmentAuditUi.current(a,edited,audit))return;AppAppearance.dialog(a).setTitle("清除"+label+"记录？").setMessage("仅清除此栏的观测与人工兼容记录；另一栏、固定参照和最近八条观测会保留。").setNegativeButton("取消",null).setPositiveButton("清除",(d,w)->{if(!EnvironmentAuditUi.current(a,edited,audit))return;String issue=audit.clearComparison(slot);result.setText(issue.isEmpty()?label+"记录已清除。":issue);update.run();}).show();});
      manual[i].setOnClickListener(v->{if(EnvironmentAuditUi.current(a,edited,audit))manual(a,audit,edited,slot,label,result,update);});
    }
    rawToggle.setOnClickListener(v->{if(!EnvironmentAuditUi.current(a,edited,audit))return;EnvironmentAuditUi.toggle(rawSection,rawToggle,"展开原始对照记录","收起原始对照记录");update.run();});
    copy.setOnClickListener(v->{if(!EnvironmentAuditUi.current(a,edited,audit))return;((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("本地标准／强化对照",audit.comparisonCopy()));result.setText("本地双报告已复制；其中的人工兼容标记仅为自行记录。");});
    dialog.show();update.run();
  }

  private static void manual(MainActivity a,EnvironmentAudit audit,ChatSession edited,String slot,String label,TextView result,Runnable changed){
    AppAppearance.dialog(a).setTitle(label+"：选择人工检查项目").setItems(MANUAL_LABELS,(d,index)->{
      if(!EnvironmentAuditUi.current(a,edited,audit))return;
      AppAppearance.dialog(a).setTitle(MANUAL_LABELS[index]).setSingleChoiceItems(STATE_LABELS,-1,(choice,state)->{
        if(!EnvironmentAuditUi.current(a,edited,audit))return;String issue=audit.setComparisonManual(slot,MANUAL_KEYS[index],STATES[state]);
        result.setText(issue.isEmpty()?label+" · "+MANUAL_LABELS[index]+"："+STATE_LABELS[state]+"（自行记录）":issue);choice.dismiss();changed.run();
      }).setNegativeButton("取消",null).show();
    }).setNegativeButton("取消",null).show();
  }
}
