package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.widget.*;
import java.util.Locale;

/** Small app-wide page; no browser session is created, stopped or reloaded here. */
public class AppUpdateActivity extends Activity {
  LinearLayout box;ProgressBar downloadProgress;TextView downloadDetails;final Handler handler=new Handler(Looper.getMainLooper());String rendered="",installMessage="";long pendingInstall;boolean permissionPending;int originSlot=-1;
  final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1000);}};
  @Override public void onCreate(Bundle state){super.onCreate(state);originSlot=getIntent().getIntExtra("originSlot",-1);if(state!=null){originSlot=state.getInt("originSlot",originSlot);pendingInstall=state.getLong("install");installMessage=state.getString("installMessage","");permissionPending=state.getBoolean("permission");}LinearLayout root=DesignUi.screen(this);box=DesignUi.body(this,root,"应用更新",()->finish());setContentView(root);}
  @Override protected void onResume(){super.onResume();handler.removeCallbacks(tick);handler.post(tick);AppUpdates.schedule(this);if(permissionPending){permissionPending=false;if(getPackageManager().canRequestPackageInstalls())install();else installIssue("尚未允许安装更新，可稍后再次点击安装");}}
  @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
  @Override protected void onSaveInstanceState(Bundle state){state.putInt("originSlot",originSlot);state.putLong("install",pendingInstall);state.putString("installMessage",installMessage);state.putBoolean("permission",permissionPending);super.onSaveInstanceState(state);}
  void refresh(){Bundle status=AppUpdates.call(this,"status",null);String fingerprint="installMessage:"+installMessage+"\n";for(String key:new String[]{"state","message","version","notes","bytes","checkedAt","autoCheck","autoDownload","wifiOnly","verifiedSerial","packageDeleteRetry","packageUri"})fingerprint+=key+":"+String.valueOf(status.get(key))+"\n";String phase=status.getString("state","");if("available".equals(phase)||"error".equals(phase))fingerprint+="resume:"+status.getBoolean("canResume");if(!fingerprint.equals(rendered)){rendered=fingerprint;DesignUi.rebuild(box,true,()->render(status));}updateProgress(status);
    if(pendingInstall>0){String kind=status.getString("state","");if(status.containsKey("verifyRequestedSerial")&&status.getLong("verifyRequestedSerial")!=pendingInstall){pendingInstall=0;}else if("ready".equals(kind)&&status.getLong("verifiedSerial")==pendingInstall){pendingInstall=0;install();}else if(!"ready".equals(kind)&&!"verifying".equals(kind)){pendingInstall=0;}}
  }
  void action(String name){installMessage="";Bundle extras=new Bundle();if(AppUpdates.validSlot(originSlot))extras.putInt("originSlot",originSlot);AppUpdates.call(this,name,extras);rendered="";refresh();}
  void render(Bundle b){
    downloadProgress=null;downloadDetails=null;
    String state=b.getString("state","idle"),version=b.getString("version",""),message=b.getString("message","");boolean downloading="downloading".equals(state)||"waiting".equals(state),resumable="paused".equals(state)||("available".equals(state)||"error".equals(state))&&b.getBoolean("canResume");boolean busy=downloading||"verifying".equals(state)||"checking".equals(state)||"deleting".equals(state);
    LinearLayout card=DesignUi.card(this);TextView title=DesignUi.text(this,"当前版本 "+AppVersion.name(this),18,DesignUi.TEXT);title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);card.addView(title);
    String status="ready".equals(state)?"新版 "+version+" 已下载":"paused".equals(state)?"下载已暂停":"waiting".equals(state)?"等待继续下载":"available".equals(state)?"发现新版本 "+version:"checking".equals(state)?"正在检查更新":"downloading".equals(state)?"正在下载 "+version:"verifying".equals(state)?"正在核验安装包":"deleting".equals(state)?"正在删除安装包":"error".equals(state)?"暂时无法检查更新":message.isEmpty()?"尚未检查更新":message;
    TextView label=DesignUi.text(this,status,15,"error".equals(state)?DesignUi.RED:DesignUi.BLUE);label.setPadding(0,DesignUi.dp(this,12),0,0);label.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);card.addView(label);
    if(!message.isEmpty()&&!message.equals(status))DesignUi.note(card,message);
    if(!installMessage.isEmpty()){TextView issue=DesignUi.text(this,installMessage,14,DesignUi.RED);issue.setPadding(0,DesignUi.dp(this,8),0,0);issue.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);card.addView(issue);}
    if(downloading||resumable){downloadProgress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);downloadProgress.setMax(1000);card.addView(downloadProgress);downloadDetails=DesignUi.text(this,"",13,DesignUi.MUTED);downloadDetails.setPadding(0,DesignUi.dp(this,8),0,0);card.addView(downloadDetails);updateProgress(b);
      DesignUi.action(card,downloading?"暂停下载":"继续下载",!downloading,()->action(downloading?"pause":"resume"));
      DesignUi.action(card,"取消下载",false,()->new AlertDialog.Builder(this).setTitle("取消这次下载？").setMessage("会删除已下载部分。仅想稍后继续，请选择暂停下载。").setNegativeButton("保留下载",null).setPositiveButton("取消下载",(d,w)->action("cancel")).show());}
    else if("ready".equals(state)){DesignUi.action(card,"安装更新",true,()->{if(pendingInstall>0)return;installMessage="";Bundle result=AppUpdates.call(this,"verify",null);pendingInstall=result.getLong("requestedSerial");rendered="";refresh();});DesignUi.action(card,"删除安装包",false,()->confirmDeletePackage(b));}
    else if("available".equals(state))DesignUi.action(card,"下载更新 · "+mb(b.getLong("bytes"))+" MB",true,()->action("download"));
    if(b.getBoolean("packageDeleteRetry"))DesignUi.action(card,"重试删除安装包",false,()->confirmDeletePackage(b));
    if(!busy){DesignUi.action(card,"检查更新",false,()->action("check"));long time=b.getLong("checkedAt");if(time>0)DesignUi.note(card,"上次检查："+android.text.format.DateFormat.getDateFormat(this).format(new java.util.Date(time))+" "+android.text.format.DateFormat.getTimeFormat(this).format(new java.util.Date(time)));}
    DesignUi.addCard(box,card);
    if(!version.isEmpty()&&!b.getString("notes","").isEmpty()){LinearLayout notes=DesignUi.card(this);DesignUi.section(notes,"这次更新","");TextView text=DesignUi.text(this,b.getString("notes"),14,DesignUi.TEXT);text.setTextIsSelectable(true);text.setLineSpacing(DesignUi.dp(this,4),1);notes.addView(text);DesignUi.addCard(box,notes);}
    LinearLayout options=DesignUi.card(this);DesignUi.section(options,"更新偏好","");toggle(options,"自动检查更新","autoCheck",b.getBoolean("autoCheck",true));toggle(options,"Wi-Fi 下自动下载新版","autoDownload",b.getBoolean("autoDownload",false));toggle(options,"手动下载也仅使用 Wi-Fi","wifiOnly",b.getBoolean("wifiOnly",true));DesignUi.note(options,"内置网络使用所选环境线路；其他模式沿用手机连接。自动检查每天一次，安装前会请你确认。");DesignUi.addCard(box,options);
  }
  void updateProgress(Bundle b){if(downloadProgress==null||downloadDetails==null)return;long total=b.getLong("total",b.getLong("bytes")),read=Math.max(0,b.getLong("received")),speed=b.getLong("bytesPerSecond"),seconds=b.getLong("remainingSeconds",-1);downloadProgress.setIndeterminate(total<=0);if(total>0)downloadProgress.setProgress((int)Math.min(1000,read*1000/total));String text=mb(read)+" / "+mb(total)+" MB";if("downloading".equals(b.getString("state"))&&speed>0){text+=" · "+(speed>=1048576?mb(speed)+" MB/s":String.format(Locale.getDefault(),"%.0f KB/s",speed/1024.0));if(seconds>=0)text+=" · 约剩 "+(seconds<60?seconds+" 秒":(seconds+59)/60+" 分钟");}if(!text.contentEquals(downloadDetails.getText()))downloadDetails.setText(text);}
  void toggle(LinearLayout parent,String text,String key,boolean value){Switch option=new Switch(this);option.setText(text);option.setTextSize(14);option.setTextColor(DesignUi.TEXT);option.setChecked(value);option.setPadding(0,DesignUi.dp(this,10),0,DesignUi.dp(this,10));parent.addView(option,new LinearLayout.LayoutParams(-1,-2));option.setOnCheckedChangeListener((button,enabled)->{Bundle extras=new Bundle();extras.putBoolean(key,enabled);AppUpdates.call(this,"settings",extras);rendered="";});}
  static String mb(long bytes){return String.format(Locale.getDefault(),"%.1f",bytes/1048576.0);}
  void installIssue(String message){installMessage=message;rendered="";refresh();}
  AlertDialog confirmDeletePackage(Bundle shown){return new AlertDialog.Builder(this).setTitle("删除安装包？").setMessage("会删除已下载的更新安装包，释放存储空间。更新偏好会保留，之后可重新下载。").setNegativeButton("保留安装包",null).setPositiveButton("删除安装包",(dialog,which)->{pendingInstall=0;permissionPending=false;Bundle extras=new Bundle();extras.putLong("code",shown.getLong("code"));extras.putString("packageUri",shown.getString("packageUri",shown.getString("uri","")));Bundle result=AppUpdates.call(this,"deletePackage",extras);installMessage=result.getString("deleteError","");rendered="";refresh();}).show();}
  void install(){Bundle status=AppUpdates.call(this,"status",null);String target=status.getString("uri","");if(target.isEmpty()){installIssue("安装包尚未准备好，请重新下载");return;}
    if(!getPackageManager().canRequestPackageInstalls()){new AlertDialog.Builder(this).setTitle("允许安装应用更新").setMessage("在系统设置中允许本应用安装更新，然后返回即可继续。").setNegativeButton("稍后",null).setPositiveButton("前往设置",(d,w)->{try{permissionPending=true;startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName())));}catch(Exception e){permissionPending=false;installIssue("请在手机设置中允许本应用安装未知应用");}}).show();return;}
    try{Uri uri=Uri.parse(target);Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("应用更新",uri));startActivity(intent);}catch(Exception e){installIssue("无法打开安装界面，请检查系统安装权限后重试");}
  }
}
