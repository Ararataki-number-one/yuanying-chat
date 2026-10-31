package local.pocketchat;

import android.view.*;
import android.widget.*;

/** The native return control is independent of IP123 and remains available offline. */
final class ExitIpPageUi implements GeckoWebView.ExitIpPageListener {
  final MainActivity a;final ChatSession owner;final GeckoWebView web;LinearLayout header;TextView status;
  ExitIpPageUi(MainActivity a){this.a=a;owner=a.session;web=a.remote;}
  static void open(MainActivity a){
    if(!NetworkStatusUi.current(a,a.session))return;
    if(a.hub==null||a.hub.page!=AppHub.CHAT){DesignUi.message(a,"IP 查询","请先返回当前环境的聊天页，再打开 IP 查询。");return;}
    if(a.remote.hasExitIpPage())return;
    ExitIpPageUi ui=new ExitIpPageUi(a);String issue=a.remote.openExitIpPage(ui);
    if(!issue.isEmpty()){DesignUi.message(a,"IP 查询",issue);return;}ui.attach();
  }
  void attach(){
    header=DesignUi.row(a);header.setBackgroundColor(ReferenceUi.CHAT_BG);header.setPadding(a.dp(12),0,a.dp(8),0);
    LinearLayout text=DesignUi.column(a);text.addView(ReferenceUi.text(a,"IP 查询 · 当前环境线路",14,ReferenceUi.TEXT,true));status=ReferenceUi.text(a,"正在打开 ip123.in…",11,ReferenceUi.MUTED,false);status.setMaxLines(1);text.addView(status);header.addView(text,new LinearLayout.LayoutParams(0,-2,1));
    header.addView(ReferenceUi.small(a,"返回聊天",true,()->web.closeExitIpPage()),new LinearLayout.LayoutParams(-2,a.dp(52)));
    web.addView(header,new FrameLayout.LayoutParams(-1,a.dp(52),Gravity.TOP));web.exitIpTopInset=a.dp(52);web.requestLayout();
    if(a.designChrome!=null)a.designChrome.cancelWebGesture();a.hideKeyboard();
  }
  @Override public void changed(String message){if(status!=null&&NetworkStatusUi.current(a,owner)&&web.hasExitIpPage())status.setText(message);}
  @Override public void closed(){if(header!=null&&header.getParent()==web)web.removeView(header);header=null;web.exitIpTopInset=0;web.requestLayout();}
  static boolean back(MainActivity a){return a.remote!=null&&a.remote.closeExitIpPage();}
  static void close(MainActivity a){if(a.remote!=null)a.remote.closeExitIpPage();}
}
