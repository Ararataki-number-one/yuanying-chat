package local.pocketchat;

import android.graphics.*;
import android.os.SystemClock;
import android.text.TextUtils;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Only the native shell is styled; both existing web surfaces stay owned by MainActivity. */
final class DesignChrome {
  final MainActivity a;
  final TextView title,dot,stateWord,latencyWord;
  final LinearLayout top,modes,networkRow;
  final Button more;
  private final View[] actions;
  private ChromeTouchDelegate touchTargets;
  private static final ExecutorService metadataReader=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"ChromeMetadata");t.setPriority(Thread.MIN_PRIORITY);return t;});
  private final Runnable render=this::renderLatest;
  private boolean queued,metadataPending,modeKnown,lastPageMode;
  private long metadataAt;
  private String profileName;

  DesignChrome(MainActivity a,LinearLayout root){
    this.a=a;
    a.toolbar=DesignUi.column(a);
    a.toolbar.setBackgroundColor(ReferenceUi.CHAT_BG);
    a.toolbar.setPadding(a.dp(10),0,a.dp(10),0);
    top=DesignUi.row(a);
    a.navigation=new Ui.IconButton(a,"hamburger","打开会话列表",false);
    a.navigation.setOnClickListener(v->a.showDrawer());
    title=ReferenceUi.text(a,Profiles.display(a,Profiles.slot(a)),16,ReferenceUi.TEXT,true);
    profileName=title.getText().toString();
    ReferenceUi.single(title);
    title.setGravity(Gravity.CENTER_VERTICAL);
    title.setPadding(a.dp(3),0,a.dp(6),0);
    title.setBackground(Ui.ripple(a,Color.TRANSPARENT,9));
    title.setOnClickListener(v->ProfileUi.show(a));

    modes=DesignUi.row(a);
    modes.setPadding(a.dp(2),a.dp(2),a.dp(2),a.dp(2));
    modes.setBackground(ReferenceUi.surface(a,ReferenceUi.BLUE_SOFT,9,Color.TRANSPARENT));
    a.nativeTab=a.modeTab("简洁","简洁聊天模式",()->a.showPage(false));
    a.webTab=a.modeTab("原网页","原网页模式",()->a.showPage(true));
    int modeHeight=a.dp(30);
    for(TextView mode:new TextView[]{a.nativeTab,a.webTab}){
      mode.setTextSize(12);
      mode.setSingleLine(true);
      mode.setPadding(a.dp(4),0,a.dp(4),0);
      modeHeight=Math.max(modeHeight,textHeight(mode)+a.dp(4));
    }
    for(TextView mode:new TextView[]{a.nativeTab,a.webTab}){
      int width=Math.max(a.dp(mode==a.nativeTab?50:60),(int)Math.ceil(mode.getPaint().measureText(mode.getText().toString()))+mode.getPaddingLeft()+mode.getPaddingRight());
      modes.addView(mode,new LinearLayout.LayoutParams(width,modeHeight));
    }
    more=ReferenceUi.more(a,()->a.moreSheet());
    // The shared button style reserves 48 dp; this compact shell expands touch separately.
    more.setMinHeight(0);
    more.setMinimumHeight(0);
    more.setPadding(a.dp(4),0,a.dp(4),0);
    int topHeight=Math.max(a.dp(40),Math.max(textHeight(title)+a.dp(4),modeHeight+a.dp(4)));
    top.addView(a.navigation,new LinearLayout.LayoutParams(a.dp(44),topHeight));
    top.addView(title,new LinearLayout.LayoutParams(0,topHeight,1));
    top.addView(modes);
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
    int lineHeight=a.dp(18);
    for(TextView text:new TextView[]{dot,a.networkLine,latencyWord,stateWord})lineHeight=Math.max(lineHeight,textHeight(text)+a.dp(2));
    networkRow.addView(dot,new LinearLayout.LayoutParams(a.dp(12),lineHeight));
    networkRow.addView(a.networkLine,new LinearLayout.LayoutParams(0,lineHeight,1));
    networkRow.addView(latencyWord,new LinearLayout.LayoutParams(-2,lineHeight));
    networkRow.addView(stateWord,new LinearLayout.LayoutParams(-2,lineHeight));
    a.toolbar.addView(networkRow,new LinearLayout.LayoutParams(-1,lineHeight));
    root.addView(a.toolbar,new LinearLayout.LayoutParams(-1,-2));
    actions=new View[]{a.navigation,title,a.nativeTab,a.webTab,more};
    a.toolbar.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->layoutTouchTargets());
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
    description(title,"当前环境："+profileName+"，点击切换环境");
    if(!modeKnown||lastPageMode!=a.pageMode){
      modeKnown=true;lastPageMode=a.pageMode;
      a.nativeTab.setBackground(Ui.ripple(a,a.pageMode?Color.TRANSPARENT:ReferenceUi.BLUE,8));
      a.webTab.setBackground(Ui.ripple(a,a.pageMode?ReferenceUi.BLUE:Color.TRANSPARENT,8));
      UiPerfStats.backgroundChange();UiPerfStats.backgroundChange();
      color(a.nativeTab,a.pageMode?0xff4d6384:Color.WHITE);
      color(a.webTab,a.pageMode?Color.WHITE:0xff4d6384);
    }
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
    @Override public AccessibilityNodeInfo.TouchDelegateInfo getTouchDelegateInfo(){
      Map<Region,View> map=new LinkedHashMap<>();
      for(int i=0;i<targets.length;i++)map.put(new Region(bounds[i]),targets[i]);
      return new AccessibilityNodeInfo.TouchDelegateInfo(map);
    }
  }
}
