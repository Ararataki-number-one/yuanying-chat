package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;

/** Saved files can be opened, shared, copied or removed without another download. */
final class SavedFileActions {
  static final int EXPORT=85;final Activity a;final ExecutorService worker=Executors.newSingleThreadExecutor();final Handler main=new Handler(Looper.getMainLooper());JSONObject exporting;volatile boolean closed,busy;String deleteProblem="";
  SavedFileActions(Activity a){this.a=a;}
  void show(JSONObject row){new AlertDialog.Builder(a).setTitle(row.optString("name","文件")).setItems(new String[]{"打开","分享","另存为","查看保存位置","删除文件"},(d,n)->{if(n==0)open(a,row);if(n==1)share(a,row);if(n==2)export(row);if(n==3)new AlertDialog.Builder(a).setTitle("保存位置").setMessage(row.optString("location","原先选择的保存位置")+"\n\n如果文件被移动或删除，请从原网页重新下载。").setPositiveButton("关闭",null).show();if(n==4)confirmDelete(row);}).show();}
  AlertDialog confirmDelete(JSONObject row){
    JSONObject selected=J.parse(row.toString());if(!selected.has("slot"))DownloadTasks.put(selected,"slot",Profiles.slot(a));String name=selected.optString("name","文件");
    String detail="会从保存位置永久删除这个文件，释放手机存储空间。";
    if(name.toLowerCase(java.util.Locale.ROOT).endsWith(".apk"))detail+="\n已安装的软件不受影响。";
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("删除“"+name+"”？").setMessage(detail)
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
  static Intent shareIntent(JSONObject row){Uri uri=Uri.parse(row.optString("uri"));Intent intent=new Intent(Intent.ACTION_SEND).setType(row.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));return intent;}
  static void open(Activity a,JSONObject row){Uri uri=Uri.parse(row.optString("uri"));String mime=row.optString("mime","application/octet-stream");try{if(mime.equals("application/pdf")||mime.startsWith("image/"))a.startActivity(new Intent(a,Profiles.preview(a)).putExtra("uri",uri.toString()).putExtra("name",row.optString("name")).putExtra("mime",mime));else{Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));a.startActivity(intent);}}catch(Exception e){problem(a,"文件无法打开，可能已移动或手机没有对应查看器");}}
  static void share(Activity a,JSONObject row){try{a.startActivity(Intent.createChooser(shareIntent(row),"分享文件"));}catch(Exception e){problem(a,"文件已移动或无法分享");}}
  void export(JSONObject row){if(busy||exporting!=null){problem(a,"请先完成当前另存为");return;}exporting=J.parse(row.toString());try{a.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(row.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_TITLE,row.optString("name","文件")),EXPORT);}catch(Exception e){exporting=null;problem(a,"设备没有文件保存器");}}
  void result(int result,Intent data){
    JSONObject source=exporting;exporting=null;if(source==null||result!=Activity.RESULT_OK||data==null||data.getData()==null)return;
    Uri destination=data.getData(),original=Uri.parse(source.optString("uri"));if(destination.equals(original))return;busy=true;
    worker.execute(()->{
      boolean success=false;String issue="另存为失败，原文件已保留";
      try{SavedFileDeletion.lease(a,destination,()->{
        if(DownloadLibrary.get(a).indexed(destination))throw new IOException("请另存为新的文件名，已有下载文件已保留");
        boolean copied=false;
        try(InputStream in=a.getContentResolver().openInputStream(original);OutputStream out=a.getContentResolver().openOutputStream(destination,"wt")){
          if(in==null||out==null)throw new IOException();byte[] buffer=new byte[65536];int n;
          while((n=in.read(buffer))!=-1){if(closed)throw new IOException();out.write(buffer,0,n);}out.flush();copied=true;
        }finally{if(!copied)delete(a,destination);}return null;
      });success=true;}catch(Exception error){if(error.getMessage()!=null&&error.getMessage().contains("新的文件名"))issue=error.getMessage();}
      boolean done=success;String message=issue;main.post(()->{busy=false;if(!closed&&!done)problem(a,message);});
    });
  }
  static void delete(Context c,Uri uri){try{if(android.provider.DocumentsContract.isDocumentUri(c,uri))android.provider.DocumentsContract.deleteDocument(c.getContentResolver(),uri);else c.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}}
  static void problem(Activity a,String message){if(a instanceof MainActivity){MainActivity host=(MainActivity)a;if(host.hub!=null&&host.hub.page!=AppHub.CHAT)host.hub.feedback(message,true);else host.status("文件操作失败："+message);}else if(a instanceof DownloadCenterActivity)((DownloadCenterActivity)a).showProblem(message);else if(a instanceof WindowHomeActivity)((WindowHomeActivity)a).showProblem(message);}
  void close(){closed=true;worker.shutdown();}
}
