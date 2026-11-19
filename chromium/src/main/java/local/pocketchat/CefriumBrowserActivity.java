package local.pocketchat;

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.cefrium.Cefrium;
import com.cefrium.CefriumBrowser;
import com.cefrium.CefriumChromeClient;
import com.cefrium.CefriumFileChooserCallback;
import com.cefrium.CefriumFileChooserParams;
import com.cefrium.CefriumLoadError;
import com.cefrium.CefriumNavigationClient;
import com.cefrium.CefriumNavigationRequest;
import com.cefrium.CefriumProfile;
import java.io.IOException;

/** Hosts Chromium in the main process with an explicit environment identity. */
public final class CefriumBrowserActivity extends ThemedActivity {
  private static final int NAVIGATION_ABORTED = -3;
  private EnvironmentSpec.Identity identity;
  private Context environment;
  private FrameLayout surface;
  private EditText address;
  private TextView status;
  private CefriumRoute route;
  private CefriumBrowser browser;
  private CefriumFiles files;
  private boolean foreground;
  private String pendingAddress;
  private long navigationRequest;
  private Runnable untrackProfile;

  @Override protected void onCreate(Bundle state){
    super.onCreate(state);
    if(Build.VERSION.SDK_INT<29||!getPackageName().equals(Application.getProcessName())){finish();return;}
    try{identity=ChromiumEntry.identity(this,getIntent());}
    catch(IOException unavailable){finish();return;}
    environment=Profiles.context(this,identity.slot);
    String opening=getIntent().getStringExtra("url");
    if(!BrowserAddressPolicy.allowed(opening))opening=BrowserPreferences.home(environment);
    createScreen(opening);
    route=new CefriumRoute(environment,identity,this::routeLost);
    files=new CefriumFiles(this,environment,route::allows,()->foreground,this::message);
    pendingAddress=opening;
  }

  private void createScreen(String opening){
    LinearLayout root=DesignUi.screen(this);
    TextView title=DesignUi.text(this,Profiles.display(this,identity.slot),15,DesignUi.MUTED);
    root.addView(title,new LinearLayout.LayoutParams(-1,-2));
    status=DesignUi.text(this,"",13,DesignUi.MUTED);
    root.addView(status,new LinearLayout.LayoutParams(-1,-2));
    surface=new FrameLayout(this);
    root.addView(surface,new LinearLayout.LayoutParams(-1,0,1));
    address=DesignUi.input(root,"网址或搜索词",opening,"搜索或输入网址");
    address.setImeOptions(EditorInfo.IME_ACTION_GO);
    address.setOnEditorActionListener((view,action,event)->{
      if(action!=EditorInfo.IME_ACTION_GO)return false;
      navigate(address.getText().toString());return true;
    });
    LinearLayout controls=new LinearLayout(this);
    controls.addView(DesignUi.button(this,"主页",false,()->navigate(BrowserPreferences.home(environment))),new LinearLayout.LayoutParams(0,-2,1));
    controls.addView(DesignUi.button(this,"打开",true,()->navigate(address.getText().toString())),new LinearLayout.LayoutParams(0,-2,1));
    controls.addView(DesignUi.button(this,"环境设置",false,this::settings),new LinearLayout.LayoutParams(0,-2,1));
    root.addView(controls,new LinearLayout.LayoutParams(-1,-2));
    setContentView(root);
  }

  private boolean stillSelected(){
    try{return identity.equals(ChromiumEntry.identity(this,getIntent()));}
    catch(IOException unavailable){return false;}
  }
  private void navigate(String input){
    if(isFinishing()||route==null)return;
    if(!stillSelected()){finish();return;}
    final String url;
    try{url=BrowserAddressPolicy.normalizeInput(input);}
    catch(IllegalArgumentException invalid){message("请输入可访问的公开网址");return;}
    if(!BrowserAddressPolicy.allowed(url)){message("请输入可访问的公开网址");return;}
    if(browser!=null){loadPage(url);return;}
    pendingAddress=url;
    if(!foreground)return;
    CefriumRoute selected=route;
    long request=++navigationRequest;
    message("正在核对此环境的网络…");
    selected.open(url,ready->{
      if(route!=selected||isFinishing()||isDestroyed()||request!=navigationRequest||!foreground)return;
      pendingAddress=null;
      if(!ready||!selected.mayStart(url)){message(selected.blockedReason());return;}
      if(!stillSelected()){finish();return;}
      if(browser==null&&!startEngine())return;
      loadPage(url);
    });
  }
  private void loadPage(String url){
    if(!route.allows(url)){routeLost();return;}
    files.navigation(browser);message("");browser.loadUrl(url);
  }
  private boolean startEngine(){
    try{
      ChromiumProfileCleanup.holdEngine(this);
      CefriumRoute.configureEngine();
      Cefrium.setDataDirectory(ChromiumProfileCleanup.dataDirectory(this));
      if(!Cefrium.initialize(getApplicationContext())){message("Chromium 组件暂时无法启动");return false;}
      if(untrackProfile==null)untrackProfile=CefriumProfileLifecycle.track(environment,identity,this::stopForProfileMaintenance);
      CefriumProfile profile=CefriumProfile.get(ChromiumEntry.profileName(identity));
      route.prepare(profile);
      CefriumBrowser created=CefriumBrowser.createWithSurface(this,profile);
      browser=created;
      route.attach(created);files.bind(created);
      created.setNavigationClient(new CefriumNavigationClient(){
        @Override public boolean onBeforeNavigate(CefriumBrowser source,CefriumNavigationRequest request){
          if(source!=browser||route==null)return true;
          String destination=request.getUrl();
          if(request.isForMainFrame()&&request.hasGesture()){
            destination=CefriumFiles.downloadAddress(source.getUrl(),destination);
          }
          if(!route.allows(destination))return true;
          if(request.isForMainFrame())files.navigation(source);
          return false;
        }
        @Override public void onUrlChanged(CefriumBrowser source,String url){
          if(source==browser&&BrowserAddressPolicy.allowed(url))address.setText(url);
        }
        @Override public void onLoadError(CefriumBrowser source,CefriumLoadError error){
          if(source==browser&&error!=null&&error.getErrorCode()!=NAVIGATION_ABORTED)message("网页加载失败，请检查连接或重试");
        }
        @Override public void onHttpAuthRequest(CefriumBrowser source,String host,String realm,int port,
                                                boolean proxy,CefriumBrowser.HttpAuthCallback callback){
          if(callback!=null&&(source!=browser||route==null||!route.authenticate(source,host,realm,port,proxy,callback)))
            callback.cancel();
        }
      });
      created.setChromeClient(new CefriumChromeClient(){
        @Override public boolean onShowFileChooser(CefriumBrowser source,CefriumFileChooserParams parameters,CefriumFileChooserCallback callback){
          if(source!=browser||files==null){if(callback!=null)callback.cancel();return true;}
          return files.choose(source,parameters,callback);
        }
      });
      // False keeps the SDK's same-browser fallback, including its download client.
      created.setPopupHandler((target,userGesture)->{
        if(!userGesture||!foreground||browser!=created||route==null||!stillSelected())return true;
        return !route.allows(CefriumFiles.downloadAddress(created.getUrl(),target));
      });
      surface.addView(created.getSurfaceContainer(),new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT));
      return true;
    }catch(IOException|RuntimeException|LinkageError unavailable){
      retireBrowser();message("Chromium 组件运行失败，请重新打开此环境");return false;
    }
  }
  private void message(String value){status.setText(value);}
  private void routeLost(){
    if(isDestroyed()||isFinishing()||route==null)return;
    navigationRequest++;
    pendingAddress=null;
    if(files!=null)files.routeLost();
    retireBrowser();message(route.blockedReason());
  }
  private void retireBrowser(){
    CefriumBrowser current=browser;browser=null;
    if(route!=null)route.retire(current);
    if(current==null)return;
    files.retire(current);
    surface.removeAllViews();
    current.close();
  }
  private void settings(){
    if(isFinishing()||files==null)return;
    if(files.busy()){message("请先完成当前文件操作");return;}
    if(!stillSelected()){finish();return;}
    startActivity(new Intent(this,Profiles.activity(identity.slot)).putExtra("openWindowAction","settings")
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    finish();
  }
  @Override protected void onActivityResult(int request,int result,Intent data){
    super.onActivityResult(request,result,data);
    if(files!=null)files.result(request,result,data);
  }
  @Override public void onBackPressed(){
    if(browser!=null&&browser.canGoBack()&&route.allows(browser.getUrl())){files.navigation(browser);browser.goBack();}
    else super.onBackPressed();
  }
  @Override protected void onResume(){
    super.onResume();if(identity==null||isFinishing())return;
    if(!stillSelected()){finish();return;}
    foreground=true;
    if(browser!=null)browser.onResume();
    if(pendingAddress!=null)navigate(pendingAddress);
  }
  @Override protected void onPause(){
    foreground=false;
    navigationRequest++;
    if(browser!=null)browser.onPause();
    super.onPause();
  }
  private void stopForProfileMaintenance(){
    closeBrowserSession();
    finish();
  }
  private void closeBrowserSession(){
    navigationRequest++;
    pendingAddress=null;
    retireBrowser();
    if(route!=null){route.close();route=null;}
    if(files!=null){files.close();files=null;}
    if(untrackProfile!=null){untrackProfile.run();untrackProfile=null;}
  }
  @Override protected void onDestroy(){
    closeBrowserSession();
    super.onDestroy();
  }
}
