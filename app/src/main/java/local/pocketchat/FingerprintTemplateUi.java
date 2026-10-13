package local.pocketchat;

import android.app.*;
import android.widget.*;
import org.json.*;
import java.util.function.Consumer;
import java.util.*;

/** Quiet template editor. Applying uses the existing draft-preserving session flow. */
final class FingerprintTemplateUi {
  interface Apply {void apply(BrowserIdentitySpec specification,Consumer<String> completed);}
  static void show(MainActivity activity){show(activity,(spec,done)->activity.session.applyIdentityTemplate(activity,spec,done));}
  static void show(MainActivity a,Apply apply){
    a.session.webStore.worker.execute(()->{EnvironmentSpec state=null;try{state=new EnvironmentSpecRepository(a.session.context).load();}catch(Exception ignored){}EnvironmentSpec loaded=state;a.session.handler.post(()->{if(!a.isDestroyed()&&!a.isFinishing())showLoaded(a,apply,loaded);});});
  }
  private static void showLoaded(MainActivity a,Apply apply,EnvironmentSpec state){
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    TextView status=a.label(summary(a.session,state),14,Ui.INK);box.addView(status);
    Spinner choices=new Spinner(a);
    BrowserIdentitySpec current;try{current=BrowserIdentitySpec.from(state.desired().browser());}catch(Exception unavailable){current=BrowserIdentitySpec.legacy(a.session.privacy.desktop,a.session.privacy.level());}final BrowserIdentitySpec original=current;
    String[] ids={BrowserIdentitySpec.MOBILE,BrowserIdentitySpec.DESKTOP,BrowserIdentitySpec.COMPATIBLE,BrowserIdentitySpec.COMPATIBLE_DESKTOP,BrowserIdentitySpec.RFP,BrowserIdentitySpec.RFP_DESKTOP};
    String[] labels=new String[ids.length];for(int i=0;i<ids.length;i++)labels[i]=BrowserIdentitySpec.preset(ids[i]).label();
    choices.setAdapter(DesignUi.spinnerAdapter(a,labels));for(int i=0;i<ids.length;i++)if(ids[i].equals(current.templateId))choices.setSelection(i);box.addView(choices);
    Spinner language=new Spinner(a);language.setAdapter(DesignUi.spinnerAdapter(a,new String[]{"保持当前语言配置","跟随系统语言","中文 zh-CN","English en-US","日本語 ja-JP"}));box.addView(language);
    TextView note=a.label("模板只使用当前真实 Firefox 能力。原生语言设置有当前 SDK 签名及回读检查，具体网页、Worker 和请求头仍需自检。原生强化模式可能改变时区和图形表现，尚未完成 ChatGPT 真机兼容性验证。独立时区及硬件伪装暂未开放。",13,Ui.MUTED);box.addView(note);
    TextView result=a.label("",13,Ui.MUTED);box.addView(result);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("环境模板").setView(scroll).setPositiveButton("保存模板",null).setNeutralButton("查看环境自检",(d,w)->EnvironmentAuditUi.show(a)).setNegativeButton("关闭",null).create();
    dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view->{
      String[] locales={"","","zh-CN","en-US","ja-JP"};int selectedIndex=language.getSelectedItemPosition();String selected=locales[selectedIndex];
      BrowserIdentitySpec spec=BrowserIdentitySpec.preset(ids[choices.getSelectedItemPosition()]).withLocales(selectedIndex==0?original.locales:selected.isEmpty()?Collections.emptyList():Collections.singletonList(selected));String error=spec.validate();
      if(!error.isEmpty()){result.setText(error);return;}
      dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);result.setText("正在保留网页状态并保存配置…");
      apply.apply(spec,issue->{if(a.isDestroyed()||!dialog.isShowing())return;dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);result.setText(issue==null||issue.isEmpty()?"配置已保存；运行状态与网页观测可分别查看。":issue);a.session.webStore.worker.execute(()->{EnvironmentSpec updated=null;try{updated=new EnvironmentSpecRepository(a.session.context).load();}catch(Exception ignored){}EnvironmentSpec latest=updated;a.session.handler.post(()->{if(!a.isDestroyed()&&dialog.isShowing())status.setText(summary(a.session,latest));});});});
    });
  }
  static String summary(ChatSession session,EnvironmentSpec spec){
    StringBuilder out=new StringBuilder("当前内核：").append(GeckoWebView.VERSION).append("\n").append(GeckoPolicyAdapter.summary());
    if(spec!=null)out.append("\n\n期望环境配置版本：").append(spec.desiredRevision).append("\n完整环境确认版本：").append(spec.appliedRevision).append("\n最近观测版本：").append(spec.observedRevision);
    else out.append("\n环境配置暂未读取");
    GeckoSettings metadata=session.web.getSettings();out.append("\n当前内核确认：").append(metadata.policyAcknowledged?"已确认当前设置":"尚未完成");
    if(!metadata.policyError.isEmpty())out.append("（").append(metadata.policyError).append("）");
    out.append("\n\n").append(NativeCapabilityManifest.officialGecko().unsupportedSummary());out.append("\n\n内核确认只代表设置接受；具体网页字段请运行自检。");return out.toString();
  }
}
