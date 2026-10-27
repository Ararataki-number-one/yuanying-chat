package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.SystemClock;
import android.text.InputType;
import android.widget.*;
import org.json.*;

/** Explicit, bounded checks. No background fingerprint collection or automatic downgrade. */
final class EnvironmentAuditUi {
  static void show(MainActivity a){
    ChatSession edited=a.session;EnvironmentAudit audit=edited.audit;
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(12));
    TextView protection=a.label("",14,Ui.INK);protection.setLineSpacing(a.dp(4),1);box.addView(protection);
    Button retry=button(a,box,"重试强化保护确认"),standard=button(a,box,"主动改用标准模式");
    TextView policyResult=a.label("",13,Ui.MUTED);box.addView(policyResult);
    TextView explanation=a.label("\n本机检查只在点按后采集。图形与音频检查采用有限操作，不播放声音；结果可用或发生变化，不代表原生保护已通过或出现泄漏。",13,Ui.MUTED);box.addView(explanation);
    Button local=button(a,box,"检查浏览器信息（本机）"),deep=button(a,box,"检查图形与音频（本机）"),history=button(a,box,"查看最近观测与变化");
    TextView networkExplanation=a.label("\n网络出口检查会访问 ipify 和 httpbin，服务能看到出口 IP 与必要请求信息。请求不主动携带 Cookie、密码或聊天内容。",13,Ui.MUTED);box.addView(networkExplanation);
    CheckBox consent=new CheckBox(a);consent.setText("仅本次允许向 ipify / httpbin 发送检测信息");consent.setChecked(false);box.addView(consent);
    Button network=button(a,box,"检查实际网络出口");
    TextView identityExplanation=a.label("\n真实请求身份检查会暂时打开你选择的 HTTPS 检测页，对照主文档与 Dedicated Worker 的服务端请求信息；仅在没有草稿、附件和进行中任务时打开。该结果不代表 ChatGPT 官网请求。",13,Ui.MUTED);box.addView(identityExplanation);
    Button endpoint=button(a,box,"设置请求身份检测服务");
    CheckBox identityConsent=new CheckBox(a);identityConsent.setText("仅本次允许向所选服务发送 UA、语言与出口 IP");identityConsent.setChecked(audit.requestIdentityRunning());box.addView(identityConsent);
    Button identity=button(a,box,"打开真实请求检测页"),back=button(a,box,"返回原聊天");
    TextView identityResult=a.label("",13,Ui.MUTED);box.addView(identityResult);
    Button baseline=button(a,box,"确认当前环境，更新基线");
    TextView baselineNote=a.label("确认基线只更新变化参照，不会修复检查发现的问题。最近八次网页观测仅在当前环境本地加密保存。",13,Ui.MUTED);box.addView(baselineNote);
    TextView info=a.label("",14,Ui.INK);info.setLineSpacing(a.dp(4),1);box.addView(info);ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("环境自检与变更").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("复制简要结果",(d,w)->((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("环境自检",audit.safeCopy()))).create();
    boolean[] handoff={false},policySaving={false},consentWrite={false};Runnable[] protectionTick={null},identityTick={null};
    Runnable clearIdentityConsent=()->{consentWrite[0]=true;identityConsent.setChecked(false);consentWrite[0]=false;};
    Runnable update=()->{
      if(!dialog.isShowing()||a.destroyed||a.session!=edited||edited.deleted)return;
      protection.setText("原生保护："+edited.web.protectionSummary());JSONObject state=edited.web.protectionStatus();boolean pending="pending".equals(state.optString("state"));
      retry.setVisibility(edited.privacy.level()>=2&&"failed".equals(state.optString("state"))?android.view.View.VISIBLE:android.view.View.GONE);retry.setEnabled(!audit.running&&!pending&&state.optBoolean("retryAvailable"));
      standard.setVisibility(edited.privacy.level()>=2?android.view.View.VISIBLE:android.view.View.GONE);standard.setEnabled(!audit.running&&!policySaving[0]);
      local.setEnabled(!audit.running);deep.setEnabled(!audit.running);network.setEnabled(!audit.running&&consent.isChecked());baseline.setEnabled(!audit.running);endpoint.setEnabled(!audit.running);
      boolean identityRunning=audit.requestIdentityRunning();consent.setEnabled(!audit.running||audit.networkRun&&!identityRunning);identityConsent.setEnabled(!audit.running||identityRunning);
      String selected=audit.requestIdentityEndpoint();endpoint.setText(selected.isEmpty()?"设置请求身份检测服务":"检测服务："+selected);
      identity.setEnabled(!audit.running&&!selected.isEmpty()&&identityConsent.isChecked()&&!audit.canReturnRequestIdentity());back.setVisibility(audit.canReturnRequestIdentity()?android.view.View.VISIBLE:android.view.View.GONE);back.setEnabled(audit.canReturnRequestIdentity());
      identityResult.setText(audit.requestIdentitySummary(false));info.setText(audit.summary());
    };
    Runnable watchProtection=()->{
      if(protectionTick[0]!=null)edited.handler.removeCallbacks(protectionTick[0]);long started=SystemClock.elapsedRealtime();
      // Observe the entire bounded native handshake (three 8s attempts plus backoff).
      // This is a UI observation limit; it does not extend native protection deadlines.
      protectionTick[0]=new Runnable(){public void run(){if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;update.run();if("pending".equals(edited.web.protectionStatus().optString("state"))&&SystemClock.elapsedRealtime()-started<40000)edited.handler.postDelayed(this,500);}};edited.handler.post(protectionTick[0]);
    };
    consent.setOnCheckedChangeListener((view,checked)->{if(!checked&&audit.running&&audit.networkRun&&!audit.requestIdentityRunning())audit.cancel();update.run();});
    identityConsent.setOnCheckedChangeListener((view,checked)->{if(!consentWrite[0]&&!checked&&audit.requestIdentityRunning())audit.cancel();update.run();});
    local.setOnClickListener(v->{audit.start(false,update);update.run();});deep.setOnClickListener(v->{audit.start(false,true,update);update.run();});
    network.setOnClickListener(v->{if(!consent.isChecked())return;if(ProfileUi.working(edited)){info.setText("当前有回复、上传或下载任务，请完成后再进行网络检查。");return;}audit.start(true,update);update.run();});
    retry.setOnClickListener(v->{edited.web.retryProtection();update.run();watchProtection.run();});
    standard.setOnClickListener(v->{
      if(ProfileUi.working(edited)){policyResult.setText("当前有回复、上传或下载任务，请完成后再切换模板。");return;}
      policySaving[0]=true;standard.setEnabled(false);policyResult.setText("正在保存你选择的标准模板…");
      edited.environmentIo.execute(()->{BrowserIdentitySpec requested=null;String failure="";try{BrowserIdentitySpec old=BrowserIdentitySpec.from(new EnvironmentSpecRepository(edited.context).load().desired().browser());requested=BrowserIdentitySpec.preset(old.desktop()?BrowserIdentitySpec.DESKTOP:BrowserIdentitySpec.MOBILE).withLocales(old.locales);}catch(Exception unavailable){failure="模板无法读取，未改变保护设置。";}
        BrowserIdentitySpec selected=requested;String error=failure;edited.handler.post(()->{if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;if(!error.isEmpty()){policySaving[0]=false;standard.setEnabled(true);policyResult.setText(error);return;}edited.applyIdentityTemplate(a,selected,issue->{policySaving[0]=false;if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;policyResult.setText(issue==null||issue.isEmpty()?"标准模板已保存，实际状态见上方确认结果。":issue);update.run();watchProtection.run();});});
      });
    });
    endpoint.setOnClickListener(v->endpoint(a,audit,()->{clearIdentityConsent.run();update.run();}));
    identity.setOnClickListener(v->{
      if(!identityConsent.isChecked())return;
      if(!audit.startRequestIdentity(()->{clearIdentityConsent.run();update.run();})){clearIdentityConsent.run();update.run();return;}
      update.run();long started=SystemClock.elapsedRealtime();
      // This observes the existing 20.5s controller cleanup window; no task budget changes.
      identityTick[0]=new Runnable(){public void run(){if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;if(audit.requestIdentityNavigated()){handoff[0]=true;dialog.dismiss();return;}update.run();if(audit.running&&SystemClock.elapsedRealtime()-started<25000)edited.handler.postDelayed(this,100);}};edited.handler.post(identityTick[0]);
    });
    back.setOnClickListener(v->{if(audit.returnRequestIdentity()){handoff[0]=true;dialog.dismiss();}else update.run();});
    history.setOnClickListener(v->history(a,audit));baseline.setOnClickListener(v->{audit.acceptBaseline();update.run();NetworkMetricsUi.update(a);});
    dialog.setOnDismissListener(d->{if(protectionTick[0]!=null)edited.handler.removeCallbacks(protectionTick[0]);if(identityTick[0]!=null)edited.handler.removeCallbacks(identityTick[0]);if(!handoff[0])audit.cancel();});dialog.show();update.run();watchProtection.run();
  }
  static Button button(MainActivity a,LinearLayout box,String text){Button value=new Button(a);value.setText(text);box.addView(value);return value;}
  static void endpoint(MainActivity a,EnvironmentAudit audit,Runnable changed){
    EditText address=new EditText(a);address.setSingleLine(true);address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);address.setHint("https://你的检测服务地址");address.setText(audit.requestIdentityEndpoint());address.setPadding(a.dp(20),a.dp(12),a.dp(20),a.dp(12));
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("请求身份检测服务").setMessage("只使用你信任的 HTTPS 服务。地址为空时不发送检测请求；每次打开检测页仍需单独同意。服务端只应记录本次 UA、语言与出口，不应收集账号或聊天。这里保存地址不会开始检测。").setView(address).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
    dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{String issue=audit.setRequestIdentityEndpoint(address.getText().toString().trim());if(issue!=null&&!issue.isEmpty()){address.setError(issue);return;}dialog.dismiss();changed.run();}));dialog.show();
  }
  static void history(MainActivity a,EnvironmentAudit audit){TextView text=a.label(FingerprintObservationHistory.summary(audit.observationHistory),14,Ui.INK);text.setLineSpacing(a.dp(4),1);text.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(text);AppAppearance.dialog(a).setTitle("最近的网页观测").setView(scroll).setPositiveButton("关闭",null).show();}
}
