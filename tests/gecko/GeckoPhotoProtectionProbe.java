package local.pocketchat;

import android.os.SystemClock;
import org.json.JSONObject;

/** Actual Gecko Canvas output without ever opening an Android file chooser. */
final class GeckoPhotoProtectionProbe {
  static void run(GeckoIntegrationTestActivity activity,long serial){
    ChatSession session=activity.session;int prior=session.privacy.level();
    session.prefs.edit().putInt("privacyLevel",2).commit();
    session.reading.configure(true);session.web.configure(true,2);
    android.webkit.WebChromeClient previous=session.web.chrome;
    final boolean[] chooser={false};
    session.web.setWebChromeClient(new android.webkit.WebChromeClient(){
      @Override public boolean onShowFileChooser(android.webkit.WebView web,android.webkit.ValueCallback<android.net.Uri[]> callback,FileChooserParams params){chooser[0]=true;callback.onReceiveValue(null);return true;}
    });
    String target="http://127.0.0.1:8765/browser-image?command="+serial+"&nonce="+activity.eventStore.nonce+"&privacy=2&mode=probe";
    session.web.loadUrl(target);
    poll(activity,serial,SystemClock.elapsedRealtime()+25000,target,prior,chooser,previous);
  }
  static void restore(ChatSession session,int prior,android.webkit.WebChromeClient previous){session.web.setWebChromeClient(previous);session.prefs.edit().putInt("privacyLevel",prior).commit();session.web.configure(true,prior);}
  static void poll(GeckoIntegrationTestActivity activity,long serial,long deadline,String target,int prior,boolean[] chooser,android.webkit.WebChromeClient previous){
    if(serial!=activity.run)return;
    ChatSession session=activity.session;
    session.web.evaluateJavascript("(()=>({ready:location.href==="+JSONObject.quote(target)+",value:document.getElementById('upload-result')?.textContent||'',photoEvidence:window.photoEvidence||null}))()",raw->{
      if(serial!=activity.run)return;
      JSONObject current=J.parse(raw);String value=current.optString("value");
      if(current.optBoolean("ready")&&value.equals("protected:no-selection")){
        GeckoWebView web=(GeckoWebView)session.web;
        JSONObject result=J.obj("chooserOpened",chooser[0],"upload",value,"nativePrivacyReady",web.privacyReady,"nativePrivacyLevel",web.protectionLevel,"nativeFingerprintingProtected",web.fingerprintingProtected,"photoEvidence",current.optJSONObject("photoEvidence"));
        restore(session,prior,previous);activity.event(serial,"photoProtectionProbe",result);return;
      }
      if(value.startsWith("error:")||SystemClock.elapsedRealtime()>deadline){restore(session,prior,previous);activity.event(serial,"error",J.obj("error","unselected photo privacy probe failed","result",raw,"chooserOpened",chooser[0]));return;}
      session.handler.postDelayed(()->poll(activity,serial,deadline,target,prior,chooser,previous),100);
    });
  }
}
