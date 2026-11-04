package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import android.os.*;
import java.io.IOException;
import java.util.ArrayList;
import org.json.*;

/** Validate the collected publications off-main before granting any external read access. */
final class DownloadCollectionShare {
  static void share(Activity activity,SavedFileActions actions,JSONArray selected,Runnable finished){
    if(actions.closed||actions.busy||actions.exporting!=null){SavedFileActions.problem(activity,"请先完成当前文件操作");finished.run();return;}
    if(selected.length()==0){finished.run();return;}
    if(selected.length()>DownloadCollection.LIMIT){SavedFileActions.problem(activity,"收集的文件超过分享上限");finished.run();return;}actions.busy=true;
    actions.worker.execute(()->{
      JSONArray checked=new JSONArray();String problem="";
      try{
        DownloadLibrary library=DownloadLibrary.get(activity);ArrayList<Uri> uris=new ArrayList<>();
        for(int i=0;i<selected.length();i++){JSONObject row=selected.getJSONObject(i);if(!DownloadCollection.eligible(row))throw new IOException("只能分享已保存的文件");uris.add(Uri.parse(row.optString("uri")));}
        SavedFileDeletion.leaseAll(activity,uris,()->{
          for(int i=0;i<selected.length();i++){
            if(actions.closed)throw new IOException("下载页面已关闭");JSONObject prior=selected.getJSONObject(i);Uri uri=Uri.parse(prior.optString("uri"));
            JSONObject saved=library.saved(prior);if(saved==null||!DownloadCollection.eligible(saved))throw new IOException("收集的文件已变化，请移除后重新选择："+DownloadMetadataValues.name(prior));
            try(ParcelFileDescriptor file=activity.getContentResolver().openFileDescriptor(uri,"r")){if(file==null)throw new IOException("文件无法读取："+DownloadMetadataValues.name(saved));}
            checked.put(saved);
          }
          SavedFileDeletion.onMain(actions.main,()->{if(actions.closed||activity.isFinishing()||activity.isDestroyed())return;activity.startActivity(Intent.createChooser(intent(checked),"分享收集的 "+checked.length()+" 个文件"));});return null;
        });
      }catch(Exception error){problem=error.getMessage()==null?"部分文件无法读取，请核对收集篮后重试":error.getMessage();}
      String error=problem;actions.main.post(()->{
        actions.busy=false;if(actions.closed||activity.isFinishing()||activity.isDestroyed())return;finished.run();
        if(!error.isEmpty())SavedFileActions.problem(activity,error);
      });
    });
  }
  static Intent intent(JSONArray rows){
    ArrayList<Uri> uris=new ArrayList<>();for(int i=0;i<rows.length();i++)uris.add(Uri.parse(rows.optJSONObject(i).optString("uri")));
    Intent intent=new Intent(Intent.ACTION_SEND_MULTIPLE).setType(DownloadCollection.mime(rows)).putParcelableArrayListExtra(Intent.EXTRA_STREAM,uris).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    ClipData clip=ClipData.newRawUri("收集的下载文件",uris.get(0));for(int i=1;i<uris.size();i++)clip.addItem(new ClipData.Item(uris.get(i)));intent.setClipData(clip);return intent;
  }
}
