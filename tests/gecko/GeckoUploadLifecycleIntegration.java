package local.pocketchat;

import android.net.Uri;
import android.os.SystemClock;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import java.io.File;
import java.util.HashSet;
import java.util.Set;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;

/** Controlled prompt lifecycle on the actual SDK; not a real ChatGPT upload claim. */
final class GeckoUploadLifecycleIntegration {
  static final class Prompt extends GeckoSession.PromptDelegate.FilePrompt {
    Prompt(){super("controlled-upload-lifecycle","fixture",Type.MULTIPLE,Capture.NONE,new String[]{"text/plain"},new Observer(){});}
  }
  static void run(GeckoIntegrationTestActivity activity,long serial){
    activity.session.web.loadUrl("http://127.0.0.1:8765/browser-usability?command="+serial);
    ready(activity,serial,SystemClock.elapsedRealtime()+25000);
  }
  static void ready(GeckoIntegrationTestActivity activity,long serial,long deadline){
    if(serial!=activity.run)return;
    ChatSession owner=activity.session;
    if(!owner.web.hasVisibleDocument()||owner.navigating||!owner.web.getUrl().equals("http://127.0.0.1:8765/browser-usability?command="+serial)){
      if(SystemClock.elapsedRealtime()>deadline){activity.event(serial,"error",J.obj("error","upload lifecycle fixture did not become ready"));return;}
      owner.handler.postDelayed(()->ready(activity,serial,deadline),100);return;
    }
    GeckoIntegrationTestActivity.FixtureView web=(GeckoIntegrationTestActivity.FixtureView)owner.web;
    WebChromeClient previous=web.chrome;boolean wasVisible=owner.uiVisible;
    Set<String> before=directories(owner);int heldFiles=web.uploadFiles.size();
    final ValueCallback<Uri[]>[] picker=new ValueCallback[1];final int[] completions={0};
    Prompt prompt=new Prompt();
    web.setWebChromeClient(new WebChromeClient(){
      @Override public boolean onShowFileChooser(WebView ignored,ValueCallback<Uri[]> callback,FileChooserParams params){picker[0]=callback;return true;}
    });
    try{
      boolean priorNavigating=owner.navigating,priorDispatched=owner.navigationDispatched;String priorTarget=owner.navigationTarget;
      try{
        // The real loaded fixture supplies document readiness. Only its semantic
        // origin is adapted to exercise the production ChatGPT admission path.
        web.chooserOrigin=true;owner.navigating=true;owner.navigationDispatched=true;owner.navigationTarget=MainActivity.ORIGIN;
        if(!web.canChooseFiles())throw new AssertionError("usable document was rejected by stale navigation bookkeeping");
        owner.navigationDispatched=false;if(web.canChooseFiles())throw new AssertionError("planned replacement admitted its old document");
        owner.navigationDispatched=true;owner.navigationTarget=MainActivity.ORIGIN+"c/different";if(web.canChooseFiles())throw new AssertionError("different navigation target admitted old document");
        owner.navigationTarget=MainActivity.ORIGIN;web.pendingLoads.add(web.current);if(web.canChooseFiles())throw new AssertionError("in-flight document replacement admitted old prompt");
      }finally{web.pendingLoads.remove(web.current);web.chooserOrigin=false;owner.navigating=priorNavigating;owner.navigationDispatched=priorDispatched;owner.navigationTarget=priorTarget;}
      GeckoResult<GeckoSession.PromptDelegate.PromptResponse> result=web.current.getPromptDelegate().onFilePrompt(web.current,prompt);
      result.accept(response->completions[0]++);
      if(picker[0]==null||owner.resourceChoosers!=1||owner.resourceFilePreparations!=0)throw new AssertionError("chooser did not own the file task");
      owner.uiVisible=false;owner.updateBrowserActivity();int pauses=web.resourcePauseCalls;
      if(owner.browserPaused)throw new AssertionError("chooser paused the active SDK");
      picker[0].onReceiveValue(new Uri[]{Uri.parse("content://local.pocketchat.test.upload/document")});
      boolean atomic=owner.resourceChoosers==0&&owner.resourceFilePreparations==1&&!owner.browserPaused&&web.resourcePauseCalls==pauses;
      if(!atomic)throw new AssertionError("picker-to-preparation handoff paused Gecko");
      prompt.getDelegate().onPromptDismiss(prompt);prompt.getDelegate().onPromptDismiss(prompt);
      if(!prompt.isComplete())throw new AssertionError("obsolete SDK prompt stayed incomplete");
      picker[0].onReceiveValue(new Uri[]{Uri.parse("content://local.pocketchat.test.upload/document")});
      if(owner.resourceChoosers!=0||owner.resourceFilePreparations!=1)throw new AssertionError("old chooser callback changed work ownership");
      finish(activity,serial,deadline,web,previous,wasVisible,before,heldFiles,completions,atomic);
    }catch(Throwable failure){web.setWebChromeClient(previous);owner.uiVisible=wasVisible;owner.updateBrowserActivity();activity.event(serial,"error",J.obj("error","upload lifecycle: "+failure));}
  }
  static void finish(GeckoIntegrationTestActivity activity,long serial,long deadline,GeckoIntegrationTestActivity.FixtureView web,WebChromeClient previous,boolean wasVisible,Set<String> before,int heldFiles,int[] completions,boolean atomic){
    ChatSession owner=activity.session;
    if(serial!=activity.run){web.setWebChromeClient(previous);owner.uiVisible=wasVisible;owner.updateBrowserActivity();return;}
    boolean clean=owner.resourceChoosers==0&&owner.resourceFilePreparations==0&&web.uploadFiles.size()==heldFiles&&directories(owner).equals(before);
    if(!clean||completions[0]!=1){
      if(SystemClock.elapsedRealtime()>deadline){web.setWebChromeClient(previous);owner.uiVisible=wasVisible;owner.updateBrowserActivity();activity.event(serial,"error",J.obj("error","upload lifecycle cleanup incomplete","chooser",owner.resourceChoosers,"preparation",owner.resourceFilePreparations,"completions",completions[0]));return;}
      owner.handler.postDelayed(()->finish(activity,serial,deadline,web,previous,wasVisible,before,heldFiles,completions,atomic),100);return;
    }
    web.setWebChromeClient(previous);owner.uiVisible=wasVisible;owner.updateBrowserActivity();
    activity.event(serial,"uploadLifecycle",J.obj("actualGeckoPromptDelegate",true,"controlledPrompt",true,"usableDocumentAdmission",true,"plannedNavigationRejected",true,"differentTargetRejected",true,"inflightNavigationRejected",true,"atomicHandoff",atomic,"dismissedOnce",completions[0]==1,"closedPromptResultIgnored",web.uploadFiles.size()==heldFiles,"preparationCleanup",clean,"realChatGptUploadAcceptance",false));
  }
  static Set<String> directories(ChatSession owner){Set<String> names=new HashSet<>();File[] files=new File(owner.context.getCacheDir(),"gecko-uploads").listFiles();if(files!=null)for(File file:files)names.add(file.getName());return names;}
}
