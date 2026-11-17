package local.pocketchat;

import android.graphics.Color;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.TextView;
import org.json.JSONObject;

/** Presents the Chromium route's own admission; never borrows a Gecko session. */
final class ChromiumNetworkUi {
  final BrowserActivity activity;final TextView row;
  private ReferenceUi.Modal dialog;private TextView details;
  private String explanation="";private int renderedColor;
  ChromiumNetworkUi(BrowserActivity activity){
    this.activity=activity;row=new TextView(activity){
      @Override protected void onMeasure(int widthSpec,int heightSpec){
        int capsuleWidth=activity.environmentTouch==null?0:activity.environmentTouch.getMeasuredWidth();
        int minimum=BrowserHeaderLayout.networkMinimumHeight(MeasureSpec.getSize(widthSpec),capsuleWidth,activity.dp(48),activity.dp(28));
        if(getMinimumHeight()!=minimum){setMinHeight(minimum);setMinimumHeight(minimum);}
        super.onMeasure(widthSpec,heightSpec);
      }
    };
    row.setTextSize(ReferenceUi.SECONDARY_SIZE);row.setTextColor(AppAppearance.text(ReferenceUi.MUTED));ReferenceUi.readable(row);
    row.setMinHeight(activity.dp(48));row.setMinimumHeight(activity.dp(48));row.setMaxLines(3);
    row.setPadding(activity.dp(6),activity.dp(1),activity.dp(6),activity.dp(1));
    row.setGravity(android.view.Gravity.CENTER_VERTICAL);row.setFocusable(true);row.setBackground(Ui.ripple(activity,Color.TRANSPARENT,8));
    row.setOnClickListener(view->show());row.setAccessibilityDelegate(new View.AccessibilityDelegate(){
      @Override public void onInitializeAccessibilityNodeInfo(View host,AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName(Button.class.getName());}
    });update();
  }
  void update(){
    if(activity.destroyed)return;
    ChromiumRuntime runtime=activity.runtime;ChromiumRuntime.Route route=runtime==null?null:runtime.route;
    boolean owned=runtime!=null&&!runtime.closed&&ChromiumRuntime.owner==runtime;
    boolean ticketCurrent=owned&&route!=null&&runtime.policy.current(route.ticket),evidenceCurrent=false;
    if(ticketCurrent)try{evidenceCurrent=route.evidenceCurrent();}catch(RuntimeException unavailable){}
    boolean admitted=ticketCurrent&&evidenceCurrent,degraded=false;
    String address="出口 IP 未核验",latency="延迟未测",status=admitted?"已连接":"未连接";
    String routeStatus=runtime==null?"浏览器网络尚未就绪":runtime.status();
    if(!admitted&&routeStatus.startsWith("正在"))status="连接中";
    if(route!=null&&(!owned||ticketCurrent&&!evidenceCurrent)){status="状态待核实";routeStatus="线路状态已变化，等待重新确认";}
    if(admitted&&route.receipt!=null){
      NativeNetwork network=runtime.network;
      if(runtime.internalCurrent(route.receipt)){
        long now=System.currentTimeMillis();String ip=network.exitIp;
        JSONObject stats=NetworkMetricsUi.displayStats(network,now);
        latency=NetworkMetricsUi.latency(stats,now)+(network.measuringLatency?"（测速中）":LatencyRefreshPolicy.countdown(network.latencyRemaining(now)));
        if(!ip.isEmpty())address=ip;
        degraded=network.connectionAdmission()==NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;
        if(degraded)status="核验待恢复";
        // A renewed or replaced route must not attach an earlier reading to this row.
        if(runtime.route!=route||!runtime.internalCurrent(route.receipt)){admitted=false;address="出口 IP 未核验";latency="延迟未测";status="状态待核实";routeStatus="线路状态已变化，等待重新确认";}
      }else{admitted=false;status="状态待核实";routeStatus="线路状态已变化，等待重新确认";}
    }
    String summary=address+" · "+latency+" · "+status;
    SpannableString text=new SpannableString("●  "+summary);
    int color=admitted?(degraded?ReferenceUi.ORANGE:ReferenceUi.GREEN):ReferenceUi.MUTED;
    text.setSpan(new ForegroundColorSpan(color),0,1,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    text.setSpan(new ForegroundColorSpan(color),text.length()-status.length(),text.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    if(renderedColor!=color||!TextUtils.equals(row.getText(),text)){renderedColor=color;row.setText(text);}
    String description="当前环境网络："+summary;if(!TextUtils.equals(row.getContentDescription(),description))row.setContentDescription(description);
    explanation=summary+"\n\n"+routeStatus+"\n\n这里只显示当前 Chromium 环境的线路状态。未取得此线路的 IP 或延迟测量时会明确标为未核验、未测。";
    if(details!=null&&!TextUtils.equals(details.getText(),explanation))details.setText(explanation);
  }
  void show(){
    if(activity.destroyed||activity.isFinishing()||dialog!=null&&dialog.isShowing())return;
    update();ReferenceUi.Modal opened=new ReferenceUi.Modal(activity,"网络情况").asSheet();dialog=opened;
    details=ReferenceUi.text(activity,explanation,14,ReferenceUi.TEXT,false);ReferenceUi.readable(details);opened.body.addView(details);
    ReferenceUi.menuAction(opened,"此环境的网络设置",()->{opened.dismiss();activity.openNetworkSettings();});
    opened.setOnDismissListener(ignored->{if(dialog==opened){dialog=null;details=null;}});opened.show();
  }
  void close(){if(dialog!=null)dialog.dismiss();dialog=null;details=null;}
}
