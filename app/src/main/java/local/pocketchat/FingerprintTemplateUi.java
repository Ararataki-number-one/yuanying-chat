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
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    TextView status=a.label(summary(a.session,state),14,Ui.INK);box.addView(status);
    Spinner choices=new Spinner(a);
    BrowserIdentitySpec current;try{current=BrowserIdentitySpec.from(state.desired().browser());}catch(Exception unavailable){current=BrowserIdentitySpec.legacy(a.session.privacy.desktop,a.session.privacy.level());}final ChatSession edited=a.session;
    String[] ids={BrowserIdentitySpec.MOBILE,BrowserIdentitySpec.DESKTOP,BrowserIdentitySpec.COMPATIBLE,BrowserIdentitySpec.COMPATIBLE_DESKTOP,BrowserIdentitySpec.RFP,BrowserIdentitySpec.RFP_DESKTOP};
    String[] labels=new String[ids.length];for(int i=0;i<ids.length;i++)labels[i]=BrowserIdentitySpec.preset(ids[i]).label();
    choices.setAdapter(DesignUi.spinnerAdapter(a,labels));for(int i=0;i<ids.length;i++)if(ids[i].equals(current.templateId))choices.setSelection(i);box.addView(choices);
    Spinner language=new Spinner(a);language.setAdapter(DesignUi.spinnerAdapter(a,new String[]{"保持当前语言配置","跟随系统语言","中文 zh-CN","English en-US","日本語 ja-JP"}));box.addView(language);
    TextView note=a.label("模板只使用当前真实 Firefox 能力。语言已提交给 SDK；回读只表示请求。网页、Worker 和请求头是否采用该语言，以实际自检为准。原生强化模式可能改变时区和图形表现，尚待接受或回读 ChatGPT 真机兼容性验证。独立时区及硬件伪装暂未开放。",13,Ui.MUTED);box.addView(note);
    TextView result=a.label("",13,Ui.MUTED);box.addView(result);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("环境模板").setView(scroll).setPositiveButton("保存模板",null).setNeutralButton("查看环境自检",(d,w)->EnvironmentAuditUi.show(a)).setNegativeButton("关闭",null).create();
    dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view->{
      String template=ids[choices.getSelectedItemPosition()];int selectedIndex=language.getSelectedItemPosition();
      String[] locales={"","","zh-CN","en-US","ja-JP"};String selected=locales[selectedIndex];
      dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);result.setText("正在读取当前配置并保存模板…");
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
          if(!error.isEmpty()){dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);result.setText(error);return;}
          apply.apply(specification,issue->{
            if(a.isDestroyed()||a.session!=edited||!dialog.isShowing())return;
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);result.setText(issue==null||issue.isEmpty()?"配置已保存；运行状态与网页观测可分别查看。":issue);
            edited.environmentIo.execute(()->{EnvironmentSpec updated=null;try{updated=new EnvironmentSpecRepository(edited.context).load();}catch(Exception ignored){}EnvironmentSpec latest=updated;edited.handler.post(()->{if(!a.isDestroyed()&&a.session==edited&&dialog.isShowing())status.setText(summary(edited,latest));});});
          });
        });
      });
    });
  }
  static String summary(ChatSession session,EnvironmentSpec spec){
    StringBuilder out=new StringBuilder("当前内核：").append(GeckoWebView.VERSION).append("\n").append(GeckoPolicyAdapter.summary());
    if(spec!=null)out.append("\n\n期望环境配置版本：").append(spec.desiredRevision).append("\n线路与 SDK 请求确认版本：").append(spec.appliedRevision).append("\n实际观测对应版本：").append(spec.observedRevision);
    else out.append("\n环境配置暂未读取");
    GeckoSettings metadata=session.web.getSettings();out.append("\n当前 SDK 请求：").append(metadata.policyAcknowledged?"请求接受与回读一致":"尚待接受或回读");
    if(!metadata.policyError.isEmpty())out.append("（").append(metadata.policyError).append("）");
    out.append("\n\nSDK 确认只表示请求接受或公开设置回读。语言内容进程没有独立完成回执；网页字段和请求头以实际观测为准。");return out.toString();
  }
}
