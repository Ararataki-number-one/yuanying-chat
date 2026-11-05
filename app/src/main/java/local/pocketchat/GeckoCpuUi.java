package local.pocketchat;

import android.widget.*;
import java.util.function.Consumer;
import org.json.*;

/** Desired-only editor. Saving never changes the active runtime or its tasks. */
final class GeckoCpuUi {
  static void show(MainActivity activity){
    ChatSession session=activity.session;
    session.environmentIo.execute(()->{
      GeckoCpuStore.State state=null;try{state=GeckoCpuStore.load(session.context);}catch(Exception unavailable){}
      GeckoCpuStore.State loaded=state;session.handler.post(()->{
        if(!current(activity,session))return;
        if(!identity(session,loaded)){DesignUi.message(activity,"Gecko CPU 可见数上限","配置无法读取或环境已变化；原文件和当前引擎保留，没有应用新设置。");return;}
        session.cpu.desiredSaved(loaded);loaded(activity,session,loaded);
      });
    });
  }
  private static boolean current(MainActivity activity,ChatSession session){return !activity.isDestroyed()&&!activity.isFinishing()&&activity.session==session&&!session.deleted;}
  private static boolean identity(ChatSession session,GeckoCpuStore.State state){return state!=null&&state.identity.slot==Profiles.slot(session.context)&&state.identity.generation==session.environmentGeneration&&state.identity.environmentId.equals(session.environmentId);}
  private static void loaded(MainActivity activity,ChatSession session,GeckoCpuStore.State initial){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"Gecko CPU 可见数上限");LinearLayout body=dialog.body;
    DesignUi.note(body,"这是当前环境整个 Gecko 运行时共用的网页可见 CPU 数上限，不是单个网页的独立覆盖，也不限制手机实际 CPU。其他环境和 Chromium 的设置不会在这里修改。");
    Spinner choices=new Spinner(activity);choices.setContentDescription("下次冷启动的 Gecko CPU 可见数上限");choices.setMinimumHeight(DesignUi.dp(activity,48));
    choices.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"内核默认","最多 1","最多 2"}));choices.setSelection(initial.spec.isAutomatic()?0:initial.spec.cap==1?1:2);body.addView(choices);
    DesignUi.note(body,"保存后仅在当前环境下一次真正冷启动 Gecko 引擎时应用。关闭页面、返回列表或重新打开界面不等于冷启动。本次不会重载网页、结束任务或自动重启。");
    DesignUi.note(body,"强化保护保持优先，可能继续使用内核标准值。运行中切换保护模板时，已有 ServiceWorker（网站后台任务）可能保留启动时的 CPU 值；要让这些后台任务也统一采用新保护，需要当前环境真正冷启动。保存设置或切换模板不会自动结束任务。");
    DesignUi.note(body,"原生偏好回读与页面、Worker 的实际值分别记录，不代表完整指纹隔离；较小上限也可能减少网站并行任务。");
    TextView status=DesignUi.text(activity,"",13,DesignUi.MUTED);body.addView(status);TextView result=DesignUi.text(activity,"",13,DesignUi.MUTED);body.addView(result);
    GeckoCpuStore.State[] expected={initial};
    Runnable update=()->{if(current(activity,session)&&dialog.isShowing()){GeckoCpuStore.State latest=session.cpu.snapshot();status.setText(summary(identity(session,latest)?latest.spec:expected[0].spec,session.cpu.status()));}};
    dialog.setOnDismissListener(ignored->session.cpu.removeListener(update));
    dialog.buttons("关闭",dialog::dismiss,"保存供下次冷启动",()->{
      final GeckoCpuSpec desired;try{desired=selection(choices.getSelectedItemPosition());}catch(IllegalArgumentException invalid){result.setText(invalid.getMessage());return;}
      dialog.primary().setEnabled(false);
      confirm(activity,session,expected[0],desired,message->{
        if(!current(activity,session)||!dialog.isShowing())return;dialog.primary().setEnabled(true);result.setText(message);
        GeckoCpuStore.State latest=session.cpu.snapshot();if(identity(session,latest)&&latest.spec.equals(desired)&&latest.revision>=expected[0].revision)expected[0]=latest;update.run();
      });
    });dialog.show();session.cpu.addListener(update);update.run();
  }
  static GeckoCpuSpec selection(int position){if(position<0||position>2)throw new IllegalArgumentException("请选择内核默认、最多 1 或最多 2");return GeckoCpuSpec.of(new String[]{"automatic","1","2"}[position]);}
  static String summary(GeckoCpuSpec desired,JSONObject status){
    boolean readback=Boolean.TRUE.equals(status.opt("nativeSettingReadback")),rfp=Boolean.TRUE.equals(status.opt("rfpPriority"));
    long saved=status.optLong("desiredRevision"),boot=status.optLong("activeBootRevision");
    String bootMode="";try{if(status.opt("activeBootMode") instanceof String)bootMode="\n当前启动请求："+GeckoCpuSpec.of((String)status.opt("activeBootMode")).label();}catch(IllegalArgumentException unknown){}
    String active=rfp?"强化保护优先；不以保存值承诺网页可见上限":readback?"当前引擎原生偏好已回读；页面和 Worker 尚需分别观测":"尚未取得当前引擎的原生偏好确认";
    return "已保存："+desired.label()+bootMode+"\n当前运行时："+active+(saved>0&&boot>0&&saved!=boot?"\n有新设置等待当前环境下一次真正冷启动":"")+"\n范围：整个 Gecko 运行时共用，不是单个网页的独立值";
  }
  static void confirm(MainActivity activity,ChatSession session,GeckoCpuStore.State expected,GeckoCpuSpec desired,Consumer<String> done){
    if(!current(activity,session)||!identity(session,expected)){done.accept("当前环境已变化，CPU 设置未保存");return;}
    ReferenceUi.Modal confirmation=new ReferenceUi.Modal(activity,"只保存下次冷启动的设置？");
    confirmation.note("将“"+desired.label()+"”保存到当前环境。它作用于该环境整个 Gecko 运行时，不能为同一运行时的不同网页分别设置。");
    confirmation.note("本次不会改变当前引擎、网页、回复、上传、下载或草稿，不会自动重启。关闭页面或返回列表不会使新值生效；当前环境下一次真正冷启动引擎后仍需原生回读。");
    confirmation.note("强化保护不会减弱，其标准化结果可能优先于此上限。运行中切换模板后，已有 ServiceWorker 可能保留启动时的 CPU 值；统一采用新保护需要当前环境真正冷启动。本次保存和模板切换都不会自动结束任务。设置回读不代表页面、旧 Worker 或 Service Worker 全部验证。");
    boolean[] accepted={false};confirmation.setOnDismissListener(ignored->{if(!accepted[0])done.accept("已取消，原设置和当前任务保留");});
    confirmation.buttons("取消",confirmation::dismiss,"仅保存设置",()->{
      accepted[0]=true;confirmation.dismiss();saveDesired(activity,session,expected,desired,done);
    });confirmation.show();
  }
  static void saveDesired(MainActivity activity,ChatSession session,GeckoCpuStore.State expected,GeckoCpuSpec desired,Consumer<String> done){
    if(!current(activity,session)||!identity(session,expected)){done.accept("当前环境已变化，CPU 设置未保存");return;}
    session.environmentIo.execute(()->{
      GeckoCpuStore.State state=null;try{state=GeckoCpuStore.save(session.context,expected.identity,expected.revision,desired);}catch(Exception unavailable){}
      GeckoCpuStore.State saved=state;session.handler.post(()->{
        if(activity.session==session&&!session.deleted&&identity(session,saved))session.cpu.desiredSaved(saved);
        if(!current(activity,session)){done.accept("当前界面已变化；本次没有改变正在运行的引擎");return;}
        if(!identity(session,saved)){done.accept("设置未保存或版本已变化，原配置和当前任务保留；请重新打开设置");return;}
        done.accept("已保存为“"+saved.spec.label()+"”；当前任务保持原样，等待当前环境下一次真正冷启动 Gecko 引擎。");
      });
    });
  }
}
