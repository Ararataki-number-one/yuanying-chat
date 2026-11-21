package local.pocketchat;

import android.app.AlertDialog;
import android.text.InputType;
import android.text.TextUtils;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

/** Native address controls; never inspect or modify the website's inputs. */
final class GeckoAddressUi {
  final MainActivity a;final BrowserToolbarUi.NavigationBar row;final Button address,home,windows,tools,menu;
  private final AiDiagnosticUi aiDiagnostics;
  private AlertDialog dialog;private EditText editor;private String shown="";
  GeckoAddressUi(MainActivity activity){
    a=activity;
    aiDiagnostics=AiDiagnosticUi.enabled(activity)?new AiDiagnosticUi(activity):null;
    address=DesignUi.button(a,"网址或搜索",false,()->show(a));address.setAllCaps(false);address.setEllipsize(TextUtils.TruncateAt.END);address.setGravity(android.view.Gravity.CENTER_VERTICAL);
    BrowserToolbarUi.address(address);GlassMotion.press(address,false);
    home=BrowserToolbarUi.action(a,"home","打开当前环境主页",()->home(a));
    windows=BrowserToolbarUi.action(a,"window","网页窗口",a::windowsSheet);
    tools=BrowserToolbarUi.action(a,"grid","网页工具",a::toolsSheet);
    if(aiDiagnostics!=null)tools.setOnLongClickListener(view->{aiDiagnostics.show();return true;});
    menu=BrowserToolbarUi.action(a,"more","浏览器菜单",a::moreSheet);
    row=new BrowserToolbarUi.NavigationBar(a,address,home,windows,tools,menu);refresh();
  }
  String target(){if(a.session==null)return "";String url=a.session.browserDisplayUrl();return url==null?"":url;}
  String current(){
    String url=target();
    // A cold Gecko surface reports about:blank before it has a document. Keep
    // the intended destination editable, but never relabel a visible blank page.
    if(url.isEmpty()||"about:blank".equals(url)&&a.session!=null&&!a.session.web.hasVisibleDocument()){
      String resume=a.session==null?BrowserPreferences.home(a):a.session.resumeUrl();
      return resume==null||resume.isEmpty()||"about:blank".equals(resume)?BrowserPreferences.home(a):resume;
    }
    return url;
  }

  // ChatGPT is the default website in this browser, so it has the same controls.
  static boolean visibleFor(String url){return true;}
  static boolean canForward(MainActivity a){return available(a)&&a.remote.canGoForward();}
  void refresh(){
    String url=current();if(row.getVisibility()!=View.VISIBLE)row.setVisibility(View.VISIBLE);
    if(!shown.equals(url)){shown=url;String text=url.startsWith("https://")?url.substring(8):url;address.setText(text.isEmpty()?"网址或搜索":text);address.setContentDescription("当前网址 "+url+"，点击输入网址或搜索");address.setTooltipText(url);}
  }
  static boolean available(MainActivity a){
    // A retained session can already belong to a replacement Activity while
    // this host still has a pending dialog or page-capture callback.
    return a!=null&&!a.destroyed&&!a.isFinishing()&&a.session!=null&&a.remote!=null
      &&a.remote==a.session.web&&a.remote.displayContext.getBaseContext()==a;
  }
  static void show(MainActivity a){
    if(!available(a))return;GeckoAddressUi owner=a.geckoAddress;if(owner==null)return;if(a.designChrome!=null)a.designChrome.reveal();if(owner.dialog!=null&&owner.dialog.isShowing()){owner.focusEditor(false);return;}
    LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    EditText input=DesignUi.input(box,"",owner.current(),"输入网址或搜索内容");input.setContentDescription("网址或搜索");input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);input.setSingleLine(true);input.setImeOptions(EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_EXTRACT_UI);
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setVisibility(View.GONE);notice.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("打开网址").setView(box).setPositiveButton("前往",null).setNeutralButton("主页",null).setNegativeButton("取消",null).create();owner.dialog=dialog;owner.editor=input;
    Runnable submit=()->owner.submitAddress(dialog,input,notice);
    // Keep the compact address form anchored while the keyboard changes the
    // available height; repeated headings and an empty error row waste that space.
    dialog.getWindow().setGravity(android.view.Gravity.TOP|android.view.Gravity.CENTER_HORIZONTAL);
    dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
    dialog.show();
    // The shared form styling runs on attachment and changes a final field to DONE.
    input.setImeOptions((input.getImeOptions()&~EditorInfo.IME_MASK_ACTION)|EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_EXTRACT_UI);
    final ViewTreeObserver focusObserver=input.getViewTreeObserver();
    ViewTreeObserver.OnWindowFocusChangeListener focus=new ViewTreeObserver.OnWindowFocusChangeListener(){
      @Override public void onWindowFocusChanged(boolean focused){
        if(focused){owner.showKeyboard(dialog,input);if(focusObserver.isAlive())focusObserver.removeOnWindowFocusChangeListener(this);}
      }
    };
    focusObserver.addOnWindowFocusChangeListener(focus);
    final android.os.IBinder inputWindow=input.getWindowToken();
    dialog.setOnDismissListener(ignored->{
      if(focusObserver.isAlive())focusObserver.removeOnWindowFocusChangeListener(focus);
      // Hide only this native dialog's keyboard; never focus or edit a website input.
      InputMethodManager keyboard=(InputMethodManager)a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
      if(keyboard!=null&&inputWindow!=null)keyboard.hideSoftInputFromWindow(inputWindow,0);
      if(owner.dialog==dialog)owner.dialog=null;if(owner.editor==input)owner.editor=null;
    });
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->submit.run());dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{input.setText(BrowserPreferences.home(a));submit.run();});
    input.setOnEditorActionListener((v,action,event)->{if(action==EditorInfo.IME_ACTION_GO||event!=null&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER&&event.getAction()==KeyEvent.ACTION_DOWN){submit.run();return true;}return false;});
    owner.focusEditor(true);
  }
  private void submitAddress(AlertDialog opened,EditText input,TextView notice){
    if(!available(a)||dialog!=opened||!opened.isShowing())return;
    try{
      String raw=input.getText().toString();
      String url=raw.trim().isEmpty()?BrowserPreferences.home(a):GeckoNavigationPolicy.normalizeInput(raw);
      // Acceptance is explicit. Loading state may already have changed, and an
      // offline destination is still a valid browser command.
      if(a.session.browse(url,"正在打开网页…")){
        opened.dismiss();
        a.showPage(true);
        refresh();
      }else{
        notice.setText(a.session.status);
        notice.setVisibility(View.VISIBLE);
      }
    }catch(IllegalArgumentException invalid){
      notice.setText(invalid.getMessage());
      notice.setVisibility(View.VISIBLE);
      input.setError(invalid.getMessage());
    }
  }
  private void focusEditor(boolean selectAll){
    AlertDialog opened=dialog;EditText input=editor;if(opened==null||!opened.isShowing()||input==null)return;
    input.requestFocus();if(selectAll)input.selectAll();input.post(()->showKeyboard(opened,input));
  }
  private void showKeyboard(AlertDialog opened,EditText input){
    if(!available(a)||dialog!=opened||editor!=input||!opened.isShowing()||!input.hasWindowFocus()||!input.isFocused())return;
    InputMethodManager keyboard=(InputMethodManager)a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
    if(keyboard!=null)keyboard.showSoftInput(input,InputMethodManager.SHOW_IMPLICIT);
  }
  static void home(MainActivity a){
    if(!available(a)||!a.session.browse(BrowserPreferences.home(a),"正在打开主页…"))return;
    a.showPage(true);
    if(a.geckoAddress!=null)a.geckoAddress.refresh();
  }
  static void closeSites(MainActivity a){
    if(!available(a))return;
    AppAppearance.dialog(a).setTitle("关闭网站并返回 ChatGPT？").setMessage("将关闭此环境 Gecko 中的全部网页和弹出页，未保存的网页输入或上传可能丢失。登录数据和指纹设置会保留，等待中的线路配置可以继续应用。").setNegativeButton("保留网页",null).setPositiveButton("关闭网站",(d,w)->{
      if(!available(a))return;
      ChatSession owner=a.session;
      Object surface=a.remote.current;
      long epoch=owner.prepareBrowserNavigation();
      if(epoch<0)return;
      owner.pageMemory.captureForNavigation(()->{
        if(!available(a)||a.session!=owner||owner.navigationEpoch!=epoch||a.remote.current!=surface){
          owner.cancelBrowserNavigation(epoch);
          return;
        }
        if(!a.remote.closeWebsitePages())return;
        // Closing a native page can synchronously complete an old callback.
        if(!available(a)||a.session!=owner||owner.navigationEpoch!=epoch){
          owner.cancelBrowserNavigation(epoch);
          return;
        }
        if(!owner.browse(MainActivity.ORIGIN,"正在返回 ChatGPT…"))return;
        a.showPage(true);
        if(a.geckoAddress!=null)a.geckoAddress.refresh();
      });
    }).show();
  }
  void close(){if(aiDiagnostics!=null)aiDiagnostics.close();if(dialog!=null)dialog.dismiss();dialog=null;editor=null;}
}
