package local.pocketchat;

import android.app.AlertDialog;
import android.content.Context;
import android.text.InputType;
import android.text.TextUtils;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

/** Native address controls; never inspect or modify the website's inputs. */
final class GeckoAddressUi {
  final MainActivity a;final BrowserAddressRow row;final Button address,home,back,forward,reload;
  private AlertDialog dialog;private EditText editor;private String shown="";
  GeckoAddressUi(MainActivity activity){
    a=activity;
    back=BrowserToolbarUi.action(a,"back","后退",()->a.browserHistory(-1));
    forward=BrowserToolbarUi.action(a,"chevron-right","前进",()->a.browserHistory(1));
    address=DesignUi.button(a,"网址或搜索",false,()->show(a));address.setAllCaps(false);address.setTextSize(14);address.setSingleLine(true);address.setEllipsize(TextUtils.TruncateAt.END);address.setGravity(android.view.Gravity.CENTER_VERTICAL);address.setPadding(a.dp(12),a.dp(8),a.dp(12),a.dp(8));
    address.setMinWidth(0);address.setMinimumWidth(0);address.setMinHeight(a.dp(48));address.setIncludeFontPadding(true);address.setBackground(DesignUi.glass(a,24));GlassMotion.press(address,false);
    address.setOnLongClickListener(v->{a.chooseEnvironment();return true;});
    reload=BrowserToolbarUi.action(a,"refresh","刷新网页",a::browserReloadOrStop);
    home=BrowserToolbarUi.action(a,"home","打开当前环境主页",()->home(a));
    row=new BrowserAddressRow(a,address,back,forward,reload,home);
    row.setPadding(0,a.dp(3),0,a.dp(7));row.setClipChildren(false);row.setClipToPadding(false);refresh();
  }
  String target(){if(a.session==null)return "";String url=a.session.navigating?a.session.navigationTarget:a.session.web.getUrl();return url==null?"":url;}
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

  /** Reflow the existing controls without rebuilding views or changing text size. */
  static final class BrowserAddressRow extends ViewGroup {
    final Button address;final Button[] actions;boolean stacked;
    BrowserAddressRow(Context context,Button address,Button back,Button forward,Button reload,Button home){
      super(context);this.address=address;actions=new Button[]{back,forward,reload,home};
      addView(back);addView(forward);addView(address);addView(reload);addView(home);
    }
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    int readableAddressWidth(){
      String text=address.getText().toString();int start=text.indexOf("://");start=start<0?0:start+3;
      int end=text.length();for(char separator:new char[]{'/', '?', '#'}){int index=text.indexOf(separator,start);if(index>=0)end=Math.min(end,index);}
      // Reserve the ellipsis too, so a long path cannot consume the last host
      // characters. The actual TextPaint already includes Android font scaling.
      int host=(int)Math.ceil(address.getPaint().measureText(text.substring(0,end)+"…"));
      return Math.max(dp(160),host+address.getCompoundPaddingLeft()+address.getCompoundPaddingRight());
    }
    @Override protected void onMeasure(int widthSpec,int heightSpec){
      int action=dp(48),minimum=readableAddressWidth();
      int width=resolveSize(getPaddingLeft()+getPaddingRight()+4*action+minimum,widthSpec);
      int available=Math.max(0,width-getPaddingLeft()-getPaddingRight());
      stacked=available-4*action<minimum;
      int addressWidth=stacked?available:available-4*action;
      address.measure(MeasureSpec.makeMeasureSpec(addressWidth,MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));
      int actionSpec=MeasureSpec.makeMeasureSpec(action,MeasureSpec.EXACTLY);
      for(Button button:actions)button.measure(actionSpec,actionSpec);
      int content=stacked?address.getMeasuredHeight()+dp(4)+action:Math.max(address.getMeasuredHeight(),action);
      setMeasuredDimension(width,resolveSize(getPaddingTop()+content+getPaddingBottom(),heightSpec));
    }
    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
      int start=getPaddingLeft(),end=right-left-getPaddingRight(),y=getPaddingTop();
      int action=actions[0].getMeasuredWidth(),addressHeight=address.getMeasuredHeight();
      int content=stacked?addressHeight:Math.max(addressHeight,action);
      int addressTop=y+(content-addressHeight)/2;
      int addressLeft=stacked?start:start+2*action;
      address.layout(addressLeft,addressTop,stacked?end:end-2*action,addressTop+addressHeight);
      int actionTop=stacked?y+addressHeight+dp(4):y+(content-action)/2;
      for(int i=0;i<actions.length;i++){
        int x=i<2?start+i*action:end-(4-i)*action;
        actions[i].layout(x,actionTop,x+action,actionTop+action);
      }
    }
  }
  // ChatGPT is the default website in this browser, so it has the same controls.
  static boolean visibleFor(String url){return true;}
  void refresh(){
    String url=current();if(row.getVisibility()!=View.VISIBLE)row.setVisibility(View.VISIBLE);
    if(!shown.equals(url)){shown=url;String text=url.startsWith("https://")?url.substring(8):url;address.setText(text.isEmpty()?"网址或搜索":text);address.setContentDescription("当前网址 "+url+"，点击输入网址或搜索");address.setTooltipText(url);}
    BrowserToolbarUi.enabled(back,a.remote!=null&&a.remote.canGoBack());
    BrowserToolbarUi.enabled(forward,a.remote!=null&&a.remote.canGoForward());
    boolean loading=a.session!=null&&a.session.navigating;
    BrowserToolbarUi.action(reload,loading?"close":"refresh",loading?"停止加载":"刷新网页");
  }
  static boolean available(MainActivity a){return a!=null&&!a.destroyed&&!a.isFinishing()&&a.session!=null&&a.remote!=null;}
  static void show(MainActivity a){
    if(!available(a))return;GeckoAddressUi owner=a.geckoAddress;if(owner==null)return;if(owner.dialog!=null&&owner.dialog.isShowing()){owner.focusEditor(false);return;}
    LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    EditText input=DesignUi.input(box,"",owner.current(),"输入网址或搜索内容");input.setContentDescription("网址或搜索");input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);input.setSingleLine(true);input.setImeOptions(EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_EXTRACT_UI);
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setVisibility(View.GONE);notice.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("打开网址").setView(box).setPositiveButton("前往",null).setNeutralButton("主页",null).setNegativeButton("取消",null).create();owner.dialog=dialog;owner.editor=input;
    Runnable submit=()->{if(!available(a)||owner.dialog!=dialog||!dialog.isShowing())return;try{String raw=input.getText().toString();String url=raw.trim().isEmpty()?BrowserPreferences.home(a):GeckoNavigationPolicy.normalizeInput(raw);long before=a.session.navigationEpoch;a.session.browse(url,"正在打开网页…");if(a.session.navigationEpoch!=before&&a.session.navigating&&url.equals(a.session.navigationTarget)){dialog.dismiss();a.showPage(true);owner.refresh();}else{notice.setText(a.session.status);notice.setVisibility(View.VISIBLE);}}catch(IllegalArgumentException invalid){notice.setText(invalid.getMessage());notice.setVisibility(View.VISIBLE);input.setError(invalid.getMessage());}};
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
  private void focusEditor(boolean selectAll){
    AlertDialog opened=dialog;EditText input=editor;if(opened==null||!opened.isShowing()||input==null)return;
    input.requestFocus();if(selectAll)input.selectAll();input.post(()->showKeyboard(opened,input));
  }
  private void showKeyboard(AlertDialog opened,EditText input){
    if(!available(a)||dialog!=opened||editor!=input||!opened.isShowing()||!input.hasWindowFocus()||!input.isFocused())return;
    InputMethodManager keyboard=(InputMethodManager)a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
    if(keyboard!=null)keyboard.showSoftInput(input,InputMethodManager.SHOW_IMPLICIT);
  }
  static void home(MainActivity a){if(!available(a))return;a.session.browse(BrowserPreferences.home(a),"正在打开主页…");a.showPage(true);if(a.geckoAddress!=null)a.geckoAddress.refresh();}
  static boolean closeBlocked(MainActivity a){return a.session.pending!=null||a.session.submitting||a.session.operation||a.session.resourceChoosers>0||a.session.resourceFilePreparations>0||a.session.transferActive;}
  static void closeSites(MainActivity a){
    if(!available(a))return;
    if(closeBlocked(a)){a.status("请先完成回复或暂停文件操作，再关闭网站");return;}
    AppAppearance.dialog(a).setTitle("关闭网站并返回 ChatGPT？").setMessage("将关闭此环境 Gecko 中的全部网页和弹出页，未保存的网页输入或上传可能丢失。登录数据和指纹设置会保留，等待中的线路配置可以继续应用。").setNegativeButton("保留网页",null).setPositiveButton("关闭网站",(d,w)->{
      long epoch=a.session.navigationEpoch;Object surface=a.remote.current;
      a.session.pageMemory.capture(()->{if(!available(a)||a.session.navigationEpoch!=epoch||a.remote.current!=surface)return;if(closeBlocked(a)){a.status("网页任务已变化，请完成或暂停后再关闭网站");return;}a.remote.closeWebsitePages();a.session.browse(MainActivity.ORIGIN,"正在返回 ChatGPT…");a.showPage(true);if(a.geckoAddress!=null)a.geckoAddress.refresh();});
    }).show();
  }
  void close(){if(dialog!=null)dialog.dismiss();dialog=null;editor=null;}
}
