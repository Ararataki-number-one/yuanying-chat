package local.pocketchat;

import android.annotation.TargetApi;
import android.graphics.*;
import android.os.SystemClock;
import android.text.TextUtils;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityManager;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Compact environment controls outside the untouched official ChatGPT document. */
final class DesignChrome {
  final MainActivity a;
  final TextView title,dot,stateWord,latencyWord,compactTitle;
  final FrameLayout compact;
  final LinearLayout top,networkRow;
  final LinearLayout modes=null; // Historical tests may inspect the retired control.
  final Button more;
  private final View[] actions;
  private ChromeTouchDelegate touchTargets;
  private static final ExecutorService metadataReader=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"ChromeMetadata");t.setPriority(Thread.MIN_PRIORITY);return t;});
  private final Runnable render=this::renderLatest;
  private boolean queued,metadataPending;
  private long metadataAt;
  private String profileName;
  private boolean collapsed=true;
  private final ChromeCollapseGesture swipe;
  private Runnable pendingSwipe;

  DesignChrome(MainActivity a,LinearLayout root){
    this.a=a;
    swipe=new ChromeCollapseGesture(a.dp(40),ViewConfiguration.get(a).getScaledTouchSlop(),ViewConfiguration.getLongPressTimeout());
    a.toolbar=new CollapsingToolbar();a.toolbar.setOrientation(LinearLayout.VERTICAL);
    a.toolbar.setVisibility(View.VISIBLE);
    a.toolbar.setBackgroundColor(ReferenceUi.CHAT_BG);
    a.toolbar.setPadding(a.dp(10),0,a.dp(10),0);
    compact=new FrameLayout(a);
    compactTitle=ReferenceUi.text(a,Profiles.display(a,Profiles.slot(a)),12,ReferenceUi.TEXT,true);
    ReferenceUi.single(compactTitle);
    compactTitle.setMaxWidth(a.dp(240));
    compactTitle.setGravity(Gravity.CENTER);
    compactTitle.setPadding(a.dp(14),0,a.dp(12),0);
    Ui.Icon disclosure=new Ui.Icon("chevron",ReferenceUi.MUTED);disclosure.setBounds(0,0,a.dp(12),a.dp(12));
    compactTitle.setCompoundDrawables(null,null,disclosure,null);compactTitle.setCompoundDrawablePadding(a.dp(7));
    compactTitle.setBackground(DesignUi.glass(a,14));
    compactTitle.setDuplicateParentStateEnabled(true);
    compactTitle.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    FrameLayout.LayoutParams compactLabel=new FrameLayout.LayoutParams(-2,-1,Gravity.CENTER);
    compactLabel.leftMargin=a.dp(16);compactLabel.rightMargin=a.dp(16);
    compact.addView(compactTitle,compactLabel);
    compact.setFocusable(true);
    compact.setDefaultFocusHighlightEnabled(false);
    compact.setContentDescription("当前环境："+compactTitle.getText()+"，点击展开环境工具栏");
    compact.setOnClickListener(v->reveal());
    compact.setAccessibilityDelegate(new View.AccessibilityDelegate(){
      @Override public void onInitializeAccessibilityNodeInfo(View host,AccessibilityNodeInfo info){
        super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName(Button.class.getName());
      }
    });
    AccessibilityManager accessibility=(AccessibilityManager)a.getSystemService(android.content.Context.ACCESSIBILITY_SERVICE);
    int compactHeight=Math.max(a.dp(accessibility!=null&&accessibility.isTouchExplorationEnabled()?48:28),textHeight(compactTitle)+a.dp(8));
    a.toolbar.addView(compact,new LinearLayout.LayoutParams(-1,compactHeight));
    top=DesignUi.row(a);
    a.navigation=new Ui.IconButton(a,"hamburger","管理环境",false);
    a.navigation.setOnClickListener(v->a.showDrawer());
    title=ReferenceUi.text(a,compactTitle.getText().toString(),16,ReferenceUi.TEXT,true);
    profileName=title.getText().toString();
    ReferenceUi.single(title);
    title.setGravity(Gravity.CENTER);
    title.setPadding(a.dp(12),0,a.dp(12),0);
    title.setBackground(DesignUi.glass(a,20));
    title.setOnClickListener(v->a.chooseEnvironment());

    more=ReferenceUi.more(a,()->a.moreSheet());
    // The shared button style reserves 48 dp; this compact shell expands touch separately.
    more.setMinHeight(0);
    more.setMinimumHeight(0);
    more.setPadding(a.dp(4),0,a.dp(4),0);
    int topHeight=Math.max(a.dp(40),textHeight(title)+a.dp(4));
    top.addView(a.navigation,new LinearLayout.LayoutParams(a.dp(44),topHeight));
    top.addView(title,new LinearLayout.LayoutParams(0,topHeight,1));
    top.addView(more,new LinearLayout.LayoutParams(a.dp(42),topHeight));
    a.toolbar.addView(top,new LinearLayout.LayoutParams(-1,topHeight));

    networkRow=DesignUi.row(a);
    networkRow.setPadding(a.dp(4),0,a.dp(4),0);
    // This is a read-only status line. Network navigation remains in the bottom bar.
    networkRow.setClickable(false);
    networkRow.setFocusable(false);
    dot=ReferenceUi.text(a,"●",9,ReferenceUi.MUTED,false);
    dot.setTextSize(android.util.TypedValue.COMPLEX_UNIT_DIP,9);
    a.networkLine=ReferenceUi.text(a,"连接状态待确认",11,ReferenceUi.MUTED,false);
    latencyWord=ReferenceUi.text(a,"延迟未测",11,ReferenceUi.MUTED,false);
    stateWord=ReferenceUi.text(a,"未连接",11,ReferenceUi.MUTED,true);
    ReferenceUi.single(a.networkLine);
    ReferenceUi.single(latencyWord);
    ReferenceUi.single(stateWord);
    a.networkLine.setGravity(Gravity.CENTER_VERTICAL);
    latencyWord.setGravity(Gravity.CENTER_VERTICAL);
    latencyWord.setPadding(a.dp(6),0,a.dp(6),0);
    stateWord.setGravity(Gravity.CENTER_VERTICAL);
    boolean largeFont=a.getResources().getConfiguration().fontScale>=1.4f;
    int lineHeight=a.dp(18);
    for(TextView text:new TextView[]{dot,a.networkLine,latencyWord,stateWord})lineHeight=Math.max(lineHeight,textHeight(text)+a.dp(largeFont?0:2));
    if(largeFont){
      networkRow.setOrientation(LinearLayout.VERTICAL);
      LinearLayout address=DesignUi.row(a),metrics=DesignUi.row(a);
      address.addView(dot,new LinearLayout.LayoutParams(a.dp(12),lineHeight));
      address.addView(a.networkLine,new LinearLayout.LayoutParams(0,lineHeight,1));
      metrics.addView(new View(a),new LinearLayout.LayoutParams(0,1,1));
      metrics.addView(latencyWord,new LinearLayout.LayoutParams(-2,lineHeight));
      metrics.addView(stateWord,new LinearLayout.LayoutParams(-2,lineHeight));
      networkRow.addView(address,new LinearLayout.LayoutParams(-1,lineHeight));networkRow.addView(metrics,new LinearLayout.LayoutParams(-1,lineHeight));
    }else{
      networkRow.addView(dot,new LinearLayout.LayoutParams(a.dp(12),lineHeight));
      networkRow.addView(a.networkLine,new LinearLayout.LayoutParams(0,lineHeight,1));
      networkRow.addView(latencyWord,new LinearLayout.LayoutParams(-2,lineHeight));
      networkRow.addView(stateWord,new LinearLayout.LayoutParams(-2,lineHeight));
    }
    a.toolbar.addView(networkRow,new LinearLayout.LayoutParams(-1,-2));
    top.setVisibility(View.GONE);networkRow.setVisibility(View.VISIBLE);
    root.addView(a.toolbar,new LinearLayout.LayoutParams(-1,-2));
    actions=new View[]{a.navigation,title,more};
    a.toolbar.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->layoutTouchTargets());
    a.toolbar.post(this::layoutTouchTargets);
  }

  boolean expanded(){return !collapsed;}

  /** Explicit native navigation offers the environment controls again. */
  void reveal(){
    cancelWebGesture();setCollapsed(false);
    if((a.hub==null||a.hub.page==AppHub.CHAT)&&a.toolbar.getVisibility()!=View.VISIBLE)a.toolbar.setVisibility(View.VISIBLE);
  }

  void cancelWebGesture(){
    swipe.cancel();if(pendingSwipe!=null){a.handler.removeCallbacks(pendingSwipe);pendingSwipe=null;}
  }

  private boolean gestureAllowed(boolean reading){
    if(a.destroyed||!a.active||a.keyboardVisible||a.hub==null||a.hub.page!=AppHub.CHAT)return false;
    if(reading){
      if(a.remote==null||!a.remote.hasVisibleDocument())return false;
      String url=a.remote.getUrl();if(!MainActivity.chatUrl(url)||LoginPagePolicy.login(url))return false;
    }
    AccessibilityManager accessibility=(AccessibilityManager)a.getSystemService(android.content.Context.ACCESSIBILITY_SERVICE);
    return accessibility==null||!accessibility.isTouchExplorationEnabled();
  }

  /** Observe only input already admitted by the existing browser/security listeners. */
  void webTouch(MotionEvent event){
    int result=gestureEvent(event,true);if(result==ChromeCollapseGesture.HIDE)scheduleSwipe(result,true);
  }

  private int gestureEvent(MotionEvent event,boolean reading){
    int action=event.getActionMasked();
    if(action==MotionEvent.ACTION_DOWN){
      cancelWebGesture();swipe.begin(event.getX(),event.getY(),event.getEventTime(),gestureAllowed(reading));return ChromeCollapseGesture.NONE;
    }
    if(!gestureAllowed(reading)||action==MotionEvent.ACTION_CANCEL||event.getPointerCount()!=1||action==MotionEvent.ACTION_POINTER_DOWN||action==MotionEvent.ACTION_POINTER_UP){cancelWebGesture();return ChromeCollapseGesture.NONE;}
    if(action==MotionEvent.ACTION_MOVE){swipe.move(event.getX(),event.getY(),event.getPointerCount(),event.getEventTime());return ChromeCollapseGesture.NONE;}
    return action==MotionEvent.ACTION_UP?swipe.finish(event.getX(),event.getY(),event.getEventTime()):ChromeCollapseGesture.NONE;
  }

  private void scheduleSwipe(int result,boolean reading){
    // Resize once after Android/Gecko have received UP, never beneath a live finger.
    pendingSwipe=()->{pendingSwipe=null;if(gestureAllowed(reading))setCollapsed(result==ChromeCollapseGesture.HIDE);};
    a.handler.post(pendingSwipe);
  }

  /** A deliberate swipe on the header cancels its button click; ordinary taps pass through. */
  private final class CollapsingToolbar extends LinearLayout {
    boolean sequence;
    CollapsingToolbar(){super(a);}
    @Override public boolean dispatchTouchEvent(MotionEvent event){
      int action=event.getActionMasked();if(action==MotionEvent.ACTION_DOWN)sequence=gestureAllowed(false);
      boolean owned=sequence;int result=gestureEvent(event,false);boolean handled;
      if(result==ChromeCollapseGesture.HIDE){
        MotionEvent cancel=MotionEvent.obtain(event);cancel.setAction(MotionEvent.ACTION_CANCEL);
        handled=super.dispatchTouchEvent(cancel);cancel.recycle();scheduleSwipe(result,false);
      }else handled=super.dispatchTouchEvent(event);
      if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL)sequence=false;
      return handled||owned;
    }
  }

  private void setCollapsed(boolean value){
    if(collapsed==value)return;collapsed=value;
    // Never leave hidden expanded controls' touch delegates over the compact label.
    touchTargets=null;a.toolbar.setTouchDelegate(null);
    compact.setVisibility(value?View.VISIBLE:View.GONE);
    top.setVisibility(value?View.GONE:View.VISIBLE);
    View visible=value?compact:top;
    visible.animate().cancel();
    if(android.animation.ValueAnimator.areAnimatorsEnabled()){visible.setAlpha(.65f);visible.animate().alpha(1f).setDuration(140).start();}else visible.setAlpha(1f);
    networkRow.setVisibility(View.VISIBLE);
    if(a.hub==null||a.hub.page==AppHub.CHAT)a.toolbar.setVisibility(View.VISIBLE);
    a.toolbar.post(this::layoutTouchTargets);
  }

  private static int textHeight(TextView text){
    Paint.FontMetrics metrics=text.getPaint().getFontMetrics();
    return (int)Math.ceil(metrics.bottom-metrics.top);
  }

  void update(){
    if(queued||a.destroyed)return;queued=true;a.handler.post(render);
  }

  private void renderLatest(){
    queued=false;if(a.destroyed)return;UiPerfStats.chromeUpdate();refreshMetadata();
    text(title,profileName);
    text(compactTitle,profileName);
    description(compact,"当前环境："+profileName+"，点击展开环境工具栏");
    description(title,"当前环境："+profileName+"，点击切换环境");
    NativeNetwork network=NativeNetwork.get(a);
    JSONObject config=network.settings==null?new JSONObject():network.settings;
    // Only slot/name are needed for this strip. Catalog I/O is asynchronous;
    // timestamps and latency continue to come from the current protected route.
    showNetwork(new WindowNetworkState(a,J.obj("slot",Profiles.slot(a),"name",profileName),config,WindowNetworkState.live(a.session,network),true,System.currentTimeMillis()));
  }

  private void refreshMetadata(){
    long now=SystemClock.elapsedRealtime();if(metadataPending||now-metadataAt<2000)return;
    metadataPending=true;metadataAt=now;
    metadataReader.execute(()->{
      String next=profileName;try{next=Profiles.display(a,Profiles.slot(a));DesignUi.Stars.refresh(a);}catch(Exception ignored){}
      final String value=next;a.handler.post(()->{metadataPending=false;if(!a.destroyed&&!value.equals(profileName)){profileName=value;update();}});
    });
  }

  private static void text(TextView view,String value){if(!TextUtils.equals(view.getText(),value)){view.setText(value);UiPerfStats.textChange();}}
  private static void color(TextView view,int color){if(view.getCurrentTextColor()!=color)view.setTextColor(color);}
  private static void description(View view,String value){if(!TextUtils.equals(view.getContentDescription(),value))view.setContentDescription(value);}

  void showNetwork(WindowNetworkState state){
    String address=(state.region.isEmpty()?"地区未标注":state.region)+" · "+(state.ip.isEmpty()?"IP 未核验":state.connected?state.ip:"上次 "+state.ip);
    text(a.networkLine,address);
    color(a.networkLine,ReferenceUi.TEXT);
    color(dot,state.color());
    text(latencyWord,state.latency);
    text(stateWord,state.state.equals("正常")?"已连接":state.state);
    color(stateWord,state.color());
    description(networkRow,"当前环境网络："+state.strip());
  }

  private void layoutTouchTargets(){
    if(collapsed){touchTargets=null;a.toolbar.setTouchDelegate(null);return;}
    if(a.toolbar.getWidth()<=0||networkRow.getHeight()<=0)return;
    Rect[] visible=new Rect[actions.length],expanded=new Rect[actions.length];
    int[] toolbarAt=new int[2],actionAt=new int[2];
    a.toolbar.getLocationOnScreen(toolbarAt);
    for(int i=0;i<actions.length;i++){
      // Touch targets follow view frames, not TextView's internally scrolled text.
      actions[i].getLocationOnScreen(actionAt);
      int left=actionAt[0]-toolbarAt[0],top=actionAt[1]-toolbarAt[1];
      visible[i]=new Rect(left,top,left+actions[i].getWidth(),top+actions[i].getHeight());
    }
    int touchBottom=Math.min(a.toolbar.getHeight(),networkRow.getTop()+networkRow.getHeight()/2);
    for(int i=0;i<actions.length;i++){
      Rect bounds=visible[i];
      int left=i==0?0:(visible[i-1].right+bounds.left)/2;
      int right=i==actions.length-1?a.toolbar.getWidth():(bounds.right+visible[i+1].left)/2;
      int width=Math.min(right-left,Math.max(a.dp(48),bounds.width()));
      int height=Math.min(touchBottom,Math.max(a.dp(48),bounds.height()));
      int x=Math.max(left,Math.min(bounds.centerX()-width/2,right-width));
      int y=Math.max(0,Math.min(bounds.centerY()-height/2,touchBottom-height));
      expanded[i]=new Rect(x,y,x+width,y+height);
    }
    touchTargets=new ChromeTouchDelegate(actions,expanded);
    a.toolbar.setTouchDelegate(touchTargets);
  }

  /** Bounds in toolbar coordinates; the same regions are exposed to accessibility services. */
  Rect touchBounds(View view){
    if(touchTargets!=null)for(int i=0;i<actions.length;i++)if(actions[i]==view)return new Rect(touchTargets.bounds[i]);
    return new Rect();
  }

  private static final class ChromeTouchDelegate extends TouchDelegate {
    final Rect[] bounds;
    final TouchDelegate[] delegates;
    final View[] targets;
    TouchDelegate active;
    ChromeTouchDelegate(View[] targets,Rect[] bounds){
      super(new Rect(),targets[0]);
      this.targets=targets;this.bounds=bounds;delegates=new TouchDelegate[targets.length];
      for(int i=0;i<targets.length;i++)delegates[i]=new TouchDelegate(bounds[i],targets[i]);
    }
    @Override public boolean onTouchEvent(MotionEvent event){
      int action=event.getActionMasked();
      if(action==MotionEvent.ACTION_DOWN){
        active=null;
        for(int i=0;i<bounds.length;i++)if(bounds[i].contains((int)event.getX(),(int)event.getY())){active=delegates[i];break;}
      }
      boolean handled=active!=null&&active.onTouchEvent(event);
      if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL)active=null;
      return handled;
    }
    @TargetApi(29)
    @Override public AccessibilityNodeInfo.TouchDelegateInfo getTouchDelegateInfo(){
      Map<Region,View> map=new LinkedHashMap<>();
      for(int i=0;i<targets.length;i++)map.put(new Region(bounds[i]),targets[i]);
      return new AccessibilityNodeInfo.TouchDelegateInfo(map);
    }
  }
}
