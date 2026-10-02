package local.pocketchat;

import android.content.*;
import android.net.Uri;
import android.view.*;
import android.widget.*;

/** One compact header keeps the environment and site visible around the real website. */
final class DesignChrome {
  final MainActivity a;final TextView title,badge,host;final LinearLayout address;final Button mode;
  DesignChrome(MainActivity a,LinearLayout root){
    this.a=a;a.toolbar=DesignUi.column(a);a.toolbar.setPadding(a.dp(8),a.dp(4),a.dp(8),a.dp(4));
    LinearLayout top=DesignUi.row(a);
    a.navigation=new Ui.IconButton(a,"menu","打开会话列表",false);top.addView(a.navigation,new LinearLayout.LayoutParams(a.dp(48),a.dp(48)));a.navigation.setOnClickListener(v->a.showDrawer());
    LinearLayout identity=DesignUi.column(a);identity.setPadding(a.dp(4),0,a.dp(6),0);
    title=DesignUi.text(a,Profiles.display(a,Profiles.slot(a)),15,DesignUi.TEXT);title.setSingleLine(true);title.setEllipsize(android.text.TextUtils.TruncateAt.END);identity.addView(title);
    address=DesignUi.row(a);host=DesignUi.text(a,"chatgpt.com",11,DesignUi.MUTED);host.setSingleLine(true);host.setEllipsize(android.text.TextUtils.TruncateAt.END);address.addView(host,new LinearLayout.LayoutParams(-1,-2));identity.addView(address);
    top.addView(identity,new LinearLayout.LayoutParams(0,-2,1));
    // Existing mode state stays owned by MainActivity; the visible selector opens on demand.
    a.nativeTab=a.modeTab("简洁模式","简洁聊天模式",()->a.showPage(false));a.webTab=a.modeTab("原网页模式","原网页模式",()->a.showPage(true));
    badge=DesignUi.badge(a,"默认",DesignUi.BLUE);
    mode=DesignUi.button(a,"网页 ▾",false,()->new android.app.AlertDialog.Builder(a).setTitle("显示方式")
      .setSingleChoiceItems(new String[]{"简洁聊天","原网页"},a.pageMode?1:0,(d,n)->{a.showPage(n==1);d.dismiss();}).setNegativeButton("取消",null).show());
    mode.setTextSize(12);mode.setPadding(a.dp(4),0,a.dp(4),0);top.addView(mode,new LinearLayout.LayoutParams(a.dp(64),a.dp(48)));
    Ui.IconButton fresh=new Ui.IconButton(a,"plus","新对话",true);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(a.dp(48),a.dp(48));p.leftMargin=a.dp(4);top.addView(fresh,p);fresh.setOnClickListener(v->a.newChat());
    Ui.IconButton more=new Ui.IconButton(a,"more","更多选项",false);top.addView(more,new LinearLayout.LayoutParams(a.dp(48),a.dp(48)));more.setOnClickListener(v->a.moreSheet());a.toolbar.addView(top);
    a.networkLine=DesignUi.text(a,"正在连接…",12,DesignUi.MUTED);a.networkLine.setSingleLine(true);a.networkLine.setEllipsize(android.text.TextUtils.TruncateAt.END);
    a.networkLine.setPadding(a.dp(8),a.dp(8),a.dp(8),a.dp(8));a.networkLine.setGravity(Gravity.CENTER_VERTICAL);a.networkLine.setMinHeight(a.dp(48));
    a.networkLine.setOnClickListener(v->{if(a.session.audit.hasChanges())EnvironmentAuditUi.show(a);else NetworkStatusUi.show(a);});a.toolbar.addView(a.networkLine,new LinearLayout.LayoutParams(-1,-2));
    root.addView(a.toolbar,new LinearLayout.LayoutParams(-1,-2));
  }
  void update(){
    title.setText(Profiles.display(a,Profiles.slot(a)));badge.setText(Profiles.slot(a)==AppSettings.defaultSlot(a)?"默认":"环境 "+(Profiles.slot(a)+1));
    mode.setText(a.pageMode?"网页 ▾":"简洁 ▾");mode.setContentDescription("显示方式："+(a.pageMode?"原网页":"简洁聊天"));address.setVisibility(a.pageMode?View.VISIBLE:View.GONE);
    try{String actual=Uri.parse(a.remote.getUrl()).getHost();host.setText(actual==null?"chatgpt.com":actual);}catch(Exception ignored){host.setText("chatgpt.com");}
    boolean changed=a.session.audit.hasChanges(),show=changed||a.session.offline||!a.session.networkReady;
    a.networkLine.setVisibility(show?View.VISIBLE:View.GONE);
    a.networkLine.setText(changed?"环境信息有变化 · 查看":a.session.offline?"网络已断开 · 检查连接":a.session.connecting?"正在连接…":"还未连接 · 检查连接");
    a.networkLine.setTextColor(a.session.offline||changed?DesignUi.RED:DesignUi.MUTED);
  }
}
