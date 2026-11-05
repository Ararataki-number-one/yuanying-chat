package local.pocketchat;

import android.text.InputFilter;
import android.text.InputType;
import android.widget.*;
import java.util.function.*;
import org.json.*;

/** Environment-scoped editor; never changes Android's timezone or page Date. */
final class GeckoTimeZoneUi {
  static void show(MainActivity activity){
    ChatSession session=activity.session;
    session.timeZone.refresh(state->{if(activity.isDestroyed()||activity.isFinishing()||activity.session!=session||session.deleted)return;
      if(state==null){DesignUi.message(activity,"独立时区","时区配置无法读取，原文件保留；当前没有应用新的时区设置。");return;}loaded(activity,session,state);
    });
  }
  private static void loaded(MainActivity a,ChatSession s,GeckoTimeZoneStore.State initial){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(a,"此环境的独立时区");LinearLayout box=dialog.body;
    TextView status=DesignUi.text(a,"",14,DesignUi.TEXT);box.addView(status);
    DesignUi.note(box,"仅保存到当前环境的 Gecko。不会修改手机时区，也不会用网页脚本伪造 Date。保存配置与当前会话原生回读分别显示。");
    Spinner mode=new Spinner(a);mode.setContentDescription("此环境时区模式");mode.setMinimumHeight(DesignUi.dp(a,48));mode.setAdapter(DesignUi.spinnerAdapter(a,new String[]{"跟随系统时区","UTC","指定 IANA 时区"}));mode.setSelection(initial.spec.followsSystem()?0:initial.spec.zoneId.equals("UTC")?1:2);box.addView(mode);
    EditText zone=DesignUi.input(box,"IANA 时区名称",initial.spec.followsSystem()||initial.spec.zoneId.equals("UTC")?"":initial.spec.zoneId,"例如 Asia/Shanghai、America/New_York");
    zone.setSingleLine(true);zone.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);zone.setFilters(new InputFilter[]{new InputFilter.LengthFilter(80)});
    DesignUi.note(box,"IANA 地区时区保留真实夏令时规则，不能用固定小时偏移代替。强化模板有自己的时区策略；选择独立时区不会自动减弱强化保护。");
    DesignUi.note(box,"原生上下文设置回读不代表当前页面或所有 Worker 已采用该时区。自定义时区时暂不打开新弹窗；应用设置会关闭已有弹窗并重新加载网页。");
    DesignUi.note(box,"Service Worker 仍可读取系统时区，不能提供完整时区隔离。当前环境的页面与 Worker 实际效果仍需分别验证。");
    TextView result=DesignUi.text(a,"",13,DesignUi.MUTED);box.addView(result);GeckoTimeZoneStore.State[] expected={initial};
    Runnable update=()->{if(!a.isDestroyed()&&a.session==s&&dialog.isShowing())status.setText(summary(s.timeZone.status()));};
    dialog.setOnDismissListener(ignored->s.timeZone.removeListener(update));
    dialog.buttons("关闭",dialog::dismiss,"应用并重新加载",()->{
      String selected=mode.getSelectedItemPosition()==0?"":mode.getSelectedItemPosition()==1?"UTC":zone.getText().toString();
      dialog.primary().setEnabled(false);result.setText("正在核对时区名称与当前网页…");
      s.environmentIo.execute(()->{
        GeckoTimeZoneSpec spec=null;String error="";try{spec=GeckoTimeZoneSpec.of(selected);}catch(Exception invalid){error=invalid.getMessage();}
        GeckoTimeZoneSpec wanted=spec;String invalid=error;s.handler.post(()->{
          if(a.isDestroyed()||a.isFinishing()||a.session!=s||!dialog.isShowing())return;
          Consumer<String> done=message->{if(!a.isDestroyed()&&a.session==s&&dialog.isShowing()){
            dialog.primary().setEnabled(true);result.setText(message==null||message.isEmpty()?"配置已保存，正在等待当前会话的原生确认；页面与 Worker 的结果请分别自检。"+(wanted!=null&&!wanted.followsSystem()?"Service Worker 仍可读取系统时区，不能提供完整时区隔离。":""):message);
            if(s.timeZone.cached!=null&&wanted!=null&&s.timeZone.cached.spec.equals(wanted))expected[0]=s.timeZone.cached;update.run();
          }};
          if(!invalid.isEmpty()){done.accept(invalid);return;}
          applySafely(a,s,expected[0],wanted,done);
        });
      });
    });dialog.show();s.timeZone.addListener(update);update.run();
  }
  static String summary(JSONObject status){
    String zone=status.opt("desiredZone") instanceof String?(String)status.opt("desiredZone"):"";
    String desired=status.optBoolean("loaded")?(zone.isEmpty()?"跟随系统时区":zone):"尚未读取";
    String current=status.optBoolean("nativeSettingReadback")?"当前会话原生设置已回读；页面与 Worker 尚未验证":"尚未取得当前会话的原生设置确认";
    String issue=status.optString("issue");return "已保存："+desired+"\n当前："+current+(status.optBoolean("loaded")&&!zone.isEmpty()?"\nService Worker 仍可读取系统时区，不能提供完整时区隔离。":"")+(issue.isEmpty()?"":"\n"+issue);
  }
  static String busy(ChatSession s,boolean ownsCapture){return BrowserSettingsPolicy.reason(s.pending!=null,s.submitting,s.operation&&!ownsCapture,s.transferActive,s.fileWorkActive()||s.resourceFilesUncertain(),s.currentReplyActive());}
  /** Native fence uses only current in-memory state, with catalog identity
   * checked again under the store's writer transaction before publication. */
  static final class Fence {
    final Object nativeSession,port;final String url,document,scope;final long epoch,files,web,operations;
    Fence(ChatSession s,String document){nativeSession=s.web.current;port=s.web.ports.get(s.web.current);url=s.web.getUrl();this.document=document;scope=s.pageMemory.scope();epoch=s.navigationEpoch;files=s.fileWorkGeneration;web=s.webWorkGeneration;operations=s.operationGeneration;}
    boolean current(ChatSession s){return !s.deleted&&nativeSession==s.web.current&&port==s.web.ports.get(s.web.current)&&epoch==s.navigationEpoch&&BrowserRuntimePolicy.sameDocument(url,s.web.getUrl())
        &&scope.equals(s.pageMemory.scope())&&files==s.fileWorkGeneration&&web==s.webWorkGeneration&&operations==s.operationGeneration
        &&(document.isEmpty()||s.lastDocumentId.isEmpty()||document.equals(s.lastDocumentId));}
  }
  private static boolean activity(MainActivity a,ChatSession s){return !a.isDestroyed()&&!a.isFinishing()&&a.session==s&&!s.deleted;}
  static void applySafely(MainActivity a,ChatSession s,GeckoTimeZoneStore.State expected,GeckoTimeZoneSpec wanted,Consumer<String> done){
    if(!activity(a,s)){done.accept("当前环境已变化，未保存时区");return;}
    if(GeckoTimeZonePolicy.protectionConflict(s.privacy.level(),wanted)){done.accept("强化模板优先使用自己的时区策略，请先明确选择其他模板；强化保护保持不变");return;}
    String reason=busy(s,false);if(!reason.isEmpty()){done.accept(reason);return;}
    Fence fence=new Fence(s,s.lastDocumentId);
    if(!s.web.hasVisibleDocument()){confirm(a,s,expected,wanted,fence,null,true,done);return;}
    if(!MainActivity.chatUrl(fence.url)){confirm(a,s,expected,wanted,fence,null,true,done);return;}
    s.requestTaskGuardStatus("timezone",guard->{
      if(!activity(a,s)||!fence.current(s)){done.accept("网页已变化，未保存时区");return;}
      if(guard.busyOrUnknown()){done.accept("网页回复或附件状态尚未确认，请完成当前操作后再应用时区");return;}
      s.asyncDriver("page-state",J.obj("expectedUrl",fence.url),2500,page->{
        if(!fence.current(s)||!PageMemory.completeDraft(page)||!BrowserRuntimePolicy.sameDocument(fence.url,page.optString("url"))||page.optString("draft").length()>300000){done.accept("当前草稿无法完整读取，时区未保存；请先手动保留输入");return;}
        Fence observed=new Fence(s,page.optString("documentId"));
        confirm(a,s,expected,wanted,observed,page,PageMemory.hasDraft(page)&&!LocalDraftPolicy.enabled(s.context),done);
      });
    });
  }
  private static void confirm(MainActivity a,ChatSession s,GeckoTimeZoneStore.State expected,GeckoTimeZoneSpec wanted,Fence fence,JSONObject page,boolean manual,Consumer<String> done){
    if(!activity(a,s)||!fence.current(s)){done.accept("当前网页已变化，未保存时区");return;}
    ReferenceUi.Modal confirm=new ReferenceUi.Modal(a,"应用当前环境时区？");
    confirm.note("保存为“"+wanted.label()+"”后将重新加载当前网页，并关闭此环境已打开的弹窗。不会自动重发提问。");
    if(!wanted.followsSystem())confirm.note("Service Worker 仍可读取系统时区，不能提供完整时区隔离。原生设置回读不代表当前页面或 Worker 已通过验证。");
    if(page==null&&s.web.hasVisibleDocument()||manual&&page!=null)confirm.note("当前网站的回复、上传、输入或表单不能完整自动核对与保留。请先取消并结束网站操作、手动保存；继续表示已结束相关操作并保留需要的内容。");
    else if(page!=null&&PageMemory.hasDraft(page))confirm.note("当前 ChatGPT 草稿会先暂存并再次核对。若输入变化或无法暂存，将保留网页并停止应用。");
    boolean[] accepted={false};confirm.setOnDismissListener(ignored->{if(!accepted[0])done.accept("已取消，时区未保存");});
    confirm.buttons("取消",confirm::dismiss,manual?"已保存输入，应用":"应用并重新加载",()->{
      accepted[0]=true;confirm.dismiss();
      if(!activity(a,s)||!fence.current(s)||!busy(s,false).isEmpty()){done.accept("网页或当前任务已变化，时区未保存");return;}
      s.operation=true;s.configurationCapture=true;
      Consumer<String> finish=message->{s.operation=false;s.configurationCapture=false;s.changed();done.accept(message);};
      long draftRevision=LocalDraftPolicy.revision(s.context);
      if(page==null||manual){commit(a,s,expected,wanted,fence,null,manual,draftRevision,finish);return;}
      s.environmentIo.execute(()->{
        boolean saved=false;try{saved=!PageMemory.hasDraft(page)||DraftArchive.get(s.context).save(fence.url,page.optString("draft"),"应用独立时区前的草稿",draftRevision);}catch(Exception ignored){}
        boolean stored=saved;s.handler.post(()->{
          if(!activity(a,s)||!fence.current(s)||!stored){finish.accept("草稿暂存未完成或网页已变化，时区未保存");return;}
          s.asyncDriver("page-state",J.obj("expectedUrl",fence.url),2500,fresh->{
            if(!fence.current(s)||!PageMemory.completeDraft(fresh)||!page.optString("documentId").equals(fresh.optString("documentId"))||!page.optString("draft").equals(fresh.optString("draft"))
                ||PageMemory.hasDraft(fresh)&&(!LocalDraftPolicy.enabled(s.context)||draftRevision!=LocalDraftPolicy.revision(s.context))){finish.accept("当前输入或草稿保存设置已变化，网页保留，时区未保存");return;}
            commit(a,s,expected,wanted,fence,fresh,false,draftRevision,finish);
          });
        });
      });
    });confirm.show();
  }
  private static void commit(MainActivity a,ChatSession s,GeckoTimeZoneStore.State expected,GeckoTimeZoneSpec wanted,Fence fence,JSONObject page,boolean manual,long draftRevision,Consumer<String> done){
    BooleanSupplier safe=()->activity(a,s)&&fence.current(s)&&busy(s,true).isEmpty()
        &&(page==null||manual||!PageMemory.hasDraft(page)||LocalDraftPolicy.enabled(s.context)&&draftRevision==LocalDraftPolicy.revision(s.context));
    if(!safe.getAsBoolean()){done.accept("当前网页或任务已变化，时区未保存");return;}
    if(page!=null&&!manual){s.pageMemory.remember(fence.scope,fence.url,page);s.web.checkpointState();}
    else if(manual&&s.web.hasVisibleDocument())s.pageMemory.forget(fence.url);
    Consumer<Consumer<Boolean>> finalDraftCheck=checked->{
      if(page==null||manual){checked.accept(safe.getAsBoolean());return;}
      s.asyncDriver("page-state",J.obj("expectedUrl",fence.url),2500,latest->checked.accept(safe.getAsBoolean()&&PageMemory.completeDraft(latest)
          &&page.optString("documentId").equals(latest.optString("documentId"))&&page.optString("draft").equals(latest.optString("draft"))));
    };
    s.timeZone.saveConfirmed(expected,wanted,safe,finalDraftCheck,done);
  }
}
