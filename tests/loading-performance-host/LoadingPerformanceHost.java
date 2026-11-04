package local.pocketchat;

import java.util.*;

/** Production methods are inserted verbatim; native views and time are explicit adapters. */
public final class LoadingPerformanceHost {
  static final boolean baseline=Boolean.getBoolean("baseline");
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static LoadingUi create(boolean visible,boolean deferred){
    android.os.SystemClock.now=1000;android.animation.ValueAnimator.enabled=true;
    MainActivity a=new MainActivity();a.session.web.visible=visible;a.session.web.resourceDeferred=deferred;
    LoadingUi ui=new LoadingUi(a);ui.fitActions();ui.update();return ui;
  }
  static Map<String,Object> steady(String name,LoadingUi ui,int baselineText,int baselineCancel){
    Metrics.reset();int actions=ui.a.session.web.actions;
    for(int i=0;i<100;i++)ui.update();
    Map<String,Object> result=Metrics.snapshot();
    check(name+" text assignment count",Metrics.text==(baseline?baselineText:0));
    check(name+" animation cancel count",Metrics.animationCancel==(baseline?baselineCancel:0));
    check(name+" never starts repeated fades",Metrics.animationStart==0);
    check(name+" never invokes browser actions",ui.a.session.web.actions==actions);
    if(!baseline)check(name+" no unchanged presentation assignments",Metrics.presentationWrites()==0);
    check(name+" no redundant orientation/layout assignments",Metrics.layout==0&&Metrics.orientation==0);
    return result;
  }
  public static void main(String[] args){
    Map<String,Object> workloads=new LinkedHashMap<>();
    LoadingUi live=create(true,false);
    check("Live document starts without loading cover",!live.coverShown&&live.cover.visibility==View.GONE);
    workloads.put("live100",steady("100 identical live-document updates",live,100,0));

    LoadingUi empty=create(false,false);
    check("Empty connecting document shows cover and spinner",empty.coverShown&&empty.cover.visibility==View.VISIBLE&&empty.cover.alpha==1&&empty.wheel.visibility==View.VISIBLE);
    check("Connecting copy and actions match original state",empty.title.text.equals("正在连接当前线路")&&empty.retry.visibility==View.GONE&&empty.website.visibility==View.GONE);
    workloads.put("empty100",steady("100 identical empty-page updates",empty,200,100));
    empty.a.resources.configuration.orientation=android.content.res.Configuration.ORIENTATION_LANDSCAPE;Metrics.reset();empty.update();
    check("Orientation change still updates stable empty state",empty.actions.orientation==LinearLayout.HORIZONTAL&&empty.retry.params.width==0&&empty.retry.params.weight==1&&empty.website.params.leftMargin==12&&Metrics.layout==2);
    Metrics.reset();empty.update();check("Repeated orientation produces no layout mutations",Metrics.layout==0&&Metrics.orientation==0);
    empty.a.resources.configuration.orientation=android.content.res.Configuration.ORIENTATION_PORTRAIT;empty.update();
    check("Portrait restores full-width stacked actions",empty.actions.orientation==LinearLayout.VERTICAL&&empty.retry.params.width==-1&&empty.website.params.leftMargin==0);

    android.os.SystemClock.now=20999;empty.update();check("Waiting hint stays normal before20seconds",empty.title.text.equals("正在连接当前线路"));
    android.os.SystemClock.now=21000;empty.update();check("20second boundary changes loading explanation",empty.title.text.equals("连接时间较长")&&empty.hint.text.contains("不会自动重发消息")&&empty.wheel.visibility==View.GONE&&empty.website.visibility==View.VISIBLE);
    check("Slow hint preserves normal retry visibility",empty.retry.visibility==View.GONE);
    empty.a.session.connecting=false;empty.a.session.networkReady=true;android.os.SystemClock.now=1000;empty.update();
    check("Clock rollback resets slow state and exposes loading stage",empty.title.text.equals("正在加载网页")&&empty.wheel.visibility==View.VISIBLE);
    empty.a.session.connectionStage="正在核实当前环境";empty.update();check("Connection stage change renders immediately",empty.hint.text.contains("正在核实当前环境"));

    LoadingUi deferred=create(false,true);
    check("Deferred empty surface exposes retry without network action",deferred.coverShown&&deferred.title.text.equals("稍后打开当前环境")&&deferred.hint.text.equals(ResourcePressureController.DEFERRED_MESSAGE)&&deferred.retry.text.equals("重试打开")&&deferred.retry.visibility==View.VISIBLE&&deferred.website.visibility==View.GONE&&deferred.wheel.visibility==View.GONE);
    workloads.put("deferred100",steady("100 identical deferred-page updates",deferred,300,100));
    android.os.SystemClock.now=90000;deferred.update();check("Deferred state does not acquire slow timeout copy",deferred.title.text.equals("稍后打开当前环境"));
    deferred.a.session.web.resourceDeferred=false;deferred.update();
    check("Deferred to normal starts fresh wait and restores retry label",deferred.title.text.equals("正在连接当前线路")&&deferred.retry.text.equals("重新加载"));
    android.os.SystemClock.now=109999;deferred.update();check("Deferred interval does not count as loading time",deferred.title.text.equals("正在连接当前线路"));
    android.os.SystemClock.now=110000;deferred.update();check("Fresh normal wait reaches20second boundary",deferred.title.text.equals("连接时间较长"));

    LoadingUi error=create(false,false);error.a.session.connecting=false;error.a.session.status="已应用保存的网页显示和保护设置";error.a.session.networkIssue="线路尚未连通";error.update();
    check("Network error uses real network detail",error.title.text.equals("网页暂时无法打开")&&error.hint.text.equals("线路尚未连通")&&error.retry.visibility==View.VISIBLE&&error.website.visibility==View.VISIBLE);
    check("Error suppresses native banner and spinner",error.a.status.visibility==View.GONE&&error.wheel.visibility==View.GONE);
    error.a.session.navigationFailed=true;error.a.session.pageError="当前网页加载失败";error.update();check("Page error detail takes precedence",error.hint.text.equals("当前网页加载失败"));
    error.a.session.pageError="";error.a.session.networkIssue="";error.update();check("Missing error detail uses retained fallback",error.hint.description.equals("网页尚未打开。请重新加载或检查当前环境网络。"));
    error.a.session.status="网页反馈：需要重新加载";error.update();check("Readable action word preserves plain accessibility copy",error.hint.text.contains("\u2060")&&error.hint.description.equals("网页反馈：需要重新加载"));
    Metrics.reset();error.update();if(!baseline)check("Unchanged readable copy avoids setter and description work",Metrics.text==0&&Metrics.description==0);else check("Baseline repeats readable copy assignment",Metrics.text==2&&Metrics.description==1);

    LoadingUi transition=create(false,false);transition.a.session.web.visible=true;Metrics.reset();transition.update();
    check("Live-document transition starts one180ms fade",!transition.coverShown&&transition.cover.animator.duration==180&&Metrics.animationStart==1);
    Runnable stale=transition.cover.animator.endAction;Metrics.reset();transition.update();check("Repeated live state does not restart fade",Metrics.animationStart==0);
    transition.a.session.web.visible=false;transition.update();check("Reappearing empty cover restores alpha and visibility",transition.coverShown&&transition.cover.alpha==1&&transition.cover.visibility==View.VISIBLE);
    stale.run();check("Old fade completion cannot hide reappeared cover",transition.coverShown&&transition.cover.visibility==View.VISIBLE);
    transition.a.session.web.visible=true;transition.update();transition.cover.animator.finish();check("Current fade completion hides completed cover",!transition.coverShown&&transition.cover.visibility==View.GONE);
    transition.a.session.web.visible=false;transition.update();android.animation.ValueAnimator.enabled=false;transition.a.session.web.visible=true;Metrics.reset();transition.update();
    check("Disabled system animations hide cover immediately",!transition.coverShown&&transition.cover.visibility==View.GONE&&transition.cover.alpha==0&&Metrics.animationStart==0);
    transition.a.session.web.visible=false;transition.update();check("Cover recovers after immediate-hide transition",transition.coverShown&&transition.cover.alpha==1&&transition.cover.visibility==View.VISIBLE);
    transition.a.session.web.visible=true;transition.a.session.web.resourceDeferred=true;transition.a.session.navigationFailed=true;transition.a.session.connecting=false;transition.a.session.networkReady=false;transition.update();
    check("Live document wins over deferred and failure state",!transition.coverShown&&transition.cover.visibility==View.GONE);
    MainActivity owner=transition.a;owner.session=null;Metrics.reset();transition.update();check("Missing session performs no presentation work",Metrics.presentationWrites()==0);

    Map<String,Object> report=new LinkedHashMap<>();report.put("status","passed");report.put("passed",checks.size());report.put("total",checks.size());report.put("baseline",baseline);report.put("updatesPerWorkload",100);report.put("workloads",workloads);report.put("checks",checks);
    System.out.println(json(report));
  }
  static String json(Object value){
    if(value==null)return "null";if(value instanceof Boolean||value instanceof Number)return value.toString();
    if(value instanceof Map){List<String> out=new ArrayList<>();for(Object raw:((Map<?,?>)value).entrySet()){Map.Entry<?,?> row=(Map.Entry<?,?>)raw;out.add(json(row.getKey())+":"+json(row.getValue()));}return "{"+String.join(",",out)+"}";}
    if(value instanceof Iterable){List<String> out=new ArrayList<>();for(Object item:(Iterable<?>)value)out.add(json(item));return "["+String.join(",",out)+"]";}
    return "\""+value.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";
  }
}

final class LoadingUi {
  final MainActivity a;final LinearLayout band=new LinearLayout(),cover=new LinearLayout(),actions=new LinearLayout();
  final TextView bandText=new TextView(),title=new TextView(),hint=new TextView();final ProgressBar wheel=new ProgressBar();final Button retry=new Button(),website=new Button();
  boolean actionLayoutKnown,actionsHorizontal;final PageLoadingWait wait=new PageLoadingWait();
  boolean coverShown,hintBound;String lastTitle="",lastHint;
  LoadingUi(MainActivity a){this.a=a;cover.visibility=View.GONE;band.visibility=View.GONE;retry.text="重新加载";website.text="检查网络";}
  /* PRODUCTION_METHODS */
}
final class Metrics {
  static int text,description,visibility,alpha,animationCancel,animationStart,animationAlpha,layout,orientation;
  static void reset(){text=description=visibility=alpha=animationCancel=animationStart=animationAlpha=layout=orientation=0;}
  static int presentationWrites(){return text+description+visibility+alpha+animationCancel+animationStart+animationAlpha+layout+orientation;}
  static Map<String,Object> snapshot(){Map<String,Object> out=new LinkedHashMap<>();out.put("textAssignments",text);out.put("contentDescriptionAssignments",description);out.put("visibilityAssignments",visibility);out.put("alphaAssignments",alpha);out.put("animationCancels",animationCancel);out.put("animationStarts",animationStart);out.put("animationAlphaAssignments",animationAlpha);out.put("layoutAssignments",layout);out.put("orientationAssignments",orientation);out.put("presentationWrites",presentationWrites());return out;}
}
class View {
  static final int VISIBLE=0,GONE=8;int visibility=VISIBLE;float alpha=1;final Animator animator=new Animator(this);final LinearLayout.LayoutParams params=new LinearLayout.LayoutParams();
  void setVisibility(int value){Metrics.visibility++;visibility=value;}int getVisibility(){return visibility;}
  void setAlpha(float value){Metrics.alpha++;alpha=value;}float getAlpha(){return alpha;}
  Animator animate(){return animator;}
  Object getLayoutParams(){return params;}void setLayoutParams(LinearLayout.LayoutParams value){Metrics.layout++;}
}
class TextView extends View {
  String text="",description="";void setText(String value){Metrics.text++;text=value;}String getText(){return text;}
  void setContentDescription(String value){Metrics.description++;description=value;}String getContentDescription(){return description;}
}
class EditText extends TextView {}
final class Button extends TextView {}
final class ProgressBar extends View {}
final class LinearLayout extends View {
  static final int HORIZONTAL=0,VERTICAL=1;int orientation=VERTICAL;void setOrientation(int value){Metrics.orientation++;orientation=value;}
  static final class LayoutParams {int width=-1,height=-2,topMargin,leftMargin;float weight;}
}
final class Animator {
  final View owner;long duration;Runnable endAction;float targetAlpha;
  Animator(View owner){this.owner=owner;}
  void cancel(){Metrics.animationCancel++;endAction=null;}
  Animator alpha(float value){Metrics.animationAlpha++;targetAlpha=value;return this;}
  Animator setDuration(long value){duration=value;return this;}
  Animator withEndAction(Runnable action){endAction=action;return this;}
  void start(){Metrics.animationStart++;}
  void finish(){owner.alpha=targetAlpha;Runnable action=endAction;endAction=null;if(action!=null)action.run();}
}
final class MainActivity {
  ChatSession session=new ChatSession();final TextView status=new TextView();final Resources resources=new Resources();int focusCalls;
  MainActivity(){status.visibility=View.GONE;}
  void applyFocusLayout(){focusCalls++;}Resources getResources(){return resources;}int dp(int value){return value;}
  /* CHROME_VISIBILITY */
}
final class Resources {final android.content.res.Configuration configuration=new android.content.res.Configuration();android.content.res.Configuration getConfiguration(){return configuration;}}
final class ChatSession {
  final Browser web=new Browser();boolean navigationFailed,connecting=true,networkReady;String status="正在连接",pageError="",networkIssue="",connectionStage="";
}
final class Browser {boolean visible,resourceDeferred;int actions;boolean hasVisibleDocument(){return visible;}}
final class DesignUi {/* READABLE_METHOD */}
final class ResourcePressureController {/* DEFERRED_CONSTANT */}
