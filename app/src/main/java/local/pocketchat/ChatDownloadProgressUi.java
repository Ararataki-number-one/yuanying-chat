package local.pocketchat;

import android.database.ContentObserver;
import android.text.TextUtils;
import android.view.View;
import android.widget.*;

/** Native chat card. Reads the existing in-memory task without polling disk or the browser. */
final class ChatDownloadProgressUi {
  final MainActivity a;final FileDownloads downloads;final LinearLayout card,details,actions;final TextView name,status,amount;
  final ProgressBar progress;final Button fold,primary,cancel;boolean observing,collapsed;String shown="",dismissed="";
  final ContentObserver observer;
  ChatDownloadProgressUi(MainActivity a,LinearLayout root,View browser,FileDownloads downloads){
    this.a=a;this.downloads=downloads;card=DesignUi.card(a);card.setTag("chat-download-progress");card.setVisibility(View.GONE);
    LinearLayout title=DesignUi.row(a);name=DesignUi.text(a,"文件下载",14,DesignUi.TEXT);name.setMaxLines(1);name.setEllipsize(TextUtils.TruncateAt.END);title.addView(name,new LinearLayout.LayoutParams(0,-2,1));
    fold=DesignUi.button(a,"收起",false,()->{ChatDownloadProgress state=current();if(state==null)return;if(!state.busy){dismissed=state.id;card.setVisibility(View.GONE);}else{collapsed=!collapsed;update();}});title.addView(fold,new LinearLayout.LayoutParams(-2,a.dp(40)));card.addView(title);
    status=DesignUi.text(a,"",13,DesignUi.MUTED);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);card.addView(status);
    progress=new ProgressBar(a,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(1000);progress.setContentDescription("文件下载进度");card.addView(progress,new LinearLayout.LayoutParams(-1,a.dp(8)));
    details=DesignUi.column(a);amount=DesignUi.text(a,"",12,DesignUi.MUTED);amount.setMaxLines(2);details.addView(amount);actions=DesignUi.row(a);
    primary=DesignUi.button(a,"暂停",false,()->{ChatDownloadProgress state=current();if(state==null)return;if(state.busy&&downloads.active)downloads.pause();else if(downloads.task!=null)downloads.taskActions(downloads.task);update();});actions.addView(primary,new LinearLayout.LayoutParams(0,a.dp(44),1));
    cancel=DesignUi.button(a,"取消下载",false,()->{if(current()!=null)downloads.requestCancel();});actions.addView(cancel,new LinearLayout.LayoutParams(0,a.dp(44),1));
    actions.addView(DesignUi.button(a,"下载中心",false,()->{if(a.hub!=null)a.hub.select(AppHub.DOWNLOADS);}),new LinearLayout.LayoutParams(0,a.dp(44),1));details.addView(actions);card.addView(details);
    LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(-1,-2);layout.setMargins(a.dp(12),a.dp(4),a.dp(12),a.dp(6));root.addView(card,root.indexOfChild(browser),layout);
    observer=new ContentObserver(a.handler){@Override public void onChange(boolean self){update();}};
  }
  ChatDownloadProgress current(){ChatSession session=a.session;if(session==null||session.deleted)return null;return ChatDownloadProgress.read(downloads.task,Profiles.slot(a),session.environmentId,session.environmentGeneration);}
  void visible(boolean value){
    if(value&&!observing){try{a.getContentResolver().registerContentObserver(DownloadLibraryChanges.uri(a),false,observer);observing=true;}catch(RuntimeException ignored){}}
    if(!value&&observing){try{a.getContentResolver().unregisterContentObserver(observer);}catch(RuntimeException ignored){}observing=false;}
    if(!value)card.setVisibility(View.GONE);
  }
  void update(){
    if(android.os.Looper.myLooper()!=android.os.Looper.getMainLooper()){a.handler.post(this::update);return;}
    boolean foreground=a.active&&!a.destroyed&&a.hub!=null&&a.hub.page==AppHub.CHAT;visible(foreground);if(!foreground)return;
    ChatDownloadProgress state=current();if(state!=null&&state.busy&&state.id.equals(dismissed))dismissed="";if(state==null||state.id.equals(dismissed)){card.setVisibility(View.GONE);return;}
    if(!state.id.equals(shown)){shown=state.id;collapsed=false;dismissed="";}card.setVisibility(View.VISIBLE);name.setText(state.name);
    String label=DownloadTasks.label(state.state);if(!label.contentEquals(status.getText()))status.setText(label);status.setTextColor("failed".equals(state.state)?DesignUi.RED:DesignUi.MUTED);
    progress.setIndeterminate(state.busy&&!state.determinate);if(!progress.isIndeterminate())progress.setProgress("saved".equals(state.state)?1000:state.progress);
    String value=DownloadTasks.amount(state.received)+(state.determinate?" / "+DownloadTasks.amount(state.total)+" · "+state.progress/10+"%":" · 文件总大小未知");if(!state.reason.isEmpty())value+="\n"+state.reason;amount.setText(value);
    details.setVisibility(collapsed?View.GONE:View.VISIBLE);fold.setText(state.busy?(collapsed?"展开":"收起"):"关闭");primary.setText(state.busy?"暂停":"saved".equals(state.state)?"查看文件":"paused".equals(state.state)?"继续":"查看详情");
    primary.setEnabled(!"preparing".equals(state.state)&&!"saving".equals(state.state)&&!"choosing".equals(state.state));cancel.setVisibility("saved".equals(state.state)||"cancelled".equals(state.state)?View.GONE:View.VISIBLE);
  }
  void close(){visible(false);}
}
