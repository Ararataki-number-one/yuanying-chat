package local.pocketchat;
import android.graphics.*;import android.view.*;import android.widget.*;

/** Only the native shell is styled; both existing web surfaces stay owned by MainActivity. */
final class DesignChrome {
  final MainActivity a;final TextView title,dot,chevron,stateWord;final LinearLayout modes,networkRow;
  DesignChrome(MainActivity a,LinearLayout root){
    this.a=a;a.toolbar=DesignUi.column(a);a.toolbar.setBackgroundColor(ReferenceUi.CHAT_BG);a.toolbar.setPadding(a.dp(10),a.dp(0),a.dp(10),a.dp(0));LinearLayout top=DesignUi.row(a);
    a.navigation=new Ui.IconButton(a,"hamburger","打开会话列表",false);
    top.addView(a.navigation,new LinearLayout.LayoutParams(a.dp(44),a.dp(44)));a.navigation.setOnClickListener(v->a.showDrawer());
    title=ReferenceUi.text(a,Profiles.display(a,Profiles.slot(a)),16,ReferenceUi.TEXT,true);ReferenceUi.single(title);title.setGravity(Gravity.CENTER_VERTICAL);title.setPadding(a.dp(3),0,a.dp(6),0);title.setBackground(Ui.ripple(a,Color.TRANSPARENT,9));title.setOnClickListener(v->ProfileUi.show(a));top.addView(title,new LinearLayout.LayoutParams(0,a.dp(44),1));
    modes=DesignUi.row(a);modes.setPadding(a.dp(2),a.dp(2),a.dp(2),a.dp(2));modes.setBackground(ReferenceUi.surface(a,ReferenceUi.BLUE_SOFT,10,Color.TRANSPARENT));a.nativeTab=a.modeTab("简洁","简洁聊天模式",()->a.showPage(false));a.webTab=a.modeTab("原网页","原网页模式",()->a.showPage(true));
    for(TextView mode:new TextView[]{a.nativeTab,a.webTab}){mode.setTextSize(12);mode.setSingleLine(true);mode.setPadding(a.dp(4),0,a.dp(4),0);modes.addView(mode,new LinearLayout.LayoutParams(a.dp(mode==a.nativeTab?50:60),a.dp(32)));}top.addView(modes);
    Button more=ReferenceUi.more(a,()->a.moreSheet());top.addView(more,new LinearLayout.LayoutParams(a.dp(42),a.dp(44)));a.toolbar.addView(top);
    networkRow=DesignUi.row(a);networkRow.setPadding(a.dp(4),0,a.dp(4),0);networkRow.setMinimumHeight(a.dp(28));networkRow.setBackground(Ui.ripple(a,Color.TRANSPARENT,8));dot=ReferenceUi.text(a,"●",11,ReferenceUi.MUTED,false);networkRow.addView(dot,new LinearLayout.LayoutParams(a.dp(16),-2));
    a.networkLine=ReferenceUi.text(a,"连接状态待确认",13,ReferenceUi.MUTED,false);ReferenceUi.single(a.networkLine);a.networkLine.setAutoSizeTextTypeUniformWithConfiguration(11,13,1,android.util.TypedValue.COMPLEX_UNIT_SP);networkRow.addView(a.networkLine,new LinearLayout.LayoutParams(0,a.dp(28),1));a.networkLine.setGravity(Gravity.CENTER_VERTICAL);stateWord=ReferenceUi.text(a,"未连接",13,ReferenceUi.MUTED,true);networkRow.addView(stateWord);chevron=ReferenceUi.text(a,"›",22,ReferenceUi.MUTED,false);chevron.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);networkRow.addView(chevron,new LinearLayout.LayoutParams(a.dp(20),a.dp(28)));
    View.OnClickListener open=v->a.hub.networkFor(Profiles.slot(a));networkRow.setOnClickListener(open);a.networkLine.setOnClickListener(open);networkRow.setFocusable(true);a.toolbar.addView(networkRow);root.addView(a.toolbar,new LinearLayout.LayoutParams(-1,-2));
  }
  void update(){title.setText(Profiles.display(a,Profiles.slot(a)));title.setContentDescription("当前环境："+title.getText()+"，点击切换环境");a.nativeTab.setBackground(Ui.ripple(a,a.pageMode?Color.TRANSPARENT:ReferenceUi.BLUE,9));a.webTab.setBackground(Ui.ripple(a,a.pageMode?ReferenceUi.BLUE:Color.TRANSPARENT,9));a.nativeTab.setTextColor(a.pageMode?0xff4d6384:Color.WHITE);a.webTab.setTextColor(a.pageMode?Color.WHITE:0xff4d6384);WindowNetworkState state=WindowNetworkState.current(a);a.networkLine.setText(state.mainline());a.networkLine.setTextColor(ReferenceUi.TEXT);dot.setTextColor(state.color());stateWord.setText(state.state.equals("正常")?"已连接":state.state);stateWord.setTextColor(state.color());networkRow.setContentDescription("当前环境网络："+state.strip()+"。点击进入网络页并定位当前窗口");}
}
