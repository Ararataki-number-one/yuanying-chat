package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.util.Log;
import android.widget.TextView;
import org.json.*;
import java.io.*;

/** Test-only synthetic APK over loopback. Production update URLs are never overridden. */
public class AppUpdateIntegrationActivity extends Activity {
  final Handler handler=new Handler(Looper.getMainLooper());String action;AppUpdateManager manager;long started;String hash;
  @Override public void onCreate(Bundle state){super.onCreate(state);TextView text=new TextView(this);text.setText("受控应用更新回归");setContentView(text);command(getIntent());}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);command(intent);}
  void command(Intent intent){handler.removeCallbacksAndMessages(null);action=intent.getStringExtra("updateAction");if("showUi".equals(action)){AppUpdates.open(this);event(J.obj("opened",true));return;}
    manager=AppUpdateManager.get(this);AppSettings.put(this,"updateAutoCheck","false");AppUpdates.schedule(this);
    if("verifyAccess".equals(action)){try{Bundle status=AppUpdates.call(this,"status",null);Uri uri=Uri.parse(status.getString("uri"));try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);if(!AppUpdatePolicy.hash(out.toByteArray()).equals(manager.info.sha))throw new IOException("Provider bytes differ");}
      boolean readOnly=false,traversal=false;try{getContentResolver().openFileDescriptor(uri,"rw");}catch(FileNotFoundException e){readOnly=true;}try{getContentResolver().openFileDescriptor(AppUpdates.uri(this).buildUpon().appendPath("..").appendPath("chat.db").build(),"r");}catch(FileNotFoundException e){traversal=true;}
      event(J.obj("readOnly",readOnly,"traversalRejected",traversal,"sameSigner",true,"installedVersion",AppVersion.name(this),"packageVersion",AppUpdateFiles.installed(this)));
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}return;}
    try{
      hash=intent.getStringExtra("updateHash");long bytes=intent.getLongExtra("updateBytes",0);if(hash==null||bytes<=0)throw new IOException("Missing synthetic fixture identity");
      JSONObject metadata=J.obj("schema",1,"package","local.pocketchat","version","99.0.0","versionCode",AppUpdateFiles.installed(this)+1,"bytes",bytes,"sha256",hash,"signerSha256",AppUpdatePolicy.SIGNER,"downloadUrl",AppUpdatePolicy.asset("99.0.0"),"abi","arm64-v8a","minSdk",26,"notes","受控安装包；测试不会实际安装。");
      manager.worker.execute(()->{try{manager.removeDownload();manager.clearFiles();manager.info=new AppUpdateInfo(metadata);manager.raw=metadata.toString();File external=new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),"fixture-"+action+".download");external.delete();String path="good".equals(action)?"/update-apk":"badSigner".equals(action)?"/update-wrong-signer":"badHash".equals(action)?"/update-corrupt":"/update-wait";
        DownloadManager.Request request=new DownloadManager.Request(Uri.parse("http://127.0.0.1:8765"+path)).setDestinationUri(Uri.fromFile(external)).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);manager.generation.incrementAndGet();manager.id=manager.downloads.enqueue(request);manager.change("downloading","");handler.post(()->{started=SystemClock.elapsedRealtime();if("cancel".equals(action))AppUpdates.call(this,"cancel",null);waitResult();});
      }catch(Exception e){handler.post(()->event(J.obj("error",String.valueOf(e))));}});
    }catch(Exception e){event(J.obj("error",String.valueOf(e)));}
  }
  void waitResult(){Bundle status=AppUpdates.call(this,"status",null);String state=status.getString("state");if("ready".equals(state)||"available".equals(state)){event(J.obj("action",action,"state",state,"message",status.getString("message"),"uri",status.getString("uri",""),"downloadId",manager.downloadId()));return;}if(SystemClock.elapsedRealtime()-started>60000){event(J.obj("error","DownloadManager did not finish","state",state,"message",status.getString("message")));return;}handler.postDelayed(this::waitResult,200);}
  void event(JSONObject result){Log.i("PocketAppUpdateIntegration",result.toString());}
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
