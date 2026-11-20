package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.widget.*;
import java.text.DateFormat;
import java.util.*;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;

/** Saved files can be opened, shared, copied or removed without another download. */
final class SavedFileActions {
  static final int EXPORT=85;final Activity a;final ExecutorService worker=Executors.newSingleThreadExecutor();final Handler main=new Handler(Looper.getMainLooper());JSONObject exporting;volatile boolean closed,busy;String deleteProblem="";volatile long detailEpoch;AlertDialog detailDialog;
  private static final String EXPORT_STATE="savedFileExport";
  private static final String SOURCE_UNAVAILABLE="原文件已移走或下载记录已变化，请重新选择来源";
  private boolean restoredExport;
  private Uri unverifiedTarget;
  private AlertDialog exportRetryDialog;

  SavedFileActions(Activity a){this.a=a;}

  void saveState(Bundle state){
    if(exporting==null)return;
    Bundle pending=new Bundle();
    pending.putString("uri",exporting.optString("uri"));
    pending.putInt("slot",exporting.optInt("slot",Profiles.slot(a)));
    pending.putString("id",exporting.optString("id"));
    pending.putLong("time",exporting.optLong("time"));
    state.putBundle(EXPORT_STATE,pending);
  }

  static SavedFileActions restore(Activity activity,Bundle state){
    Bundle pending=state==null?null:state.getBundle(EXPORT_STATE);
    if(pending==null)return null;
    String source=pending.getString("uri"),id=pending.getString("id");
    int slot=pending.getInt("slot",-1);
    long time=pending.getLong("time",-1);
    if(source==null||id==null||slot<0||slot>=Profiles.MAX||time<0||!documentUri(Uri.parse(source)))return null;
    SavedFileActions actions=new SavedFileActions(activity);
    actions.exporting=J.obj("uri",source,"slot",slot,"id",id,"time",time);
    actions.restoredExport=true;
    return actions;
  }

  private static boolean documentUri(Uri uri){
    return uri!=null&&"content".equals(uri.getScheme())&&uri.getAuthority()!=null&&!uri.getAuthority().isEmpty();
  }
  void show(JSONObject row){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,DownloadMetadataValues.name(row)).asSheet();
    String[] labels={"打开","分享","另存为","详细信息","删除文件"};
    for(int i=0;i<labels.length;i++){final int n=i;ReferenceUi.menuAction(d,labels[i],()->{
      d.dismiss();if(n==0)open(a,row);if(n==1)share(a,row);if(n==2)export(row);
      if(n==3)details(row);
      if(n==4)confirmDelete(row);
    });}d.show();
  }
  static String detailsText(JSONObject row){long time=row.optLong("time");return "文件名称\n"+DownloadMetadataValues.name(row)+"\n\n大小\n"+DownloadTasks.amount(DownloadMetadataValues.bytes(row))+"\n\n类型\n"+DownloadMetadataValues.mime(row)+"\n\n保存时间\n"+(time<=0?"时间未记录":DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,Locale.getDefault()).format(new Date(time)))+"\n\n保存位置\n"+DownloadMetadataValues.location(row);}
  void details(JSONObject selected){
    if(closed)return;if(detailDialog!=null)detailDialog.dismiss();long token=++detailEpoch;JSONObject row=J.parse(selected.toString());if(!row.has("slot"))DownloadTasks.put(row,"slot",Profiles.slot(a));final JSONObject[] current={row};
    LinearLayout box=DesignUi.column(a);int padding=DesignUi.dp(a,20);box.setPadding(padding,padding,padding,padding);TextView text=DesignUi.text(a,detailsText(row),14,DesignUi.TEXT);text.setTextIsSelectable(true);box.addView(text);ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("详细信息").setView(scroll).setPositiveButton("关闭",null).setNeutralButton("复制位置",null).setNegativeButton("重新读取信息",null).create();detailDialog=dialog;
    dialog.setOnDismissListener(d->{if(detailEpoch==token){detailEpoch++;detailDialog=null;}});dialog.show();
    dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{if(closed||detailEpoch!=token)return;ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);if(clipboard!=null)clipboard.setPrimaryClip(ClipData.newPlainText("保存位置",DownloadMetadataValues.location(current[0])));});
    dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener(v->{if(closed||detailEpoch!=token)return;dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);SavedDownloadMetadata.retry(a,current[0],()->!closed&&detailEpoch==token,updated->{if(!dialog.isShowing())return;dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);if(updated!=null){current[0]=updated;text.setText(detailsText(updated));}});});
  }
  AlertDialog confirmDelete(JSONObject row){
    JSONObject selected=J.parse(row.toString());if(!selected.has("slot"))DownloadTasks.put(selected,"slot",Profiles.slot(a));String name=DownloadMetadataValues.name(selected);
    String detail="会从保存位置永久删除这个文件，释放手机存储空间。";
    if(name.toLowerCase(java.util.Locale.ROOT).endsWith(".apk"))detail+="\n已安装的软件不受影响。";
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("删除“"+name+"”？").setMessage(detail)
        .setNegativeButton("取消",null).setPositiveButton("删除文件",(d,w)->remove(selected)).create();
    dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(DesignUi.RED);return dialog;
  }
  void remove(JSONObject row){
    if(closed)return;if(busy||exporting!=null){problem(a,"请先完成当前文件操作");return;}busy=true;
    worker.execute(()->{
      String error="";try{SavedFileDeletion.remove(a,row);}catch(Exception e){error=e.getMessage()==null?"删除失败，下载记录已保留":e.getMessage();}
      String message=error;main.post(()->{busy=false;if(closed)return;
        if(!message.isEmpty()){deleteProblem=message;problem(a,message);}
        else if(a instanceof DownloadCenterActivity){DownloadCenterActivity center=(DownloadCenterActivity)a;center.showProblem("");center.refresh();}
        else if(a instanceof MainActivity){MainActivity host=(MainActivity)a;if(!deleteProblem.isEmpty()){if(host.hub!=null&&android.text.TextUtils.equals(host.hub.feedbackText.getText(),deleteProblem))host.hub.feedbackBar.setVisibility(android.view.View.GONE);if(host.status!=null&&android.text.TextUtils.equals(host.status.getText(),"文件操作失败："+deleteProblem))host.status.setVisibility(android.view.View.GONE);}if(host.hub!=null&&host.hub.page==AppHub.DOWNLOADS)host.hub.refresh();}
        if(message.isEmpty())deleteProblem="";
      });
    });
  }
  static Intent shareIntent(JSONObject row){Uri uri=Uri.parse(row.optString("uri"));Intent intent=new Intent(Intent.ACTION_SEND).setType(DownloadMetadataValues.mime(row)).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));return intent;}
  static void open(Activity a,JSONObject row){Uri uri=Uri.parse(row.optString("uri"));String mime=DownloadMetadataValues.mime(row);try{if(mime.equals("application/pdf")||mime.startsWith("image/"))a.startActivity(new Intent(a,Profiles.preview(a)).putExtra("uri",uri.toString()).putExtra("name",DownloadMetadataValues.name(row)).putExtra("mime",mime));else{Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));a.startActivity(intent);}}catch(Exception e){problem(a,"文件无法打开，可能已移动或手机没有对应查看器");}}
  static void share(Activity a,JSONObject row){try{a.startActivity(Intent.createChooser(shareIntent(row),"分享文件"));}catch(Exception e){problem(a,"文件已移动或无法分享");}}
  void export(JSONObject row){export(row,null);}

  private void export(JSONObject row,Uri previousTarget){
    if(closed)return;
    if(busy||exporting!=null){problem(a,"请先完成当前另存为");return;}
    exporting=J.parse(row.toString());
    unverifiedTarget=previousTarget;
    try{
      a.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
          .setType(DownloadMetadataValues.mime(row)).putExtra(Intent.EXTRA_TITLE,DownloadMetadataValues.name(row)),EXPORT);
    }catch(Exception error){
      exporting=null;
      unverifiedTarget=null;
      problem(a,"设备没有文件保存器");
    }
  }

  void result(int result,Intent data){
    JSONObject source=exporting;
    boolean restored=restoredExport;
    Uri previousTarget=unverifiedTarget;
    exporting=null;
    restoredExport=false;
    unverifiedTarget=null;
    if(closed||source==null||result!=Activity.RESULT_OK)return;
    Uri destination=data==null?null:data.getData();
    if(!documentUri(destination)){problem(a,"没有收到可用的保存位置，请重新另存为");return;}
    Uri original=Uri.parse(source.optString("uri"));
    if(restored){recoverExport(source,original,destination);return;}
    if(destination.equals(original)||destination.equals(previousTarget)){
      if(previousTarget!=null)problem(a,"请选择不同的文件名或保存位置");
      return;
    }
    busy=true;
    try{worker.execute(()->{
      String issue="";
      try{SavedFileDeletion.leaseAll(a,Arrays.asList(original,destination),()->{
        DownloadLibrary library=DownloadLibrary.get(a);
        if(library.indexed(destination))throw new IOException("请另存为新的文件名，已有下载文件已保留");
        if(closed)throw new IOException("另存为已取消");
        if(previousTarget!=null&&library.saved(source)==null)throw new IOException(SOURCE_UNAVAILABLE);
        try(InputStream in=openExportInput(original)){
          if(closed)throw new IOException("另存为已取消");
          try(OutputStream out=a.getContentResolver().openOutputStream(destination,"wt")){
            SavedFileBytes.copy(in,out,()->!closed);
          }
        }
        if(closed)throw new IOException("另存为已取消");
        return null;
      });}catch(Exception error){
        String reason=error.getMessage();
        issue=SOURCE_UNAVAILABLE.equals(reason)||reason!=null&&reason.contains("新的文件名")?reason:
            "另存为未完成，原文件已保留。请检查保存位置后重试";
      }
      String message=issue;
      main.post(()->{busy=false;if(!closed&&!message.isEmpty())problem(a,message);});
    });}catch(RejectedExecutionException retired){busy=false;if(!closed)problem(a,"另存为尚未开始，原文件已保留，请稍后重试");}
  }

  private void recoverExport(JSONObject source,Uri original,Uri destination){
    busy=true;
    try{worker.execute(()->{
      JSONObject verified=null;
      try{verified=SavedFileDeletion.lease(a,original,()->{
        JSONObject row=DownloadLibrary.get(a).saved(source);
        if(row==null||closed)return null;
        try(InputStream input=openExportInput(original)){return row;}
      });}catch(Exception unavailable){}
      JSONObject retry=verified;
      main.post(()->{
        busy=false;
        if(closed)return;
        if(retry==null)problem(a,SOURCE_UNAVAILABLE+"。系统可能已在所选位置留下空文件。");
        else offerExportRetry(retry,destination);
      });
    });}catch(RejectedExecutionException retired){busy=false;if(!closed)problem(a,"另存为尚未开始，原文件已保留，请稍后重试");}
  }

  private InputStream openExportInput(Uri source)throws IOException{
    InputStream opened=null;
    try{
      opened=a.getContentResolver().openInputStream(source);
      if(opened==null)throw new IOException(SOURCE_UNAVAILABLE);
      PushbackInputStream input=new PushbackInputStream(opened);
      int first=input.read();
      if(first!=-1)input.unread(first);
      return input;
    }catch(IOException|RuntimeException error){
      if(opened!=null)try{opened.close();}catch(IOException closing){error.addSuppressed(closing);}
      throw new IOException(SOURCE_UNAVAILABLE,error);
    }
  }

  private void offerExportRetry(JSONObject source,Uri previousTarget){
    if(a.isFinishing()||a.isDestroyed())return;
    if(exportRetryDialog!=null)exportRetryDialog.dismiss();
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("继续另存为")
      .setMessage("保存窗口重建后，应用未写入副本，系统可能已留下空文件。请使用新的文件名或保存位置。")
      .setNegativeButton("取消",null).setPositiveButton("重选保存位置",(d,w)->export(source,previousTarget)).create();
    exportRetryDialog=dialog;
    dialog.setOnDismissListener(d->{if(exportRetryDialog==dialog)exportRetryDialog=null;});
    dialog.show();
  }

  static void problem(Activity a,String message){if(a instanceof MainActivity){MainActivity host=(MainActivity)a;if(host.hub!=null&&host.hub.page!=AppHub.CHAT)host.hub.feedback(message,true);else if(host.status!=null)host.status("文件操作失败："+message);else Toast.makeText(a,message,Toast.LENGTH_LONG).show();}else if(a instanceof DownloadCenterActivity)((DownloadCenterActivity)a).showProblem(message);else if(a instanceof WindowHomeActivity)((WindowHomeActivity)a).showProblem(message);}
  void close(){closed=true;detailEpoch++;if(detailDialog!=null){detailDialog.dismiss();detailDialog=null;}if(exportRetryDialog!=null){exportRetryDialog.dismiss();exportRetryDialog=null;}worker.shutdown();}
}
