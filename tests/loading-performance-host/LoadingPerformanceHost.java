package local.pocketchat;

import java.util.*;

/** Production methods are inserted verbatim; native views and time are explicit adapters. */
public final class LoadingPerformanceHost {
  static final boolean baseline=Boolean.getBoolean("baseline");
  static final boolean compactLayout=Boolean.getBoolean("compactLayout");
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
    if(!baseline)check(name+" no repeated action text measurements",Metrics.measures==0);
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

    if(!baseline){
      LoadingUi responsive=create(false,false);responsive.a.resources.configuration.orientation=android.content.res.Configuration.ORIENTATION_LANDSCAPE;
      int required=2*Math.max(DesignUi.actionWidth(responsive.retry,48),DesignUi.actionWidth(responsive.website,48))+12;
      responsive.cover.width=required+responsive.cover.paddingLeft+responsive.cover.paddingRight;responsive.update();
      check("Equal-weight actions fit at the exact measured width boundary",responsive.actions.orientation==LinearLayout.HORIZONTAL&&responsive.retry.params.width==0&&responsive.website.params.weight==1);
      responsive.cover.width--;responsive.update();check("One pixel below the measured boundary keeps both actions stacked",responsive.actions.orientation==LinearLayout.VERTICAL&&responsive.retry.params.width==-1&&responsive.website.params.width==-2&&responsive.website.params.topMargin==4);
      responsive.cover.width=900;responsive.update();check("A wider same-orientation cover restores equal-weight actions",responsive.actions.orientation==LinearLayout.HORIZONTAL);
      responsive.a.resources.configuration.fontScale=2f;responsive.update();check("Enlarged labels retain safe stacked actions within the content width cap",responsive.actions.orientation==LinearLayout.VERTICAL);
      responsive.a.resources.configuration.fontScale=1f;responsive.update();check("Restoring label scale re-evaluates the measured action width",responsive.actions.orientation==LinearLayout.HORIZONTAL);
      responsive.website.setText("检查当前环境网络");responsive.update();check("An unequal longer label must fit its own equal-weight half",responsive.actions.orientation==LinearLayout.VERTICAL);
      responsive.website.setText("检查网络");responsive.update();check("Restoring a short label invalidates the width cache",responsive.actions.orientation==LinearLayout.HORIZONTAL);
      android.os.SystemClock.now=21000;responsive.update();check("Network-first ordering retains the same native buttons and correct leading gap",responsive.actions.children.get(0)==responsive.website&&responsive.actions.children.get(1)==responsive.retry&&responsive.website.params.leftMargin==0&&responsive.retry.params.leftMargin==12);
      Metrics.reset();for(int i=0;i<100;i++)responsive.update();check("Stable wide landscape updates do not remeasure or rewrite presentation",Metrics.measures==0&&Metrics.presentationWrites()==0);
    }
    if(!baseline&&compactLayout){
      LoadingUi shortWindow=create(false,false);shortWindow.a.session.connecting=false;shortWindow.a.session.connectionStage="等待手机 VPN";shortWindow.a.session.status="手机 VPN 未连接，已暂停网页联网；连接 VPN 后，点击“重新加载”。";
      shortWindow.a.resources.configuration.orientation=android.content.res.Configuration.ORIENTATION_LANDSCAPE;shortWindow.update();shortWindow.layoutCover(132);
      check("Short viewport puts both real actions before scrollable explanation",shortWindow.content.children.indexOf(shortWindow.title)<shortWindow.content.children.indexOf(shortWindow.actions)&&shortWindow.content.children.indexOf(shortWindow.actions)<shortWindow.content.children.indexOf(shortWindow.hint)&&shortWindow.actions.children.contains(shortWindow.retry)&&shortWindow.actions.children.contains(shortWindow.website));
      check("Short viewport keeps all real content and hides only the decorative emblem",shortWindow.emblem.visibility==View.GONE&&shortWindow.title.visibility==View.VISIBLE&&shortWindow.hint.visibility==View.VISIBLE&&shortWindow.guidance.visibility==View.VISIBLE&&shortWindow.retry.visibility==View.VISIBLE&&shortWindow.website.visibility==View.VISIBLE&&shortWindow.actions.orientation==LinearLayout.HORIZONTAL);
      // Actual API 35 evidence measured this native title at 79px at density3.
      // The 48dp buttons and existing12dp horizontal top gap are unchanged.
      int actionBottom=shortWindow.cover.paddingTop+shortWindow.title.params.topMargin+27+shortWindow.title.params.bottomMargin+shortWindow.actions.params.topMargin+shortWindow.website.params.topMargin+48;
      check("Observed132dp cover fits the complete48dp action row before scrolling",actionBottom<=132-shortWindow.cover.paddingBottom&&shortWindow.cover.paddingTop==6&&shortWindow.cover.paddingBottom==6&&shortWindow.overflow.scrollY==0);
      check("Compact layout preserves true VPN error and primary action",shortWindow.title.text.equals("等待 VPN 连接")&&shortWindow.hint.description.equals("网页联网已暂停。\n连接手机 VPN 后，再重新加载。")&&shortWindow.actions.children.get(0)==shortWindow.website);
      Metrics.reset();for(int i=0;i<100;i++){shortWindow.layoutCover(132);shortWindow.update();}
      check("Repeated short-window measurement is idle and invokes no actions",Metrics.presentationWrites()==0&&Metrics.measures==0&&shortWindow.a.session.web.actions==0);
      shortWindow.overflow.scrollY=80;shortWindow.a.resources.configuration.orientation=android.content.res.Configuration.ORIENTATION_PORTRAIT;shortWindow.layoutCover(480);shortWindow.update();
      check("Restored portrait retains original order decorative emblem and spacing",shortWindow.emblem.visibility==View.VISIBLE&&shortWindow.content.children.indexOf(shortWindow.hint)<shortWindow.content.children.indexOf(shortWindow.actions)&&shortWindow.cover.paddingTop==20&&shortWindow.cover.paddingBottom==28&&shortWindow.title.params.topMargin==14&&shortWindow.title.params.bottomMargin==6&&shortWindow.actions.params.topMargin==16&&shortWindow.hint.params.topMargin==0&&shortWindow.guidance.params.topMargin==24&&shortWindow.actions.orientation==LinearLayout.VERTICAL&&shortWindow.overflow.scrollY==0);
      shortWindow.layoutCover(0);check("Unknown viewport height does not replace the measured arrangement",!shortWindow.compactCover&&shortWindow.emblem.visibility==View.VISIBLE);
    }

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
  final MainActivity a;final LinearLayout band=new LinearLayout(),cover=new LinearLayout(),content=new LinearLayout(),actions=new LinearLayout();final View emblem=new View();final ScrollView overflow=new ScrollView();
  final TextView bandText=new TextView(),title=new TextView(),hint=new TextView(),guidance=new TextView();final ProgressBar wheel=new ProgressBar();final ImageView symbol=new ImageView();final Button retry=new Button(),website=new Button();
  boolean actionLayoutKnown,actionsHorizontal,compactCover;final PageLoadingWait wait=new PageLoadingWait();
  boolean networkFirst,actionsLandscape;int actionsAvailable;float actionsFontScale;String actionsRetryLabel="",actionsWebsiteLabel="";
  boolean coverShown,hintBound;String lastTitle="",lastHint;
  LoadingUi(MainActivity a){this.a=a;cover.visibility=View.GONE;band.visibility=View.GONE;retry.text="重新加载";website.text="检查网络";retry.owner=a;website.owner=a;cover.paddingLeft=cover.paddingRight=28;cover.paddingTop=20;cover.paddingBottom=28;title.params.topMargin=14;title.params.bottomMargin=6;actions.params.topMargin=16;guidance.params.topMargin=24;for(View child:new View[]{emblem,title,hint,actions,guidance})content.addView(child,child.params);}
  /* PRODUCTION_METHODS */
  /* CURRENT_ACTIONS_ADAPTER */
  /* COMPACT_COVER_ADAPTER */
}
final class Metrics {
  static int text,description,visibility,alpha,animationCancel,animationStart,animationAlpha,layout,orientation,measures;
  static void reset(){text=description=visibility=alpha=animationCancel=animationStart=animationAlpha=layout=orientation=measures=0;}
  static int presentationWrites(){return text+description+visibility+alpha+animationCancel+animationStart+animationAlpha+layout+orientation;}
  static Map<String,Object> snapshot(){Map<String,Object> out=new LinkedHashMap<>();out.put("textAssignments",text);out.put("contentDescriptionAssignments",description);out.put("visibilityAssignments",visibility);out.put("alphaAssignments",alpha);out.put("animationCancels",animationCancel);out.put("animationStarts",animationStart);out.put("animationAlphaAssignments",animationAlpha);out.put("layoutAssignments",layout);out.put("orientationAssignments",orientation);out.put("presentationWrites",presentationWrites());return out;}
}
class View {
  static final int VISIBLE=0,GONE=8;int visibility=VISIBLE,width=900,paddingLeft,paddingRight,paddingTop,paddingBottom;float alpha=1;final Animator animator=new Animator(this);LinearLayout.LayoutParams params=new LinearLayout.LayoutParams();
  int getWidth(){return width;}int getPaddingLeft(){return paddingLeft;}int getPaddingRight(){return paddingRight;}
  void setPadding(int left,int top,int right,int bottom){Metrics.layout++;paddingLeft=left;paddingRight=right;paddingTop=top;paddingBottom=bottom;}void setBackground(Object drawable){Metrics.layout++;}
  void setVisibility(int value){Metrics.visibility++;visibility=value;}int getVisibility(){return visibility;}
  void setAlpha(float value){Metrics.alpha++;alpha=value;}float getAlpha(){return alpha;}
  Animator animate(){return animator;}
  Object getLayoutParams(){return params;}void setLayoutParams(LinearLayout.LayoutParams value){Metrics.layout++;params=value;}
}
class TextView extends View {
  void setTextColor(int color){Metrics.layout++;}
  String text="",description="";void setText(String value){Metrics.text++;text=value;}String getText(){return text;}
  void setContentDescription(String value){Metrics.description++;description=value;}String getContentDescription(){return description;}
}
class EditText extends TextView {}
final class Button extends TextView {MainActivity owner;MainActivity getContext(){return owner;}Paint getPaint(){return new Paint(owner);}int getCompoundPaddingLeft(){return paddingLeft;}int getCompoundPaddingRight(){return paddingRight;}}
final class Paint {final MainActivity owner;Paint(MainActivity owner){this.owner=owner;}float measureText(String text){Metrics.measures++;return text.length()*14*owner.resources.configuration.fontScale;}}
final class ProgressBar extends View {}
final class ImageView extends View {}
final class Color {static final int WHITE=-1,TRANSPARENT=0;}
final class Ui {static Object ripple(MainActivity owner,int color,int radius){return color;}}
final class LinearLayout extends View {
  final List<View> children=new ArrayList<>();int getChildCount(){return children.size();}void removeAllViews(){Metrics.layout++;children.clear();}void addView(View view,LayoutParams params){Metrics.layout++;view.params=params;children.add(view);}
  void removeView(View view){Metrics.layout++;children.remove(view);}void addView(View view,int at,LayoutParams params){Metrics.layout++;view.params=params;children.add(at,view);}
  static final int HORIZONTAL=0,VERTICAL=1;int orientation=VERTICAL;void setOrientation(int value){Metrics.orientation++;orientation=value;}
  static final class LayoutParams {LayoutParams(){}LayoutParams(int width,int height){this.width=width;this.height=height;}int width=-1,height=-2,topMargin,bottomMargin,leftMargin;float weight;}
}
final class ScrollView extends View {int scrollY;void scrollTo(int x,int y){Metrics.layout++;scrollY=y;}}
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
final class Resources {final android.content.res.Configuration configuration=new android.content.res.Configuration();final android.util.DisplayMetrics metrics=new android.util.DisplayMetrics();android.content.res.Configuration getConfiguration(){return configuration;}android.util.DisplayMetrics getDisplayMetrics(){return metrics;}}
final class ChatSession {
  final Browser web=new Browser();boolean navigationFailed,connecting=true,networkReady;String status="正在连接",pageError="",networkIssue="",connectionStage="";
}
final class Browser {boolean visible,resourceDeferred;int actions;boolean hasVisibleDocument(){return visible;}}
final class DesignUi {static final int BLUE=0xff2468f2;static int dp(MainActivity owner,int value){return owner.dp(value);}/* READABLE_METHOD *//* ACTION_WIDTH_METHOD */}
final class ResourcePressureController {/* DEFERRED_CONSTANT */}
