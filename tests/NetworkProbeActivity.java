package local.pocketchat;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import androidx.webkit.*;

public class NetworkProbeActivity extends Activity {
  WebView web;boolean finished=false;
  void result(JSONObject json){if(finished)return;finished=true;try{FileOutputStream out=openFileOutput("network-"+(getIntent().getBooleanExtra("expectFailure",false)?"closed":"route")+".json",MODE_PRIVATE);out.write(json.toString(2).getBytes(StandardCharsets.UTF_8));out.close();}catch(Exception ignored){}TextView text=new TextView(this);text.setText(json.toString());setContentView(text);}
  JSONObject fields(Object... pairs){JSONObject o=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)o.put((String)pairs[i],pairs[i+1]);}catch(Exception ignored){}return o;}
  @Override public void onCreate(Bundle b){super.onCreate(b);web=new WebView(this);web.getSettings().setJavaScriptEnabled(true);setContentView(web);boolean expectFailure=getIntent().getBooleanExtra("expectFailure",false);
    if(!WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)){result(fields("pass",false,"reason","Proxy override unsupported"));return;}
    web.setWebViewClient(new WebViewClient(){
      @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame())result(fields("pass",expectFailure,"networkError",e.getErrorCode(),"detail",e.getDescription().toString()));}
      @Override public void onPageFinished(WebView v,String url){if(finished)return;v.evaluateJavascript("document.body.innerText",s->{try{String body=(String)new JSONTokener(s).nextValue();String ip=new JSONObject(body).optString("ip");result(fields("pass",!expectFailure&&ip.equals(getIntent().getStringExtra("expectedIp")),"matchesVerifiedProxyExit",ip.equals(getIntent().getStringExtra("expectedIp")),"usedApplicationProxy",true));}catch(Exception e){result(fields("pass",false,"reason","No IP response"));}});}
    });
    String proxy=getIntent().getStringExtra("proxy");ProxyController.getInstance().setProxyOverride(new ProxyConfig.Builder().addProxyRule(proxy).removeImplicitRules().build(),this::runOnUiThread,()->web.loadUrl("https://api.ipify.org?format=json"));
    new android.os.Handler().postDelayed(()->result(fields("pass",false,"reason","Network probe timeout")),25000);
  }
  @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
