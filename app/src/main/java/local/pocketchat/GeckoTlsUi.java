package local.pocketchat;

import android.widget.*;
import java.util.function.Consumer;
import org.json.*;

/** Desired-only TLS editor. Saving never changes a live runtime or its tasks. */
final class GeckoTlsUi {
  static void show(MainActivity activity){
    ChatSession session=activity.session;
    session.environmentIo.execute(()->{
      GeckoTlsStore.State state=null;try{state=GeckoTlsStore.load(session.context);}catch(Exception unavailable){}
      GeckoTlsStore.State loaded=state;session.handler.post(()->{
        if(!current(activity,session))return;
        if(!identity(session,loaded)){DesignUi.message(activity,"Gecko TLS 协议版本","配置无法读取或环境已变化；原文件和当前引擎保留，没有应用新设置。");return;}
        session.tls.desiredSaved(loaded);loaded(activity,session,loaded);
      });
    });
  }
  private static boolean current(MainActivity activity,ChatSession session){return !activity.isDestroyed()&&!activity.isFinishing()&&activity.session==session&&!session.deleted;}
  private static boolean identity(ChatSession session,GeckoTlsStore.State state){return state!=null&&state.identity.slot==Profiles.slot(session.context)&&state.identity.generation==session.environmentGeneration&&state.identity.environmentId.equals(session.environmentId);}
  private static void loaded(MainActivity activity,ChatSession session,GeckoTlsStore.State initial){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"Gecko TLS 协议版本");LinearLayout body=dialog.body;
    DesignUi.note(body,"设置仅约束当前环境整个 Gecko 运行时的网页连接。应用独立下载器、连接检查、代理入口自身的 Java 或其他 TLS 栈不在此范围内。内核默认沿用实际内核策略，不在这里固定协议范围；仅 TLS 1.3 会拒绝只支持旧协议的站点。");
    Spinner choices=new Spinner(activity);choices.setContentDescription("下次冷启动的 Gecko TLS 协议版本");choices.setMinimumHeight(DesignUi.dp(activity,48));
    choices.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"内核默认","仅 TLS 1.3"}));choices.setSelection(initial.spec.isDefault()?0:1);body.addView(choices);
    DesignUi.note(body,"保存后仅在当前环境下一次真正冷启动 Gecko 引擎时应用。关闭页面、返回列表或重新打开界面不等于冷启动。本次不会重载网页、结束任务或自动重启。");
    DesignUi.note(body,"原生偏好回读与真实站点的 TLS 握手是两项独立证据；本设置页不验证网络握手，不代表完整 TLS 指纹隔离，也不修改强化保护或 HTTP/2、HTTP/3。");
    DesignUi.note(body,"Chromium / System WebView 暂无独立 TLS 协议版本设置接口，此处不会修改它。若旧站点无法连接，可保存回“内核默认”，等待下一次真正冷启动。");
    TextView status=DesignUi.text(activity,"",13,DesignUi.MUTED);body.addView(status);TextView result=DesignUi.text(activity,"",13,DesignUi.MUTED);body.addView(result);
    GeckoTlsStore.State[] expected={initial};
    Runnable update=()->{if(current(activity,session)&&dialog.isShowing()){GeckoTlsStore.State latest=session.tls.snapshot();status.setText(summary(identity(session,latest)?latest.spec:expected[0].spec,session.tls.status()));}};
    dialog.setOnDismissListener(ignored->session.tls.removeListener(update));
    dialog.buttons("关闭",dialog::dismiss,"保存供下次冷启动",()->{
      final GeckoTlsSpec desired;try{desired=selection(choices.getSelectedItemPosition());}catch(IllegalArgumentException invalid){result.setText(invalid.getMessage());return;}
      dialog.primary().setEnabled(false);
      confirm(activity,session,expected[0],desired,message->{
        if(!current(activity,session)||!dialog.isShowing())return;dialog.primary().setEnabled(true);result.setText(message);
        GeckoTlsStore.State latest=session.tls.snapshot();if(identity(session,latest)&&latest.spec.equals(desired)&&latest.revision>=expected[0].revision)expected[0]=latest;update.run();
      });
    });dialog.show();session.tls.addListener(update);update.run();
  }
  static GeckoTlsSpec selection(int position){if(position<0||position>1)throw new IllegalArgumentException("请选择内核默认或仅 TLS 1.3");return GeckoTlsSpec.of(new String[]{"default","tls13"}[position]);}
  private static Integer version(JSONObject value,String key){Object raw=value.opt(key);if(!(raw instanceof Integer||raw instanceof Long))return null;long number=((Number)raw).longValue();return number>=3&&number<=4?(int)number:null;}
  private static String version(int value){return new String[]{"","TLS 1.0","TLS 1.1","TLS 1.2","TLS 1.3"}[value];}
  private static String range(int min,int max){return min==max?version(min):version(min)+" 至 "+version(max);}
  static String summary(GeckoTlsSpec desired,JSONObject supplied){
    JSONObject status=supplied==null?new JSONObject():supplied;
    Integer min=version(status,"configuredMin"),max=version(status,"configuredMax"),defaultMin=version(status,"defaultMin"),defaultMax=version(status,"defaultMax");
    boolean typed=min!=null&&max!=null&&defaultMin!=null&&defaultMax!=null&&min<=max&&defaultMin<=defaultMax&&status.opt("hasUserMin") instanceof Boolean&&status.opt("hasUserMax") instanceof Boolean;
    GeckoTlsSpec bootSpec=null;try{if(status.opt("activeBootMode") instanceof String)bootSpec=GeckoTlsSpec.of((String)status.opt("activeBootMode"));}catch(IllegalArgumentException unknown){}
    boolean noUser=Boolean.FALSE.equals(status.opt("hasUserMin"))&&Boolean.FALSE.equals(status.opt("hasUserMax"));
    boolean readback=Boolean.TRUE.equals(status.opt("nativeSettingReadback"))&&typed&&noUser&&min.equals(defaultMin)&&max.equals(defaultMax)&&bootSpec!=null&&(!bootSpec.requiresTls13()||min==4&&max==4);
    long saved=status.optLong("desiredRevision"),boot=status.optLong("activeBootRevision");
    String bootMode=bootSpec==null?"":"\n当前启动请求："+bootSpec.label();
    String active=readback?"当前引擎原生 TLS 偏好已回读\n当前有效范围："+range(min,max)+"\n当前原生默认范围："+range(defaultMin,defaultMax) : "尚未取得当前引擎的原生 TLS 偏好确认";
    if(!noUser&&(Boolean.TRUE.equals(status.opt("hasUserMin"))||Boolean.TRUE.equals(status.opt("hasUserMax"))))active+="\n存在残留手动偏好覆盖，尚未确认内核默认";
    String issue=status.optString("issue");if(issue.length()>400)issue=issue.substring(0,400);if(!issue.isEmpty())active+="\n"+issue;
    return "已保存："+desired.label()+bootMode+"\n"+active+(saved>0&&boot>0&&saved!=boot?"\n有新设置等待当前环境下一次真正冷启动":"")+"\n网络握手：本设置页未验证\n范围：当前环境 Gecko 网页连接共用；应用其他 TLS 栈未覆盖；System WebView 独立设置不受支持";
  }
  static void confirm(MainActivity activity,ChatSession session,GeckoTlsStore.State expected,GeckoTlsSpec desired,Consumer<String> done){
    if(!current(activity,session)||!identity(session,expected)){done.accept("当前环境已变化，TLS 设置未保存");return;}
    ReferenceUi.Modal confirmation=new ReferenceUi.Modal(activity,"只保存下次冷启动的设置？");
    confirmation.note("将“"+desired.label()+"”保存到当前环境整个 Gecko 运行时的网页连接；应用独立下载器、连接检查、代理入口自身的 Java 或其他 TLS 栈不受此设置覆盖。其他环境和 Chromium / System WebView 不会修改。");
    confirmation.note("本次不会改变当前引擎、网页、回复、上传、下载或草稿，不会自动重启。关闭页面或返回列表不会使新值生效；当前环境下一次真正冷启动引擎后仍需原生回读。");
    confirmation.note("仅 TLS 1.3 可能使旧站点无法连接；内核默认恢复实际内核策略，不承诺固定的版本范围。原生回读不等于真实站点握手验证或完整 TLS 指纹隔离。");
    boolean[] accepted={false};confirmation.setOnDismissListener(ignored->{if(!accepted[0])done.accept("已取消，原设置和当前任务保留");});
    confirmation.buttons("取消",confirmation::dismiss,"仅保存设置",()->{
      accepted[0]=true;confirmation.dismiss();saveDesired(activity,session,expected,desired,done);
    });confirmation.show();
  }
  static void saveDesired(MainActivity activity,ChatSession session,GeckoTlsStore.State expected,GeckoTlsSpec desired,Consumer<String> done){
    if(!current(activity,session)||!identity(session,expected)){done.accept("当前环境已变化，TLS 设置未保存");return;}
    session.environmentIo.execute(()->{
      GeckoTlsStore.State state=null;try{state=GeckoTlsStore.save(session.context,expected.identity,expected.revision,desired);}catch(Exception unavailable){}
      GeckoTlsStore.State saved=state;session.handler.post(()->{
        if(activity.session==session&&!session.deleted&&identity(session,saved))session.tls.desiredSaved(saved);
        if(!current(activity,session)){done.accept("当前界面已变化；本次没有改变正在运行的引擎");return;}
        if(!identity(session,saved)){done.accept("设置未保存或版本已变化，原配置和当前任务保留；请重新打开设置");return;}
        done.accept("已保存为“"+saved.spec.label()+"”；当前任务保持原样，等待当前环境下一次真正冷启动 Gecko 引擎。");
      });
    });
  }
}
