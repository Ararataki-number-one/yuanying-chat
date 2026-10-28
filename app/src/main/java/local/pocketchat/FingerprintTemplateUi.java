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
    ChatSession edited=a.session;
    edited.environmentIo.execute(()->{EnvironmentSpec state=null;try{state=new EnvironmentSpecRepository(edited.context).load();}catch(Exception ignored){}EnvironmentSpec loaded=state;edited.handler.post(()->{if(!a.isDestroyed()&&!a.isFinishing()&&!edited.deleted&&a.session==edited)showLoaded(a,apply,loaded);});});
  }
  private static void showLoaded(MainActivity a,Apply apply,EnvironmentSpec state){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(a,"环境模板");
    LinearLayout box=dialog.body;box.setPadding(a.dp(2),a.dp(8),a.dp(2),a.dp(12));
    TextView status=a.label(summary(a.session,state),14,Ui.INK);status.setLineSpacing(a.dp(4),1);box.addView(status);
    TextView scope=a.label("仅调整 Firefox 网页显示、语言和现有隐私保护，不提供完整桌面指纹。",13,Ui.MUTED);scope.setPadding(0,a.dp(8),0,a.dp(10));box.addView(scope);
    box.addView(a.label("选择模板",13,Ui.MUTED));
    Spinner choices=new Spinner(a);
    BrowserIdentitySpec current;try{current=BrowserIdentitySpec.from(state.desired().browser());}catch(Exception unavailable){current=BrowserIdentitySpec.legacy(a.session.privacy.desktop,a.session.privacy.level());}final ChatSession edited=a.session;
    String[] ids={BrowserIdentitySpec.MOBILE,BrowserIdentitySpec.DESKTOP,BrowserIdentitySpec.COMPATIBLE,BrowserIdentitySpec.COMPATIBLE_DESKTOP,BrowserIdentitySpec.RFP,BrowserIdentitySpec.RFP_DESKTOP};
    String[] labels=new String[ids.length];for(int i=0;i<ids.length;i++)labels[i]=templateName(BrowserIdentitySpec.preset(ids[i]).json());
    choices.setAdapter(DesignUi.spinnerAdapter(a,labels));for(int i=0;i<ids.length;i++)if(ids[i].equals(current.templateId))choices.setSelection(i);box.addView(choices);
    box.addView(a.label("网页语言",13,Ui.MUTED));
    Spinner language=new Spinner(a);language.setAdapter(DesignUi.spinnerAdapter(a,new String[]{"保持当前语言配置","跟随系统语言","中文 zh-CN","English en-US","日本語 ja-JP"}));box.addView(language);
    TextView note=a.label("电脑版中，Worker 脚本下载与其发起的 HTTP 请求不保证采用相同 UA，请分别查看服务端观测。强化模板为实验模式，网页兼容性尚待真机验证。",13,Ui.MUTED);note.setPadding(0,a.dp(6),0,0);box.addView(note);
    DesignUi.action(box,"模板说明与状态详情",false,()->showDetails(a,edited));
    DesignUi.action(box,"当前环境身份与配置版本",false,()->{if(!a.isDestroyed()&&!a.isFinishing()&&!edited.deleted&&a.session==edited)EnvironmentIdentityUi.show(a,edited);});
    TextView result=a.label("",13,Ui.MUTED);box.addView(result);
    DesignUi.action(box,"查看环境自检",false,()->{dialog.dismiss();EnvironmentAuditUi.show(a);});
    dialog.buttons("关闭",dialog::dismiss,"保存模板",()->{
      String template=ids[choices.getSelectedItemPosition()];int selectedIndex=language.getSelectedItemPosition();
      String[] locales={"","","zh-CN","en-US","ja-JP"};String selected=locales[selectedIndex];
      dialog.primary().setEnabled(false);result.setText("正在读取当前配置并保存模板…");
      // The dialog stays open after saving. "Keep current" must read the current
      // desired language, including previous saves, rather than its opening value.
      edited.environmentIo.execute(()->{
        BrowserIdentitySpec requested=null;String failure="";
        try{
          List<String> selectedLocales=selectedIndex==0?BrowserIdentitySpec.from(new EnvironmentSpecRepository(edited.context).load().desired().browser()).locales:selected.isEmpty()?Collections.emptyList():Collections.singletonList(selected);
          requested=BrowserIdentitySpec.preset(template).withLocales(selectedLocales);failure=requested.validate();
        }catch(Exception unavailable){failure="当前语言配置无法读取，模板未保存；原配置已保留";}
        BrowserIdentitySpec specification=requested;String error=failure;
        edited.handler.post(()->{
          if(a.isDestroyed()||a.isFinishing()||a.session!=edited||!dialog.isShowing())return;
          if(!error.isEmpty()){dialog.primary().setEnabled(true);result.setText(error);return;}
          apply.apply(specification,issue->{
            if(a.isDestroyed()||a.session!=edited||!dialog.isShowing())return;
            dialog.primary().setEnabled(true);result.setText(issue==null||issue.isEmpty()?"配置已保存；运行状态与网页观测可分别查看。":issue);
            edited.environmentIo.execute(()->{EnvironmentSpec updated=null;try{updated=new EnvironmentSpecRepository(edited.context).load();}catch(Exception ignored){}EnvironmentSpec latest=updated;edited.handler.post(()->{if(!a.isDestroyed()&&a.session==edited&&dialog.isShowing())status.setText(summary(edited,latest));});});
          });
        });
      });
    });
    dialog.show();
  }
  static String summary(ChatSession session,EnvironmentSpec spec){
    String desired=spec==null?"配置暂未读取":templateName(spec.desired().browser())+" · 已保存";
    GeckoSettings metadata=session.web.getSettings();
    String using=metadata.policyAcknowledged&&metadata.acceptedBrowserIdentity.length()>0
        ?templateName(metadata.acceptedBrowserIdentity)+" · 浏览器设置已接受":"尚待浏览器确认";
    return "期望模板："+desired+"\n正在使用："+using+"\n原生保护："+session.web.protectionSummary()+"\n最近自检："+auditSummary(session,spec);
  }
  private static String templateName(JSONObject browser){
    try{
      BrowserIdentitySpec value=BrowserIdentitySpec.from(browser);if(!value.validate().isEmpty())return "模板信息不可用";
      String display=value.desktop()?"电脑版":"手机版";
      return ("native-rfp".equals(value.privacy)?"强化":"compatibility".equals(value.privacy)?"兼容":"标准")+display+("native-rfp".equals(value.privacy)?"（实验）":"");
    }catch(Exception unavailable){return "模板信息不可用";}
  }
  private static String auditSummary(ChatSession session,EnvironmentSpec spec){
    if(session.audit.running)return "正在检查…";
    JSONObject report=session.audit.report;
    if(spec!=null&&spec.observedRevision>0){JSONObject saved=spec.observations();if(saved.optLong("at")>report.optLong("at"))report=saved;}
    if(report.length()==0)return "尚未检查";
    if(!report.optBoolean("fresh")||!session.audit.observationCurrent(report)||!report.optString("policy").equals(session.audit.policyStamp())
        ||report.optBoolean("network")&&!report.optString("route").equals(session.audit.routeStamp()))return "历史结果，请重新检查";
    if(spec==null||spec.appliedRevision<=0||report.optLong("identityAppliedRevision")!=spec.appliedRevision)return "已采集，尚未关联当前模板";
    JSONArray rows=report.optJSONArray("rows");if(rows==null||rows.length()==0)return "结果尚不完整，请查看自检";
    int issues=0,uncovered=0,available=0,restricted=0,failed=0;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null){uncovered++;continue;}String status=row.optString("state");if(AuditReport.ISSUE.equals(status))issues++;else if(AuditReport.AVAILABLE.equals(status))available++;else if(AuditReport.RESTRICTED.equals(status))restricted++;else if(AuditReport.FAILED.equals(status))failed++;else if(!AuditReport.VERIFIED.equals(status))uncovered++;}
    return "已采集 · "+issues+" 项差异 · "+uncovered+" 项未覆盖"+(available+restricted+failed>0?"\n按需 API 操作："+available+" 可用 · "+restricted+" 受限 · "+failed+" 失败":"");
  }
  private static void showDetails(MainActivity a,ChatSession edited){
    edited.environmentIo.execute(()->{EnvironmentSpec loaded=null;try{loaded=new EnvironmentSpecRepository(edited.context).load();}catch(Exception ignored){}EnvironmentSpec latest=loaded;
      edited.handler.post(()->{if(a.isDestroyed()||a.isFinishing()||edited.deleted||a.session!=edited)return;
        TextView text=a.label(details(edited,latest),14,Ui.INK);text.setLineSpacing(a.dp(4),1);text.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));ScrollView scroll=new ScrollView(a);scroll.addView(text);
        AppAppearance.dialog(a).setTitle("模板说明与状态详情").setView(scroll).setPositiveButton("关闭",null).show();
      });
    });
  }
  private static String details(ChatSession session,EnvironmentSpec spec){
    StringBuilder out=new StringBuilder("当前内核：").append(GeckoWebView.VERSION).append("\n").append(GeckoPolicyAdapter.summary());
    out.append("\n").append(NativeCapabilityManifest.officialGecko().unsupportedSummary());
    if(spec!=null)out.append("\n\n期望环境配置版本：").append(spec.desiredRevision).append("\n线路与 SDK 请求确认版本：").append(spec.appliedRevision).append("\n实际观测对应版本：").append(spec.observedRevision);
    else out.append("\n环境配置暂未读取");
    GeckoSettings metadata=session.web.getSettings();out.append("\n原生保护：").append(session.web.protectionSummary());out.append("\n当前 SDK 请求：").append(metadata.policyAcknowledged?"请求接受与回读一致":"尚待接受或回读");
    if(!metadata.policyError.isEmpty())out.append("（").append(metadata.policyError).append("）");
    out.append("\n语言请求：").append(Arrays.toString(metadata.requestedLocales)).append("\n语言规范化预测：").append(Arrays.toString(metadata.expectedSdkLocales));
    out.append("\n\n浏览器设置已接受，只表示 SDK 请求接受或公开设置回读，不代表网页已采用或全部指纹通过。常规自检的页面与 Worker JS 信息一致，不能验证联网 UA 一致；真实请求对照需主动打开你配置的 HTTPS 检测页，其来源与 ChatGPT 官网分开记录。图形、音频和字体操作按需采集，不把输出变化当作泄漏或保护失败。");
    out.append("\n\n未覆盖：任意跨源网站、Shared Worker、Service Worker、完整网络协议与 DNS 路径；已配置且逐次授权的受控跨源 iframe 另按报告记录。独立时区和 Canvas / WebGL / 音频 / 字体 / 硬件自定义伪装未开放。强化模板为实验模式，具体 API 保护、真实账号登录和网页兼容性仍需验证。");return out.toString();
  }
}
