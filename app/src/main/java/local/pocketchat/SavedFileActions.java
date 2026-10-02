package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;

/** Saved files can be opened, shared or copied elsewhere without another download. */
final class SavedFileActions {
  static final int EXPORT=85;final Activity a;final ExecutorService worker=Executors.newSingleThreadExecutor();final Handler main=new Handler(Looper.getMainLooper());JSONObject exporting;volatile boolean closed,busy;
  SavedFileActions(Activity a){this.a=a;}
  void show(JSONObject row){new AlertDialog.Builder(a).setTitle(row.optString("name","文件")).setItems(new String[]{"打开","分享","另存为","查看保存位置"},(d,n)->{if(n==0)open(a,row);if(n==1)share(a,row);if(n==2)export(row);if(n==3)new AlertDialog.Builder(a).setTitle("保存位置").setMessage(row.optString("location","原先选择的保存位置")+"\n\n如果文件被移动或删除，请从原网页重新下载。").setPositiveButton("关闭",null).show();}).show();}
  static Intent shareIntent(JSONObject row){Uri uri=Uri.parse(row.optString("uri"));Intent intent=new Intent(Intent.ACTION_SEND).setType(row.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));return intent;}
  static void open(Activity a,JSONObject row){Uri uri=Uri.parse(row.optString("uri"));String mime=row.optString("mime","application/octet-stream");try{if(mime.equals("application/pdf")||mime.startsWith("image/"))a.startActivity(new Intent(a,Profiles.preview(a)).putExtra("uri",uri.toString()).putExtra("name",row.optString("name")).putExtra("mime",mime));else{Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("已保存文件",uri));a.startActivity(intent);}}catch(Exception e){toast(a,"文件无法打开，可能已移动或手机没有对应查看器");}}
  static void share(Activity a,JSONObject row){try{a.startActivity(Intent.createChooser(shareIntent(row),"分享文件"));}catch(Exception e){toast(a,"文件已移动或无法分享");}}
  void export(JSONObject row){if(busy||exporting!=null){toast(a,"请先完成当前另存为");return;}exporting=J.parse(row.toString());try{a.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(row.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_TITLE,row.optString("name","文件")),EXPORT);}catch(Exception e){exporting=null;toast(a,"设备没有文件保存器");}}
  void result(int result,Intent data){JSONObject source=exporting;exporting=null;if(source==null||result!=Activity.RESULT_OK||data==null||data.getData()==null)return;Uri destination=data.getData(),original=Uri.parse(source.optString("uri"));if(destination.equals(original)){toast(a,"文件已经在这个位置");return;}busy=true;worker.execute(()->{boolean success=false;try(InputStream in=a.getContentResolver().openInputStream(original);OutputStream out=a.getContentResolver().openOutputStream(destination,"wt")){if(in==null||out==null)throw new IOException();byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){if(closed)throw new IOException();out.write(buffer,0,n);}out.flush();success=true;}catch(Exception e){delete(a,destination);}boolean done=success;main.post(()->{busy=false;if(!closed)toast(a,done?"另存为完成，原文件已保留":"另存为失败，原文件已保留");});});}
  static void delete(Context c,Uri uri){try{if(android.provider.DocumentsContract.isDocumentUri(c,uri))android.provider.DocumentsContract.deleteDocument(c.getContentResolver(),uri);else c.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}}
  static void toast(Context c,String s){android.widget.Toast.makeText(c,s,android.widget.Toast.LENGTH_LONG).show();}
  void close(){closed=true;worker.shutdown();}
}
