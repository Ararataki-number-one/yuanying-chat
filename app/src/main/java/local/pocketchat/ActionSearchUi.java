package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
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
  static List<Command> commands(Activity a){
    List<Command> out=new ArrayList<>();
    if(a instanceof MainActivity){MainActivity m=(MainActivity)a;ChatSession owner=m.session;
      if(owner!=null&&m.hub!=null){
        java.util.function.Consumer<Runnable> current=run->{if(NetworkStatusUi.current(m,owner)&&ProfileCatalog.get(m).available(Profiles.slot(m)))run.run();};
        add(out,"chat","返回当前会话","继续当前网页与输入","聊天 返回 继续 chat",()->current.accept(()->m.hub.select(AppHub.CHAT)));
        add(out,"switch","快速切换环境","搜索窗口，保留正在进行的会话","账号 窗口 切换 switch",()->EnvironmentSwitcherUi.show(a));
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
    add(out,"environments","管理全部环境","任务收件箱、环境配置和保存视图","账号 窗口 工作台 environment",()->a.startActivity(new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
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
    LinearLayout heading=DesignUi.row(a);while(dialog.head.getChildCount()>0){View child=dialog.head.getChildAt(0);android.view.ViewGroup.LayoutParams params=child.getLayoutParams();dialog.head.removeView(child);heading.addView(child,params);}dialog.head.setOrientation(LinearLayout.VERTICAL);dialog.head.addView(heading,new LinearLayout.LayoutParams(-1,-2));
    LinearLayout field=DesignUi.column(a);EditText search=DesignUi.searchInput(field,"例如：草稿、切换、下载、网络");search.setContentDescription("搜索应用操作");search.setImeOptions(EditorInfo.IME_ACTION_GO);dialog.head.addView(field,new LinearLayout.LayoutParams(-1,-2));
    TextView count=DesignUi.text(a,"",12,DesignUi.MUTED);count.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);field.addView(count);
    final List<ActionSearchPolicy.Item> shown=new ArrayList<>();
    java.util.function.Consumer<String> execute=id->{Command command=byId.get(id);if(command==null)return;dialog.dismiss();AppSettings.put(a,RECENTS,ActionSearchPolicy.remember(id,recent));command.run.run();};
    Runnable render=()->{List<ActionSearchPolicy.Item> result=ActionSearchPolicy.search(items,search.getText().toString(),recent);shown.clear();shown.addAll(result);dialog.body.removeAllViews();count.setText(result.size()+" 项操作"+(search.length()==0&&!recent.isEmpty()?" · 最近使用优先":""));
      for(ActionSearchPolicy.Item item:result)DesignUi.groupedRow(dialog.body,DesignUi.setting(a,"info",item.label,item.detail,"",()->execute.accept(item.id)));
      if(result.isEmpty())DesignUi.note(dialog.body,"没有匹配的操作。试试“文件”“草稿”“账号”或“设置”。");
      dialog.resize();};
    search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){render.run();}public void afterTextChanged(Editable e){}});
    search.setOnEditorActionListener((view,action,event)->{boolean enter=event!=null&&event.getAction()==KeyEvent.ACTION_DOWN&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER;if((action==EditorInfo.IME_ACTION_GO||enter)&&!shown.isEmpty()){execute.accept(shown.get(0).id);return true;}return false;});
    dialog.buttons("关闭",dialog::dismiss,"",()->{});render.run();dialog.show();search.requestFocus();
    dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
  }
}
