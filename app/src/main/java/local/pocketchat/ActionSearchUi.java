package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.*;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.util.*;

/** A shared command surface for both account-free workspaces and the live chat. */
final class ActionSearchUi {
  static final String RECENTS="uxActionRecents";
  static final class Command {
    final ActionSearchPolicy.Item item;final Runnable run;
    Command(String id,String label,String detail,String aliases,Runnable run){item=new ActionSearchPolicy.Item(id,label,detail,aliases);this.run=run;}
  }
  static void add(List<Command> commands,String id,String label,String detail,String aliases,Runnable run){commands.add(new Command(id,label,detail,aliases,run));}
  private static String glyphFor(String id){
    if(id==null)return "info";
    switch(id){
      case "chat":return "browser";
      case "switch":case "environments":return "window";
      case "drafts":return "file";
      case "history":case "focus":return "book";
      case "connection":case "network":case "ip":return "globe";
      case "edit":return "new";
      case "permissions":return "shield";
      case "zoom":return "search";
      case "reload":return "refresh";
      case "downloads":case "updates":return "download";
      case "settings":return "settings";
      case "backup":return "backup";
      case "feedback":return "feedback";
      default:return "info";
    }
  }
  private static LinearLayout commandRow(Activity a,ActionSearchPolicy.Item item,Runnable run){
    LinearLayout row=DesignUi.row(a);row.setGravity(Gravity.CENTER_VERTICAL);
    row.setMinimumHeight(DesignUi.dp(a,58));
    row.setPadding(DesignUi.dp(a,16),DesignUi.dp(a,11),DesignUi.dp(a,14),DesignUi.dp(a,11));
    row.setBackground(new RippleDrawable(ColorStateList.valueOf(ReferenceUi.tone(0x140067d8,0x2682b3ff)),new ColorDrawable(Color.TRANSPARENT),new ColorDrawable(Color.WHITE)));
    ImageView icon=new ImageView(a);icon.setImageDrawable(new ReferenceUi.IconTileDrawable(a,glyphFor(item.id),30,false,false));
    icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(DesignUi.dp(a,30),DesignUi.dp(a,30));ip.setMarginEnd(DesignUi.dp(a,12));
    row.addView(icon,ip);
    LinearLayout copy=DesignUi.column(a);
    TextView title=ReferenceUi.crisp(ReferenceUi.workspaceText(a,item.label,15,ReferenceUi.inkPrimary(),true));
    title.setTypeface(ReferenceUi.TYPE_MEDIUM);
    copy.addView(title);
    if(item.detail!=null&&!item.detail.isEmpty()){
      TextView sub=ReferenceUi.prose(ReferenceUi.workspaceText(a,item.detail,ReferenceUi.SECONDARY_SIZE,ReferenceUi.secondaryInk(),false));
      sub.setPadding(0,DesignUi.dp(a,3),0,0);copy.addView(sub);
    }
    row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    ImageView arrow=new ImageView(a);arrow.setImageDrawable(new Ui.Icon("chevron-right",ReferenceUi.chevronInk()));
    arrow.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams ap=new LinearLayout.LayoutParams(DesignUi.dp(a,14),DesignUi.dp(a,14));ap.setMarginStart(DesignUi.dp(a,8));
    row.addView(arrow,ap);
    row.setClickable(true);row.setFocusable(true);
    row.setContentDescription(item.label+(item.detail==null||item.detail.isEmpty()?"":"，"+item.detail));
    row.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    return row;
  }
  static List<Command> commands(Activity a){
    List<Command> out=new ArrayList<>();
    if(a instanceof MainActivity){MainActivity m=(MainActivity)a;ChatSession owner=m.session;
      if(owner!=null&&m.hub!=null){
        java.util.function.Consumer<Runnable> current=run->{if(NetworkStatusUi.current(m,owner)&&ProfileCatalog.get(m).available(Profiles.slot(m)))run.run();};
        add(out,"chat","返回浏览器","继续当前网页与输入","浏览器 网页 聊天 返回 继续 browser chat",()->current.accept(()->m.hub.select(AppHub.CHAT)));
        add(out,"switch","快速切换环境","切换浏览器，保留原网页和任务","账号 窗口 切换 浏览器 switch browser",()->EnvironmentSwitcherUi.show(a));
        add(out,"drafts","草稿救援","查找暂存输入或保存当前草稿","草稿 复制 恢复 输入 draft",()->current.accept(()->LocalDraftsUi.show(m)));
        add(out,"history","离线会话检索","搜索本机已经保存的会话内容","历史 记录 搜索 阅读 history offline",()->current.accept(()->LocalHistoryUi.show(m)));
        add(out,"focus",m.focusReading?"退出专注阅读":"进入专注阅读","收起应用工具栏与导航，扩大网页阅读空间","全屏 阅读 沉浸 focus fullscreen",()->current.accept(()->m.setFocusReading(!m.focusReading)));
        add(out,"connection","查看连接与回复状态","检查当前环境，保留原网页","网络 状态 故障 回复 等待 connection",()->current.accept(m::showStatusDetails));
        add(out,"network","当前环境网络","打开当前环境的线路管理","线路 代理 订阅 节点 network proxy",()->current.accept(()->m.hub.networkFor(Profiles.slot(m))));
        add(out,"ip","查询当前环境 IP","查看实际出口信息","出口 地址 地区 ip",()->current.accept(()->ExitIpPageUi.open(m)));
        add(out,"edit","编辑当前环境","名称、分组、浏览器与偏好","修改 设置 环境 edit",()->current.accept(()->EnvironmentEditorUi.show(m)));
        add(out,"permissions","站点权限","管理当前环境的网站权限","相机 麦克风 摄像 位置 permission",()->current.accept(()->SitePermissionsUi.show(m)));
        if(owner.privacy.desktop&&BrowserReadingPolicy.chat(m.remote.getUrl()))add(out,"zoom","网页缩放","调整电脑版网页阅读大小","字体 大小 放大 缩小 zoom",()->current.accept(()->BrowserReadingUi.show(m)));
        add(out,"reload","重新加载网页","先核对回复、附件和未发送的输入","刷新 重试 恢复 reload refresh",()->current.accept(m::requestReload));
      }
    }
    add(out,"environments","管理全部环境","切换环境、管理配置和独立账号","账号 窗口 工作台 environment",()->a.startActivity(new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
    add(out,"downloads","下载中心","搜索文件、筛选环境和收集分享","文件 附件 保存 下载 download file",()->{if(a instanceof MainActivity&&((MainActivity)a).hub!=null)((MainActivity)a).hub.select(AppHub.DOWNLOADS);else a.startActivity(new Intent(a,DownloadCenterActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));});
    add(out,"settings","应用设置","启动、外观与后台提醒","设置 主题 通知 黑夜 setting",()->{if(a instanceof MainActivity&&((MainActivity)a).hub!=null)((MainActivity)a).hub.select(AppHub.SETTINGS);else a.startActivity(new Intent(a,AppSettingsActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));});
    add(out,"backup","环境配置备份","导出或恢复密码加密的环境配置","备份 迁移 导入 导出 backup",()->a.startActivity(new Intent(a,EnvironmentConfigBackupActivity.class)));
    add(out,"updates","检查应用更新","查看更新与版本通道","升级 版本 安装 update",()->AppUpdates.open(a));
    add(out,"feedback","问题与建议","提交反馈并查看处理进度","帮助 反馈 建议 bug help",()->FeedbackUi.open(a));
    return out;
  }
  static void show(Activity a){
    if(a.isFinishing()||a.isDestroyed())return;
    List<Command> commands=commands(a);List<ActionSearchPolicy.Item> items=new ArrayList<>();Map<String,Command> byId=new HashMap<>();for(Command c:commands){items.add(c.item);byId.put(c.item.id,c);}
    List<String> recent=ActionSearchPolicy.recent(AppSettings.get(a,RECENTS,""),items);
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(a,"搜索操作");
    LinearLayout heading=DesignUi.row(a);heading.setClipChildren(false);heading.setClipToPadding(false);
    while(dialog.head.getChildCount()>0){View child=dialog.head.getChildAt(0);android.view.ViewGroup.LayoutParams params=child.getLayoutParams();dialog.head.removeView(child);heading.addView(child,params);}
    dialog.head.setOrientation(LinearLayout.VERTICAL);dialog.head.addView(heading,new LinearLayout.LayoutParams(-1,-2));
    LinearLayout field=DesignUi.column(a);field.setPadding(0,DesignUi.dp(a,6),0,DesignUi.dp(a,8));
    FrameLayout searchHost=new FrameLayout(a);
    EditText search=new EditText(a);search.setSingleLine(true);NativeControls.prepare(search);
    search.setTextSize(15);search.setTextColor(DesignUi.TEXT);search.setHintTextColor(ReferenceUi.secondaryInk());
    search.setHint("搜索草稿、网络、下载…");search.setContentDescription("搜索应用操作");
    search.setImeOptions(EditorInfo.IME_ACTION_GO);search.setMinHeight(DesignUi.dp(a,46));
    search.setPadding(DesignUi.dp(a,14),DesignUi.dp(a,10),DesignUi.dp(a,14),DesignUi.dp(a,10));
    search.setBackground(new ReferenceUi.FieldWell(a){
      @Override protected void drawBase(android.graphics.Canvas canvas,boolean dark,float r){
        if(!dark){
          fill.setColor(0xffffffff);canvas.drawRoundRect(face,r,r,fill);
          rim.setStrokeWidth(Math.max(1f,0.55f*density));rim.setColor(0x18111827);
          canvas.drawRoundRect(edge,Math.max(0f,r-0.35f*density),Math.max(0f,r-0.35f*density),rim);
        }else super.drawBase(canvas,true,r);
      }
    });
    Ui.Icon lens=new Ui.Icon("search",ReferenceUi.secondaryInk());lens.setBounds(0,0,DesignUi.dp(a,17),DesignUi.dp(a,17));
    search.setCompoundDrawables(lens,null,null,null);search.setCompoundDrawablePadding(DesignUi.dp(a,8));
    searchHost.addView(search,new FrameLayout.LayoutParams(-1,-2));
    Button clear=ReferenceUi.iconButton(a,"close","清除搜索内容",()->search.setText(""));clear.setVisibility(View.GONE);
    searchHost.addView(clear,new FrameLayout.LayoutParams(DesignUi.dp(a,46),DesignUi.dp(a,46),Gravity.END|Gravity.CENTER_VERTICAL));
    field.addView(searchHost,new LinearLayout.LayoutParams(-1,-2));
    TextView count=ReferenceUi.workspaceText(a,"",ReferenceUi.SECONDARY_SIZE,ReferenceUi.secondaryInk(),false);
    count.setFontFeatureSettings("tnum");count.setPadding(DesignUi.dp(a,4),DesignUi.dp(a,8),DesignUi.dp(a,4),0);
    count.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);field.addView(count);
    dialog.head.addView(field,new LinearLayout.LayoutParams(-1,-2));
    final List<ActionSearchPolicy.Item> shown=new ArrayList<>();
    java.util.function.Consumer<String> execute=id->{Command command=byId.get(id);if(command==null)return;dialog.dismiss();AppSettings.put(a,RECENTS,ActionSearchPolicy.remember(id,recent));command.run.run();};
    Runnable render=()->{List<ActionSearchPolicy.Item> result=ActionSearchPolicy.search(items,search.getText().toString(),recent);shown.clear();shown.addAll(result);dialog.body.removeAllViews();
      count.setText(result.size()+" 项操作"+(search.length()==0&&!recent.isEmpty()?" · 最近使用优先":""));
      if(result.isEmpty()){
        dialog.body.addView(ReferenceUi.modalEmpty(a,"search","没有匹配的操作","试试“文件”“草稿”“账号”或“设置”。"),new LinearLayout.LayoutParams(-1,-2));
      }else{
        LinearLayout group=ReferenceUi.modalGroup(a);
        for(int i=0;i<result.size();i++){
          if(i>0)group.addView(ReferenceUi.modalDivider(a,58));
          ActionSearchPolicy.Item item=result.get(i);
          group.addView(commandRow(a,item,()->execute.accept(item.id)),new LinearLayout.LayoutParams(-1,-2));
        }
        dialog.body.addView(group,new LinearLayout.LayoutParams(-1,-2));
      }
      dialog.resize();};
    search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){clear.setVisibility(s.length()==0?View.GONE:View.VISIBLE);search.setPadding(DesignUi.dp(a,14),DesignUi.dp(a,10),DesignUi.dp(a,s.length()==0?14:48),DesignUi.dp(a,10));render.run();}public void afterTextChanged(Editable e){}});
    search.setOnEditorActionListener((view,action,event)->{boolean enter=event!=null&&event.getAction()==KeyEvent.ACTION_DOWN&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER;if((action==EditorInfo.IME_ACTION_GO||enter)&&!shown.isEmpty()){execute.accept(shown.get(0).id);return true;}return false;});
    render.run();dialog.show();search.requestFocus();
    dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
  }
}
