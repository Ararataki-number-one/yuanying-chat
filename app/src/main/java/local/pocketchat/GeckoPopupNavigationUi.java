package local.pocketchat;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewTreeObserver;
import android.widget.Button;
import android.widget.FrameLayout;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoSession;

/** A blocked popup offers an explicit current-page action; websites never open a modal. */
final class GeckoPopupNavigationUi {
  final GeckoWebView web;
  Target pending;Attempt attempt;Button action;ReferenceUi.Modal dialog;
  View dialogDecor;ViewTreeObserver.OnWindowFocusChangeListener dialogFocus;
  Application lifecycleApplication;MainActivity lifecycleActivity;
  GeckoSession offeredSession;Object offeredGate;long offeredDocument=-1;boolean closed,leaving;
  final Application.ActivityLifecycleCallbacks lifecycle=new Application.ActivityLifecycleCallbacks(){
    public void onActivityCreated(Activity activity,Bundle state){}
    public void onActivityStarted(Activity activity){}
    public void onActivityResumed(Activity activity){}
    public void onActivityPaused(Activity activity){if(activity==lifecycleActivity)invalidate();}
    public void onActivityStopped(Activity activity){if(activity==lifecycleActivity)invalidate();}
    public void onActivitySaveInstanceState(Activity activity,Bundle state){}
    public void onActivityDestroyed(Activity activity){if(activity==lifecycleActivity)invalidate();}
  };

  GeckoPopupNavigationUi(GeckoWebView web){this.web=web;}

  static boolean targetAllowed(String value){return value!=null&&value.length()<=8192&&value.equals(value.trim())&&GeckoNavigationPolicy.publicWeb(value)&&!RequestIdentityAudit.diagnosticUrl(value);}
  static boolean completePage(JSONObject page,String url){
    Object length=page==null?null:page.opt("draftLength"),document=page==null?null:page.opt("documentId");
    return PageMemory.completeDraft(page)&&Boolean.TRUE.equals(page.opt("draftComplete"))&&(length instanceof Integer||length instanceof Long)
        &&((Number)length).longValue()==page.optString("draft").length()&&document instanceof String&&!((String)document).isEmpty()&&((String)document).length()<=160&&url.equals(page.optString("url"));
  }
  static boolean sameDraft(JSONObject saved,JSONObject current,String url){return completePage(saved,url)&&completePage(current,url)&&saved.optString("documentId").equals(current.optString("documentId"))&&saved.optString("draft").equals(current.optString("draft"));}
  static boolean idle(TaskGuardSnapshot value,ChatSession owner,boolean ownCapture){return value!=null&&value.known&&!value.replyBusy&&!value.fileBusy&&!value.submitting&&!value.downloading&&(!value.operation||ownCapture)
      &&value.generation==owner.environmentGeneration&&value.environmentId.equals(owner.environmentId)&&value.navigationEpoch==owner.navigationEpoch;}

  static final class Target {
    final MainActivity activity;final ChatSession owner;final GeckoSession sdk;final Object runtime,gate,pagePort,routePort;
    final String source,target,environment,openEpoch,route;final int slot,generation;
    final long document,navigation,connection,identity,protection,desired,draftRevision;final boolean drafts;
    final GeckoTimeZoneUi.Fence work;
    Target(MainActivity activity,GeckoWebView web,GeckoSession sdk,String target){
      this.activity=activity;owner=web.owner;this.sdk=sdk;this.target=target;source=web.getUrl();runtime=web.runtime;
      GeckoWebView.TimeZoneGate current=web.timeZoneGates.get(sdk);gate=current;openEpoch=current==null?"":current.epoch;document=current==null?-1:current.documentSerial;
      pagePort=web.ports.get(sdk);routePort=web.routePort;navigation=owner.navigationEpoch;connection=owner.connectionEpoch;identity=web.identityPolicyRevision;protection=web.nativeProtection.token();
      desired=owner.timeZone.status().optLong("desiredRevision",-1);slot=Profiles.slot(owner.context);environment=owner.environmentId;generation=owner.environmentGeneration;route=web.ipRouteStamp();
      draftRevision=LocalDraftPolicy.revision(owner.context);drafts=LocalDraftPolicy.enabled(owner.context);work=new GeckoTimeZoneUi.Fence(owner,owner.lastDocumentId);
    }
    boolean current(GeckoPopupNavigationUi ui){
      GeckoWebView view=ui.web;GeckoWebView.TimeZoneGate actual=view.timeZoneGates.get(sdk);
      return !ui.closed&&!view.destroyed&&!view.failed&&!view.addonDisabled&&!owner.deleted&&view.owner==owner&&activity.session==owner&&activity.remote==view
          &&!activity.isDestroyed()&&!activity.isFinishing()&&activity.active&&owner.uiVisible&&!owner.browserPaused&&view.displayContext.getBaseContext()==activity
          &&view.current==sdk&&sdk.isOpen()&&!view.crashed.contains(sdk)&&view.runtime==runtime&&runtime!=null&&actual==gate&&actual!=null&&actual.epoch.equals(openEpoch)&&actual.documentSerial==document
          &&pagePort!=null&&view.ports.get(sdk)==pagePort&&routePort!=null&&view.routePort==routePort&&source.equals(view.getUrl())&&navigation==owner.navigationEpoch&&connection==owner.connectionEpoch
          &&identity==view.identityPolicyRevision&&protection==view.nativeProtection.token()&&desired>=1&&owner.timeZone.status().optLong("desiredRevision",-1)==desired
          &&slot==Profiles.slot(owner.context)&&generation==owner.environmentGeneration&&environment.equals(owner.environmentId)&&draftRevision==LocalDraftPolicy.revision(owner.context)&&drafts==LocalDraftPolicy.enabled(owner.context)
          &&work.current(owner)&&view.hasVisibleDocument()&&view.readingOwnerVisible()&&view.isShown()&&!view.ipRouteNeedsReload&&view.timeZoneAllows(sdk)
          &&owner.guard.allowed()&&!route.isEmpty()&&route.equals(view.ipRouteStamp())&&targetAllowed(target)&&ui.focusOwned(activity);
    }
  }
  static final class Attempt {
    final Target target;GeckoTimeZoneUi.Fence work;JSONObject page;boolean manual,confirmed,ownsCapture;long captureGeneration,draftRevision;
    Attempt(Target target){this.target=target;work=target.work;draftRevision=target.draftRevision;}
  }

  boolean focusOwned(MainActivity activity){return web.hasWindowFocus()||dialog!=null&&dialog.isShowing()&&dialog.getWindow()!=null&&dialog.getWindow().getDecorView().hasWindowFocus();}
  String changedMessage(){return web.ipRouteNeedsReload?"线路已变化，请先在“独立时区”中重新匹配，再重试打开链接":"网页、任务或设置已变化，当前网页已保留；请重新操作链接";}
  boolean valid(Attempt value,boolean ownCapture){return value!=null&&attempt==value&&pending==value.target&&value.target.current(this)&&value.work.current(web.owner)&&GeckoTimeZoneUi.busy(web.owner,ownCapture).isEmpty();}

  void offer(GeckoSession source,String target){
    if(closed||web.destroyed||source==null||source!=web.current||!source.isOpen()||!web.hasVisibleDocument())return;
    if(!targetAllowed(target)){invalidate();return;}
    Context host=web.displayContext.getBaseContext();if(!(host instanceof MainActivity))return;MainActivity activity=(MainActivity)host;
    if(web.ipRouteNeedsReload){web.owner.setStatus(changedMessage());return;}
    Target next=new Target(activity,web,source,target);if(!next.current(this))return;
    boolean same=offeredSession==source&&offeredGate==next.gate&&offeredDocument==next.document;
    if(same&&action==null)return;
    stopFlow();pending=next;if(!same){removeAction();offeredSession=source;offeredGate=next.gate;offeredDocument=next.document;}watchLifecycle(activity);
    if(action==null){
      action=ReferenceUi.button(activity,"弹窗已拦截 · 在当前页打开",false,this::begin);action.setTextSize(14);action.setMaxLines(2);action.setMaxWidth(DesignUi.dp(activity,360));action.setMinimumHeight(DesignUi.dp(activity,48));action.setMinimumWidth(DesignUi.dp(activity,48));action.setElevation(DesignUi.dp(activity,4));
      FrameLayout.LayoutParams layout=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);layout.leftMargin=layout.rightMargin=DesignUi.dp(activity,12);layout.topMargin=DesignUi.dp(activity,8);web.addView(action,layout);
    }
    action.setContentDescription("弹窗已拦截，在当前页打开："+target);action.setEnabled(true);action.bringToFront();
  }
  void begin(){
    Target selected=pending;if(selected==null||!selected.current(this)){invalidate();web.owner.setStatus(changedMessage());return;}
    String busy=GeckoTimeZoneUi.busy(web.owner,false);if(!busy.isEmpty()){web.owner.setStatus(busy);return;}
    stopFlow();Attempt value=new Attempt(selected);attempt=value;action.setEnabled(false);
    if(!MainActivity.chatUrl(selected.source)){value.manual=true;confirm(value);return;}
    web.owner.requestTaskGuardStatus("popup-current-page",guard->{
      if(!valid(value,false)||!idle(guard,web.owner,false)){fail(value,"网页回复或附件状态尚未确认，请完成当前操作后再打开链接");return;}
      web.owner.asyncDriver("page-state",J.obj("expectedUrl",selected.source),2500,page->{
        if(!valid(value,false)||!completePage(page,selected.source)){fail(value,"当前 ChatGPT 输入无法完整读取，请先手动保留输入后重试");return;}
        value.page=page;value.work=new GeckoTimeZoneUi.Fence(web.owner,page.optString("documentId"));value.manual=PageMemory.hasDraft(page)&&!selected.drafts;confirm(value);
      });
    });
  }
  void confirm(Attempt value){
    if(!valid(value,false)){fail(value,changedMessage());return;}
    MainActivity activity=value.target.activity;ReferenceUi.Modal confirm=new ReferenceUi.Modal(activity,"在当前页打开链接？");dialog=confirm;
    confirm.note("新窗口已拦截。继续会用目标网页替换当前页，不会自动重发提问，也不能保证网站的登录跳转结果。");confirm.note(value.target.target);
    if(value.manual)confirm.note("请先结束网站正在进行的回复、上传或其他操作，并手动保存表单和输入。继续表示已完成这些操作并保留所需内容。"+(value.page!=null?"本机草稿保存已关闭，本次不会保存草稿副本。":""));
    else if(value.page!=null&&PageMemory.hasDraft(value.page))confirm.note("当前 ChatGPT 草稿会先暂存到本机并再次核对；若输入变化或无法暂存，当前网页会保留。");
    confirm.cancel=()->fail(value,"已取消，当前网页已保留");confirm.setOnDismissListener(ignored->{if(dialog==confirm){dialog=null;fail(value,"已取消，当前网页已保留");}});
    confirm.buttons("取消",confirm.cancel,value.manual?"已保存输入，在当前页打开":"在当前页打开",()->accept(value));confirm.show();
    dialogDecor=confirm.getWindow().getDecorView();View watched=dialogDecor;dialogFocus=focused->{if(!focused&&dialog==confirm&&!leaving)web.owner.handler.post(()->{if(dialog==confirm&&confirm.isShowing()&&!watched.hasWindowFocus())invalidate();});};watched.getViewTreeObserver().addOnWindowFocusChangeListener(dialogFocus);
  }
  void accept(Attempt value){
    if(!valid(value,false)||value.confirmed){fail(value,changedMessage());return;}value.confirmed=true;
    ChatSession owner=web.owner;value.captureGeneration=owner.operationGeneration;value.ownsCapture=true;owner.operation=true;owner.configurationCapture=true;
    if(dialog!=null&&dialog.primary()!=null)dialog.primary().setEnabled(false);
    if(value.page==null){commit(value);return;}
    if(!value.manual&&PageMemory.hasDraft(value.page)){
      owner.environmentIo.execute(()->{
        boolean archived=false;try{EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(value.target.slot,value.target.generation,value.target.environment);archived=ProfileCatalog.get(owner.context).withIdentity(identity,()->DraftArchive.get(owner.context).save(value.target.source,value.page.optString("draft"),"打开被拦截链接前草稿",value.draftRevision));}catch(Exception ignored){}
        boolean saved=archived;owner.handler.post(()->{if(!valid(value,true)||!saved){fail(value,"草稿暂存未完成或网页已变化，当前网页已保留");return;}reread(value,false);});
      });
    }else reread(value,false);
  }
  void reread(Attempt value,boolean last){
    if(!valid(value,true)){fail(value,changedMessage());return;}
    web.owner.asyncDriver("page-state",J.obj("expectedUrl",value.target.source),2500,fresh->{
      if(!valid(value,true)||!sameDraft(value.page,fresh,value.target.source)){fail(value,"当前输入已变化或无法完整核对，网页已保留");return;}
      if(last){value.page=fresh;commit(value);return;}
      web.owner.requestTaskGuardStatus("popup-final",guard->{
        if(!valid(value,true)||!idle(guard,web.owner,true)||!guard.documentId.equals(fresh.optString("documentId"))){fail(value,"网页回复或附件状态已变化，当前网页已保留");return;}
        reread(value,true);
      });
    });
  }
  void commit(Attempt value){
    if(!valid(value,true)||!value.confirmed||!value.ownsCapture||value.captureGeneration!=web.owner.operationGeneration||value.draftRevision!=LocalDraftPolicy.revision(web.owner.context)
        ||value.page!=null&&!completePage(value.page,value.target.source)){fail(value,changedMessage());return;}
    ChatSession owner=web.owner;
    if(value.page!=null&&!value.manual){owner.pageMemory.remember(value.work.scope,value.target.source,value.page);web.checkpointState();}
    else if(value.manual)owner.pageMemory.forget(value.target.source);
    String target=value.target.target;releaseCapture(value);attempt=null;pending=null;removeAction();unwatchLifecycle();leaving=true;dismissDialog();
    try{owner.browse(target,"正在打开网页…");}finally{leaving=false;owner.changed();}
  }
  void releaseCapture(Attempt value){
    if(value==null||!value.ownsCapture)return;value.ownsCapture=false;
    if(value.captureGeneration==web.owner.operationGeneration&&web.owner.configurationCapture){web.owner.operation=false;web.owner.configurationCapture=false;}
  }
  void fail(Attempt value,String message){
    if(attempt!=value)return;stopFlow();if(pending!=null&&!pending.current(this))invalidate();web.owner.setStatus(message);web.owner.changed();
  }
  void dismissDialog(){ReferenceUi.Modal previous=dialog;dialog=null;if(dialogDecor!=null&&dialogFocus!=null&&dialogDecor.getViewTreeObserver().isAlive())dialogDecor.getViewTreeObserver().removeOnWindowFocusChangeListener(dialogFocus);dialogDecor=null;dialogFocus=null;if(previous!=null&&previous.isShowing())previous.dismiss();}
  void stopFlow(){Attempt previous=attempt;attempt=null;releaseCapture(previous);dismissDialog();if(action!=null)action.setEnabled(true);}
  void removeAction(){if(action!=null){web.removeView(action);action=null;}}
  void watchLifecycle(MainActivity activity){if(lifecycleActivity==activity)return;unwatchLifecycle();lifecycleActivity=activity;lifecycleApplication=activity.getApplication();lifecycleApplication.registerActivityLifecycleCallbacks(lifecycle);}
  void unwatchLifecycle(){if(lifecycleApplication!=null)lifecycleApplication.unregisterActivityLifecycleCallbacks(lifecycle);lifecycleApplication=null;lifecycleActivity=null;}
  void invalidate(){stopFlow();pending=null;removeAction();unwatchLifecycle();}
  void focusChanged(boolean focused){
    if(closed||leaving)return;
    if(focused){if(pending!=null&&!pending.current(this))invalidate();return;}
    // Our explicit confirmation owns another native window. Its loss of focus
    // is checked after the window handoff, never interpreted as website consent.
    web.owner.handler.post(()->{if(!closed&&!leaving&&pending!=null&&!pending.current(this))invalidate();});
  }
  void close(){if(closed)return;closed=true;invalidate();}
}
