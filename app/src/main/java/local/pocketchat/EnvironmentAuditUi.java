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
    Button identityState=button(a,box,"查看当前环境身份与配置版本");
    identityState.setOnClickListener(v->{if(current(a,edited,audit))EnvironmentIdentityUi.show(a,edited);});
    Button retry=button(a,box,"重试强化保护确认"),standard=button(a,box,"主动改用标准模式");
    TextView policyResult=a.label("",13,Ui.MUTED);box.addView(policyResult);
    TextView explanation=a.label("\n本机检查只在点按后采集。图形与音频检查采用有限操作，不播放声音；结果可用或发生变化，不代表原生保护已通过或出现泄漏。",13,Ui.MUTED);box.addView(explanation);
    Button local=button(a,box,"检查浏览器信息（本机）"),deep=button(a,box,"检查图形与音频（本机）");
    TextView info=a.label("",14,Ui.INK);info.setLineSpacing(a.dp(4),1);info.setPadding(0,a.dp(12),0,a.dp(8));box.addView(info);
    // Returning remains accessible even while advanced settings are collapsed.
    Button back=button(a,box,"返回原聊天"),history=button(a,box,"查看最近观测与变化"),fixed=button(a,box,"固定深检参照与比较"),comparison=button(a,box,"标准／强化本地双报告对照");
    Button detailsToggle=button(a,box,"展开结果详情");LinearLayout details=section(a,box);
    TextView rawInfo=a.label("",14,Ui.INK);rawInfo.setLineSpacing(a.dp(4),1);details.addView(rawInfo);
    Button templateCapabilities=button(a,details,"原生保护能力与兼容记录");
    templateCapabilities.setOnClickListener(v->{if(current(a,edited,audit))ProtectionTemplateUi.show(a,edited);});
    Button copyDeep=button(a,details,"复制脱敏深检诊断"),baseline=button(a,details,"确认当前环境，更新基线");
    TextView baselineNote=a.label("确认基线只更新变化参照，不会修复检查发现的问题。最近八次网页观测仅在当前环境本地加密保存。固定深检参照单独保留，需主动保存或清除。 诊断复制仅包含状态、数值与有效哈希，原始文字和地址留在本机查看。",13,Ui.MUTED);details.addView(baselineNote);
    Button advancedToggle=button(a,box,"展开高级网络检测");LinearLayout advanced=section(a,box);
    TextView networkExplanation=a.label("\n网络出口检查会访问 ipify 和 httpbin，服务能看到出口 IP 与必要请求信息。请求不主动携带 Cookie、密码或聊天内容。",13,Ui.MUTED);advanced.addView(networkExplanation);
    CheckBox consent=new CheckBox(a);consent.setText("仅本次允许向 ipify / httpbin 发送检测信息");consent.setChecked(false);advanced.addView(consent);
    Button network=button(a,advanced,"检查实际网络出口");
    TextView identityExplanation=a.label("\n真实请求身份检查会暂时打开你选择的 HTTPS 检测页，对照主文档与 Dedicated Worker 的服务端请求信息；仅在没有草稿、附件和进行中任务时打开。该结果不代表 ChatGPT 官网请求。Shared Worker 与 Service Worker 的请求、缓存和生命周期尚未覆盖；本检查不会注册或清理它们。",13,Ui.MUTED);advanced.addView(identityExplanation);
    Button endpoint=button(a,advanced,"设置请求身份检测服务"),serviceCheck=button(a,advanced,"检查检测服务（不离开聊天）"),frameEndpoint=button(a,advanced,"设置跨源 iframe 检测来源");
    CheckBox identityConsent=new CheckBox(a);identityConsent.setText("仅本次允许向所选服务发送 UA、语言与出口 IP");identityConsent.setChecked(audit.requestIdentityRunning());advanced.addView(identityConsent);
    CheckBox frameConsent=new CheckBox(a);frameConsent.setText("仅本次允许访问第二 HTTPS 来源，检查跨源 iframe 图形");advanced.addView(frameConsent);
    Button identity=button(a,advanced,"打开真实请求检测页"),crossFrame=button(a,advanced,"打开跨源 iframe 图形检测");
    TextView identityResult=a.label("",13,Ui.MUTED);advanced.addView(identityResult);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("环境自检与变更").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("复制脱敏简要结果",(d,w)->{if(current(a,edited,audit))((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("环境自检",audit.safeCopy()));}).create();
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
      crossFrame.setEnabled(!audit.running&&!selected.isEmpty()&&!audit.requestIdentityFrameEndpoint().isEmpty()&&identityConsent.isChecked()&&frameConsent.isChecked()&&!audit.canReturnRequestIdentity());fixed.setEnabled(!audit.running);copyDeep.setEnabled(!audit.running&&audit.hasDeepRecord());comparison.setEnabled(!audit.running);
      info.setText(briefSummary(audit));
      if(details.getVisibility()==android.view.View.VISIBLE)rawInfo.setText(audit.summary());
      if(advanced.getVisibility()==android.view.View.VISIBLE)identityResult.setText(audit.serviceProbeSummary(false)+"\n\n"+audit.requestIdentitySummary(false));
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
    detailsToggle.setOnClickListener(v->{if(!current(a,edited,audit))return;toggle(details,detailsToggle,"展开结果详情","收起结果详情");update.run();});
    advancedToggle.setOnClickListener(v->{if(!current(a,edited,audit))return;toggle(advanced,advancedToggle,"展开高级网络检测","收起高级网络检测");update.run();});
    comparison.setOnClickListener(v->{if(current(a,edited,audit))FingerprintComparisonUi.show(a,audit);});
    history.setOnClickListener(v->{if(current(a,edited,audit))history(a,audit);});fixed.setOnClickListener(v->{if(current(a,edited,audit))fixed(a,audit);});copyDeep.setOnClickListener(v->{if(!current(a,edited,audit))return;((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("脱敏深检诊断",audit.deepRecordCopy()));policyResult.setText("已复制状态、数值与有效哈希；没有复制 UA、地址、网页原文或原始错误。真机兼容仍需分别操作记录。");});baseline.setOnClickListener(v->{if(!current(a,edited,audit))return;audit.acceptBaseline();update.run();NetworkMetricsUi.update(a);});
    dialog.setOnDismissListener(d->{if(protectionTick[0]!=null)edited.handler.removeCallbacks(protectionTick[0]);if(identityTick[0]!=null)edited.handler.removeCallbacks(identityTick[0]);if(!handoff[0])audit.cancel();});dialog.show();update.run();watchProtection.run();
  }
  static LinearLayout section(MainActivity a,LinearLayout parent){LinearLayout value=new LinearLayout(a);value.setOrientation(LinearLayout.VERTICAL);value.setVisibility(android.view.View.GONE);value.setPadding(a.dp(4),0,a.dp(4),a.dp(12));parent.addView(value);return value;}
  static void toggle(LinearLayout section,Button control,String collapsed,String expanded){boolean show=section.getVisibility()!=android.view.View.VISIBLE;section.setVisibility(show?android.view.View.VISIBLE:android.view.View.GONE);control.setText(show?expanded:collapsed);}
  static String briefSummary(EnvironmentAudit audit){JSONObject report=audit.report;boolean valid=report.length()>0&&report.optBoolean("fresh")&&audit.observationCurrent(report)&&report.optString("policy").equals(audit.policyStamp())&&(!report.optBoolean("network")||report.optString("route").equals(audit.routeStamp()));String value=FingerprintAuditSummary.summary(report,valid,audit.running,audit.lastError,audit.storageIssue);return audit.hasChanges()?value+"\n\n环境基线有 "+audit.changes.length()+" 项变化，可展开结果详情查看。":value;}
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
    ChatSession edited=a.session;LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(16));
    String[] contexts={"main","worker","frame","crossOriginFrame"},labels=new String[contexts.length];for(int i=0;i<contexts.length;i++)labels[i]=FingerprintContextBaselines.label(contexts[i]);
    box.addView(a.label("选择执行环境，每类各保留一份参照",13,Ui.MUTED));Spinner selected=new Spinner(a);selected.setAdapter(DesignUi.spinnerAdapter(a,labels));box.addView(selected);
    TextView overview=a.label("",13,Ui.MUTED);overview.setLineSpacing(a.dp(3),1);box.addView(overview);
    TextView text=a.label("",14,Ui.INK);text.setLineSpacing(a.dp(4),1);box.addView(text);Button pin=button(a,box,"固定当前执行环境的深检参照"),clear=button(a,box,"清除所选执行环境参照");
    TextView result=a.label("不同页面、Worker 或 iframe 的输出分别保留，不比较跨执行环境哈希。跨源 iframe 需先在高级网络检测中主动授权并完成检查。",13,Ui.MUTED);box.addView(result);
    TextView eligibility=a.label("",13,Ui.MUTED);box.addView(eligibility);ScrollView scroll=new ScrollView(a);scroll.addView(box);AlertDialog dialog=AppAppearance.dialog(a).setTitle("固定深检参照").setView(scroll).setPositiveButton("关闭",null).create();
    Runnable update=()->{if(!current(a,edited,audit))return;String context=contexts[selected.getSelectedItemPosition()];boolean ready=!audit.running&&audit.deepObservationCurrent(context);overview.setText(audit.pinnedContextOverview());text.setText(audit.pinnedDeepSummary(context));pin.setEnabled(ready);clear.setEnabled(!audit.running&&audit.hasPinnedDeepBaseline(context));selected.setEnabled(!audit.running);eligibility.setText(ready?"本次有效深检可固定；其他执行环境的参照会保留。":"尚无所选执行环境的当前有效深检，或检查正在进行。请先完成对应的主动检查。");};
    selected.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onItemSelected(AdapterView<?> parent,android.view.View view,int position,long id){update.run();}public void onNothingSelected(AdapterView<?> parent){}});
    pin.setOnClickListener(v->{if(!current(a,edited,audit))return;String context=contexts[selected.getSelectedItemPosition()];Runnable capture=()->{if(!current(a,edited,audit))return;String issue=audit.pinDeepObservation(context);result.setText(issue.isEmpty()?"所选执行环境的深检参照已加密保存。":issue);update.run();};if(!audit.hasPinnedDeepBaseline(context))capture.run();else AppAppearance.dialog(a).setTitle("替换所选深检参照？").setMessage("仅替换“"+FingerprintContextBaselines.label(context)+"”的固定参照，其他参照会保留。").setNegativeButton("取消",null).setPositiveButton("替换",(d,w)->capture.run()).show();});
    clear.setOnClickListener(v->{if(!current(a,edited,audit))return;String context=contexts[selected.getSelectedItemPosition()];AppAppearance.dialog(a).setTitle("清除所选深检参照？").setMessage("仅清除“"+FingerprintContextBaselines.label(context)+"”的参照，其他参照和最近八条观测会保留。").setNegativeButton("取消",null).setPositiveButton("清除",(d,w)->{if(!current(a,edited,audit))return;String issue=audit.clearPinnedDeepBaseline(context);result.setText(issue.isEmpty()?"所选参照已清除。":issue);update.run();}).show();});dialog.show();update.run();
  }
  static void history(MainActivity a,EnvironmentAudit audit){
    if(a.destroyed||a.session!=audit.session||audit.session.deleted)return;
    ChatSession edited=a.session;TextView text=a.label(FingerprintObservationHistory.summary(audit.observationHistory),14,Ui.INK);text.setLineSpacing(a.dp(4),1);text.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(text);
    AppAppearance.dialog(a).setTitle("最近的网页观测").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("清除观测历史",(d,w)->AppAppearance.dialog(a).setTitle("清除最近观测历史？").setMessage("最近检查结果与固定深检参照会保留。").setNegativeButton("取消",null).setPositiveButton("清除",(confirm,which)->{if(a.destroyed||a.session!=edited||edited.deleted)return;String issue=audit.clearObservationHistory();if(!issue.isEmpty())AppAppearance.dialog(a).setTitle("历史记录").setMessage(issue).setPositiveButton("关闭",null).show();}).show()).show();
  }
}
