package local.pocketchat;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;

public class MediaTestActivity extends MainActivity {
 JSONArray checks=new JSONArray();int selections=0;
 void check(String n,boolean p){checks.put(J.obj("name",n,"pass",p));}
 @Override void startNetwork(){networkReady=true;session.networkReady=true;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);remote.loadUrl(ORIGIN);}
 @Override WebViewClient remoteClient(){return new WebViewClient(){@Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture-media.html"));}catch(Exception e){return blocked();}}};}
 @Override public void startActivityForResult(Intent intent,int request){if(request==74){selections++;handler.postDelayed(()->onActivityResult(74,RESULT_OK,new Intent().setData(Uri.parse("content://local.pocketchat.fixturefiles/"+(selections==1?"document.pdf":"image.png")))),250);}else super.startActivityForResult(intent,request);}
 @Override public void onCreate(Bundle b){getSharedPreferences("chat",0).edit().clear().commit();super.onCreate(b);setRequestedOrientation(1);handler.postDelayed(()->begin(),4000);}
 void begin(){attachments.open("file");handler.postDelayed(()->{check("Pending upload blocks premature send",attachments.blocked());},600);handler.postDelayed(()->{check("PDF file chooser reached native callback",selections==1);check("PDF confirmed ready",attachments.hasFiles()&&!attachments.blocked());remote.evaluateJavascript("window.uploadReadCount",s->{check("WebView reads selected content URI bytes","1".equals(s));attachments.open("image");handler.postDelayed(()->second(),5000);});},5000);}
 void second(){check("Image and PDF coexist in composer",aCount()==2&&!attachments.blocked());remote.evaluateJavascript("window.uploadReadCount",s->{check("Both files read by renderer","2".equals(s));attachments.remove("fixture-document.pdf");handler.postDelayed(()->{check("Remove verified in web and native composer",aCount()==1&&!session.attachments.toString().contains("fixture-document.pdf"));attachments.retry(session.attachments.optJSONObject(0));handler.postDelayed(()->{check("Retry retains one file and becomes ready",aCount()==1&&!attachments.blocked());remote.evaluateJavascript("window.uploadReadCount",r->check("Retry reuses saved URI through standard chooser callback","3".equals(r)));input.setText("");sendPrompt();sendPrompt();handler.postDelayed(()->finishCheck(),7500);},5500);},2000);});}
 int aCount(){return session.attachments.length();}
 void finishCheck(){remote.evaluateJavascript("window.sendCount",s->{check("Attachment message sends exactly once","1".equals(s));check("Confirmed message clears attachment chips",aCount()==0);check("Reply completes with attachment metadata",session.pending==null);boolean saved=false;for(String key:prefs.getAll().keySet())if(key.startsWith("preview:")&&key.endsWith("fixture-image.png"))saved=true;check("Sent attachment retains local preview reference",saved);check("Attachment-only message keeps its filename",session.entries.toString().contains("fixture-image.png"));try{J.write(new File(getFilesDir(),"media-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}});}
}

