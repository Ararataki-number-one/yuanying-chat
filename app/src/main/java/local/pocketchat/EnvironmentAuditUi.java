package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.SystemClock;
import android.text.InputType;
import android.widget.*;
import org.json.*;

/** Explicit, bounded checks. No background fingerprint collection or automatic downgrade. */
final class EnvironmentAuditUi {
  static boolean current(MainActivity a,ChatSession edited,EnvironmentAudit audit){return !a.destroyed&&a.session==edited&&audit.session==edited&&!edited.deleted;}
  static void show(MainActivity a){
    ChatSession edited=a.session;EnvironmentAudit audit=edited.audit;
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(12));
    TextView protection=a.label("",14,Ui.INK);protection.setLineSpacing(a.dp(4),1);box.addView(protection);
    Button retry=button(a,box,"重试强化保护确认"),standard=button(a,box,"主动改用标准模式");
    TextView policyResult=a.label("",13,Ui.MUTED);box.addView(policyResult);
    TextView explanation=a.label("\n本机检查只在点按后采集。图形与音频检查采用有限操作，不播放声音；结果可用或发生变化，不代表原生保护已通过或出现泄漏。",13,Ui.MUTED);box.addView(explanation);
    Button local=button(a,box,"检查浏览器信息（本机）"),deep=button(a,box,"检查图形与音频（本机）"),history=button(a,box,"查看最近观测与变化"),fixed=button(a,box,"固定深检参照与比较"),copyDeep=button(a,box,"复制深检原始记录");
    TextView networkExplanation=a.label("\n网络出口检查会访问 ipify 和 httpbin，服务能看到出口 IP 与必要请求信息。请求不主动携带 Cookie、密码或聊天内容。",13,Ui.MUTED);box.addView(networkExplanation);
    CheckBox consent=new CheckBox(a);consent.setText("仅本次允许向 ipify / httpbin 发送检测信息");consent.setChecked(false);box.addView(consent);
    Button network=button(a,box,"检查实际网络出口");
    TextView identityExplanation=a.label("\n真实请求身份检查会暂时打开你选择的 HTTPS 检测页，对照主文档与 Dedicated Worker 的服务端请求信息；仅在没有草稿、附件和进行中任务时打开。该结果不代表 ChatGPT 官网请求。",13,Ui.MUTED);box.addView(identityExplanation);
    Button endpoint=button(a,box,"设置请求身份检测服务"),serviceCheck=button(a,box,"检查检测服务（不离开聊天）"),frameEndpoint=button(a,box,"设置跨源 iframe 检测来源");
    CheckBox identityConsent=new CheckBox(a);identityConsent.setText("仅本次允许向所选服务发送 UA、语言与出口 IP");identityConsent.setChecked(audit.requestIdentityRunning());box.addView(identityConsent);
    CheckBox frameConsent=new CheckBox(a);frameConsent.setText("仅本次允许访问第二 HTTPS 来源，检查跨源 iframe 图形");box.addView(frameConsent);
    Button identity=button(a,box,"打开真实请求检测页"),crossFrame=button(a,box,"打开跨源 iframe 图形检测"),back=button(a,box,"返回原聊天");
    TextView identityResult=a.label("",13,Ui.MUTED);box.addView(identityResult);
    Button baseline=button(a,box,"确认当前环境，更新基线");
    TextView baselineNote=a.label("确认基线只更新变化参照，不会修复检查发现的问题。最近八次网页观测仅在当前环境本地加密保存。固定深检参照单独保留，需主动保存或清除。",13,Ui.MUTED);box.addView(baselineNote);
    TextView info=a.label("",14,Ui.INK);info.setLineSpacing(a.dp(4),1);box.addView(info);ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("环境自检与变更").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("复制简要结果",(d,w)->{if(current(a,edited,audit))((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("环境自检",audit.safeCopy()));}).create();
    boolean[] handoff={false},policySaving={false},consentWrite={false},crossStarting={false};Runnable[] protectionTick={null},identityTick={null};
    Runnable clearIdentityConsent=()->{consentWrite[0]=true;identityConsent.setChecked(false);frameConsent.setChecked(false);crossStarting[0]=false;consentWrite[0]=false;};
    Runnable update=()->{
      if(!dialog.isShowing()||a.destroyed||a.session!=edited||edited.deleted)return;
      protection.setText("原生保护："+edited.web.protectionSummary());JSONObject state=edited.web.protectionStatus();boolean pending="pending".equals(state.optString("state"));
      retry.setVisibility(edited.privacy.level()>=2&&"failed".equals(state.optString("state"))?android.view.View.VISIBLE:android.view.View.GONE);retry.setEnabled(!audit.running&&!pending&&state.optBoolean("retryAvailable"));
      standard.setVisibility(edited.privacy.level()>=2?android.view.View.VISIBLE:android.view.View.GONE);standard.setEnabled(!audit.running&&!policySaving[0]);
      local.setEnabled(!audit.running);deep.setEnabled(!audit.running);network.setEnabled(!audit.running&&consent.isChecked());baseline.setEnabled(!audit.running);endpoint.setEnabled(!audit.running);
      boolean identityRunning=audit.requestIdentityRunning(),serviceRunning=audit.serviceProbeRunning();consent.setEnabled(!audit.running||audit.networkRun&&!identityRunning&&!serviceRunning);identityConsent.setEnabled(!audit.running||identityRunning||serviceRunning);frameConsent.setEnabled(!audit.running||crossStarting[0]);
      String selected=audit.requestIdentityEndpoint();endpoint.setText(selected.isEmpty()?"设置请求身份检测服务":"检测服务："+selected);
      identity.setEnabled(!audit.running&&!selected.isEmpty()&&identityConsent.isChecked()&&!audit.canReturnRequestIdentity());back.setVisibility(audit.canReturnRequestIdentity()?android.view.View.VISIBLE:android.view.View.GONE);back.setEnabled(audit.canReturnRequestIdentity());
      serviceCheck.setEnabled(!audit.running&&!selected.isEmpty()&&identityConsent.isChecked()&&!audit.canReturnRequestIdentity());frameEndpoint.setEnabled(!audit.running);frameEndpoint.setText(audit.requestIdentityFrameEndpoint().isEmpty()?"设置跨源 iframe 检测来源":"第二检测来源："+audit.requestIdentityFrameEndpoint());
      crossFrame.setEnabled(!audit.running&&!selected.isEmpty()&&!audit.requestIdentityFrameEndpoint().isEmpty()&&identityConsent.isChecked()&&frameConsent.isChecked()&&!audit.canReturnRequestIdentity());fixed.setEnabled(!audit.running);copyDeep.setEnabled(!audit.running&&audit.hasDeepRecord());
      identityResult.setText(audit.serviceProbeSummary(false)+"\n\n"+audit.requestIdentitySummary(false));info.setText(audit.summary());
    };
    Runnable watchProtection=()->{
      if(protectionTick[0]!=null)edited.handler.removeCallbacks(protectionTick[0]);long started=SystemClock.elapsedRealtime();
      // Observe the entire bounded native handshake (three 8s attempts plus backoff).
      // This is a UI observation limit; it does not extend native protection deadlines.
      protectionTick[0]=new Runnable(){public void run(){if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;update.run();if("pending".equals(edited.web.protectionStatus().optString("state"))&&SystemClock.elapsedRealtime()-started<40000)edited.handler.postDelayed(this,500);}};edited.handler.post(protectionTick[0]);
    };
    consent.setOnCheckedChangeListener((view,checked)->{if(!checked&&audit.running&&audit.networkRun&&!audit.requestIdentityRunning()&&!audit.serviceProbeRunning())audit.cancel();update.run();});
    identityConsent.setOnCheckedChangeListener((view,checked)->{if(!consentWrite[0]&&!checked&&(audit.requestIdentityRunning()||audit.serviceProbeRunning()))audit.cancel();update.run();});
    local.setOnClickListener(v->{if(!current(a,edited,audit))return;audit.start(false,update);update.run();});deep.setOnClickListener(v->{if(!current(a,edited,audit))return;audit.start(false,true,update);update.run();});
    network.setOnClickListener(v->{if(!current(a,edited,audit))return;if(!consent.isChecked())return;if(ProfileUi.working(edited)){info.setText("当前有回复、上传或下载任务，请完成后再进行网络检查。");return;}audit.start(true,update);update.run();});
    retry.setOnClickListener(v->{if(!current(a,edited,audit))return;edited.web.retryProtection();update.run();watchProtection.run();});
    standard.setOnClickListener(v->{if(!current(a,edited,audit))return;
      if(ProfileUi.working(edited)){policyResult.setText("当前有回复、上传或下载任务，请完成后再切换模板。");return;}
      policySaving[0]=true;standard.setEnabled(false);policyResult.setText("正在保存你选择的标准模板…");
      edited.environmentIo.execute(()->{BrowserIdentitySpec requested=null;String failure="";try{BrowserIdentitySpec old=BrowserIdentitySpec.from(new EnvironmentSpecRepository(edited.context).load().desired().browser());requested=BrowserIdentitySpec.preset(old.desktop()?BrowserIdentitySpec.DESKTOP:BrowserIdentitySpec.MOBILE).withLocales(old.locales);}catch(Exception unavailable){failure="模板无法读取，未改变保护设置。";}
        BrowserIdentitySpec selected=requested;String error=failure;edited.handler.post(()->{if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;if(!error.isEmpty()){policySaving[0]=false;standard.setEnabled(true);policyResult.setText(error);return;}edited.applyIdentityTemplate(a,selected,issue->{policySaving[0]=false;if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;policyResult.setText(issue==null||issue.isEmpty()?"标准模板已保存，实际状态见上方确认结果。":issue);update.run();watchProtection.run();});});
      });
    });
    endpoint.setOnClickListener(v->{if(current(a,edited,audit))endpoint(a,audit,()->{clearIdentityConsent.run();update.run();});});
    Runnable watchIdentity=()->{
      if(identityTick[0]!=null)edited.handler.removeCallbacks(identityTick[0]);long started=SystemClock.elapsedRealtime();
      identityTick[0]=new Runnable(){public void run(){if(!dialog.isShowing()||a.destroyed||a.session!=edited)return;if(audit.canReturnRequestIdentity()){handoff[0]=true;dialog.dismiss();return;}update.run();if(audit.running&&SystemClock.elapsedRealtime()-started<40000)edited.handler.postDelayed(this,100);}};edited.handler.post(identityTick[0]);
    };
    frameConsent.setOnCheckedChangeListener((view,checked)->{if(!consentWrite[0]&&!checked&&crossStarting[0])audit.cancel();update.run();});
    serviceCheck.setOnClickListener(v->{if(!current(a,edited,audit))return;if(!identityConsent.isChecked())return;audit.startServiceProbe(()->{clearIdentityConsent.run();update.run();});update.run();});
    frameEndpoint.setOnClickListener(v->{if(current(a,edited,audit))frameEndpoint(a,audit,()->{clearIdentityConsent.run();update.run();});});
    identity.setOnClickListener(v->{if(!current(a,edited,audit))return;if(!identityConsent.isChecked())return;if(!audit.startRequestIdentity(()->{clearIdentityConsent.run();update.run();})){clearIdentityConsent.run();update.run();return;}update.run();watchIdentity.run();});
    crossFrame.setOnClickListener(v->{if(!current(a,edited,audit))return;
      if(!identityConsent.isChecked()||!frameConsent.isChecked())return;crossStarting[0]=true;
      boolean started=audit.startServiceProbe(()->{
        if(!dialog.isShowing()||a.destroyed||a.session!=edited||!identityConsent.isChecked()||!frameConsent.isChecked()){clearIdentityConsent.run();return;}
        if(!audit.serviceProbe.supportsCrossOriginFrame(audit.requestIdentityFrameEndpoint())){audit.lastError="服务未确认支持已配置的第二 HTTPS 来源；原聊天没有离开。请查看服务检查结果。";clearIdentityConsent.run();update.run();return;}
        if(!audit.startCrossOriginRequestIdentity(()->{clearIdentityConsent.run();update.run();})){clearIdentityConsent.run();update.run();return;}update.run();
      });
      if(!started)clearIdentityConsent.run();update.run();if(started)watchIdentity.run();
    });
    back.setOnClickListener(v->{if(!current(a,edited,audit))return;if(audit.returnRequestIdentity()){handoff[0]=true;dialog.dismiss();}else update.run();});
    history.setOnClickListener(v->{if(current(a,edited,audit))history(a,audit);});fixed.setOnClickListener(v->{if(current(a,edited,audit))fixed(a,audit);});copyDeep.setOnClickListener(v->{if(!current(a,edited,audit))return;((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("本机深检记录",audit.deepRecordCopy()));policyResult.setText("已复制本机观测；请在同一手机分别运行标准与确认后的强化模式，并记录登录、输入、绘图、附件和恢复结果。");});baseline.setOnClickListener(v->{if(!current(a,edited,audit))return;audit.acceptBaseline();update.run();NetworkMetricsUi.update(a);});
    dialog.setOnDismissListener(d->{if(protectionTick[0]!=null)edited.handler.removeCallbacks(protectionTick[0]);if(identityTick[0]!=null)edited.handler.removeCallbacks(identityTick[0]);if(!handoff[0])audit.cancel();});dialog.show();update.run();watchProtection.run();
  }
  static Button button(MainActivity a,LinearLayout box,String text){Button value=new Button(a);value.setText(text);box.addView(value);return value;}
  static void endpoint(MainActivity a,EnvironmentAudit audit,Runnable changed){
    if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;
    EditText address=new EditText(a);address.setSingleLine(true);address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);address.setHint("https://你的检测服务地址");address.setText(audit.requestIdentityEndpoint());address.setPadding(a.dp(20),a.dp(12),a.dp(20),a.dp(12));
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("请求身份检测服务").setMessage("只使用你信任的 HTTPS 服务。地址为空时不发送检测请求；每次打开检测页仍需单独同意。服务端只应记录本次 UA、语言与出口，不应收集账号或聊天。这里保存地址不会开始检测。").setView(address).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
    dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;String issue=audit.setRequestIdentityEndpoint(address.getText().toString().trim());if(issue!=null&&!issue.isEmpty()){address.setError(issue);return;}dialog.dismiss();changed.run();}));dialog.show();
  }
  static void frameEndpoint(MainActivity a,EnvironmentAudit audit,Runnable changed){
    if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;
    EditText address=new EditText(a);address.setSingleLine(true);address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);address.setText(audit.requestIdentityFrameEndpoint());address.setHint("https://你信任的第二检测来源/pocketchat-identity/v1/");address.setPadding(a.dp(20),a.dp(12),a.dp(20),a.dp(12));
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("跨源 iframe 检测来源").setMessage("使用你信任的第二 HTTPS 来源，且须与主检测服务的能力声明一致。只有点按跨源检测并本次同意后才会访问；会打开受控检测页，结束后由你返回聊天。").setView(address).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
    dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;String issue=audit.setRequestIdentityFrameEndpoint(address.getText().toString().trim());if(!issue.isEmpty()){address.setError(issue);return;}dialog.dismiss();changed.run();}));dialog.show();
  }
  static void fixed(MainActivity a,EnvironmentAudit audit){
    if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;
    ChatSession edited=a.session;LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(16));TextView text=a.label(audit.pinnedDeepSummary(),14,Ui.INK);box.addView(text);Button pin=button(a,box,"固定当前主页面深检为参照"),clear=button(a,box,"清除固定深检参照");TextView result=a.label("固定参照只对应主页面的同组观测；Worker 与 iframe 的结果分别显示，不比较跨环境哈希。",13,Ui.MUTED);box.addView(result);ScrollView scroll=new ScrollView(a);scroll.addView(box);AlertDialog dialog=AppAppearance.dialog(a).setTitle("固定深检参照").setView(scroll).setPositiveButton("关闭",null).create();
    Runnable update=()->{text.setText(audit.pinnedDeepSummary());pin.setEnabled(!audit.running&&audit.deepObservationCurrent());clear.setEnabled(!audit.running&&audit.pinnedDeepBaseline.length()>0);};
    Runnable capture=()->{if(a.destroyed||a.session!=edited||edited.deleted)return;String issue=audit.pinDeepObservation();result.setText(issue.isEmpty()?"固定深检参照已加密保存。":issue);update.run();};
    pin.setOnClickListener(v->{if(audit.pinnedDeepBaseline.length()==0)capture.run();else AppAppearance.dialog(a).setTitle("替换固定深检参照？").setMessage("会用当前有效主页面深检替换已固定的参照。").setNegativeButton("取消",null).setPositiveButton("替换",(d,w)->capture.run()).show();});
    clear.setOnClickListener(v->AppAppearance.dialog(a).setTitle("清除固定深检参照？").setMessage("最近八条观测记录会保留。").setNegativeButton("取消",null).setPositiveButton("清除",(d,w)->{if(a.destroyed||a.session!=edited||edited.deleted)return;String issue=audit.clearPinnedDeepBaseline();result.setText(issue.isEmpty()?"固定深检参照已清除。":issue);update.run();}).show());dialog.show();update.run();
  }
  static void history(MainActivity a,EnvironmentAudit audit){
    if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;
    ChatSession edited=a.session;TextView text=a.label(FingerprintObservationHistory.summary(audit.observationHistory),14,Ui.INK);text.setLineSpacing(a.dp(4),1);text.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(text);
    AppAppearance.dialog(a).setTitle("最近的网页观测").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("清除观测历史",(d,w)->AppAppearance.dialog(a).setTitle("清除最近观测历史？").setMessage("最近检查结果与固定深检参照会保留。").setNegativeButton("取消",null).setPositiveButton("清除",(confirm,which)->{if(a.destroyed||a.session!=edited||edited.deleted)return;String issue=audit.clearObservationHistory();if(!issue.isEmpty())AppAppearance.dialog(a).setTitle("历史记录").setMessage(issue).setPositiveButton("关闭",null).show();}).show()).show();
  }
}
