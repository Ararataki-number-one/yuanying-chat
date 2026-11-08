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
  final MainActivity a;final LinearLayout row;final Button address,home;
  private AlertDialog dialog;private EditText editor;private String shown="";
  GeckoAddressUi(MainActivity activity){
    a=activity;row=DesignUi.row(a);row.setVisibility(View.GONE);row.setPadding(a.dp(10),a.dp(2),a.dp(10),a.dp(4));
    address=DesignUi.button(a,"网址或搜索",false,()->show(a));address.setAllCaps(false);address.setTextSize(13);address.setSingleLine(true);address.setEllipsize(TextUtils.TruncateAt.MIDDLE);address.setGravity(android.view.Gravity.CENTER_VERTICAL);address.setPadding(a.dp(12),a.dp(8),a.dp(12),a.dp(8));
    home=DesignUi.button(a,"主页",false,()->home(a));home.setTextSize(12);home.setSingleLine(true);home.setMinWidth(a.dp(56));home.setMinimumWidth(a.dp(56));home.setPadding(a.dp(6),a.dp(8),a.dp(6),a.dp(8));home.setContentDescription("打开当前环境主页");
    row.addView(address,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-2,-2);hp.leftMargin=a.dp(6);row.addView(home,hp);refresh();
  }
  String target(){if(a.session==null)return "";String url=a.session.navigating?a.session.navigationTarget:a.session.web.getUrl();return url==null?"":url;}
  String current(){String url=target();return url.isEmpty()?(a.session==null?BrowserPreferences.home(a):a.session.resumeUrl()):url;}
  static boolean visibleFor(String url){return GeckoNavigationPolicy.publicWeb(url)&&!MainActivity.chatUrl(url);}
  void refresh(){String url=target();int visibility=visibleFor(url)?View.VISIBLE:View.GONE;if(row.getVisibility()!=visibility)row.setVisibility(visibility);if(visibility==View.GONE)return;String text=(url.startsWith("http:")?"HTTP 未加密 · ":"")+url;if(!shown.equals(text)){shown=text;address.setText(text);address.setContentDescription("当前网址 "+text+"，点击输入网址或搜索");}}
  static boolean available(MainActivity a){return a!=null&&!a.destroyed&&!a.isFinishing()&&a.session!=null&&a.remote!=null;}
  static void show(MainActivity a){
    if(!available(a))return;GeckoAddressUi owner=a.geckoAddress;if(owner==null)return;if(owner.dialog!=null&&owner.dialog.isShowing()){owner.focusEditor(false);return;}
    LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    EditText input=DesignUi.input(box,"网址或搜索",owner.current(),"输入网址或搜索内容");input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);input.setSingleLine(true);input.setImeOptions(EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_EXTRACT_UI);
    // Keep the editor in one parent for its entire focused/IME lifetime.
    LinearLayout inputRow=new LinearLayout(a);inputRow.setOrientation(LinearLayout.HORIZONTAL);inputRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
    box.removeView(input);inputRow.addView(input,new LinearLayout.LayoutParams(0,-2,1));box.addView(inputRow,new LinearLayout.LayoutParams(-1,-2));
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    AlertDialog.Builder builder=AppAppearance.dialog(a);
    // Own only this dialog's heading so it can yield space to the native field.
    // Match the existing Material title's theme and padding at normal heights.
    LinearLayout heading=new LinearLayout(builder.getContext());heading.setOrientation(LinearLayout.HORIZONTAL);
    android.content.res.TypedArray titleStyle=builder.getContext().obtainStyledAttributes(new int[]{android.R.attr.dialogPreferredPadding});
    int titlePadding=titleStyle.getDimensionPixelSize(0,a.dp(24));titleStyle.recycle();
    heading.setPadding(titlePadding,a.dp(18),titlePadding,0);
    TextView title=new TextView(builder.getContext(),null,android.R.attr.windowTitleStyle);title.setText("打开网址");title.setSingleLine(true);title.setEllipsize(TextUtils.TruncateAt.END);heading.addView(title,new LinearLayout.LayoutParams(-1,-2));
    ScrollView form=new ScrollView(a);form.addView(box,new ScrollView.LayoutParams(-1,-2));
    AlertDialog dialog=builder.setTitle("打开网址").setCustomTitle(heading).setView(form).setPositiveButton("前往",null).setNeutralButton("主页",null).setNegativeButton("取消",null).create();owner.dialog=dialog;owner.editor=input;
    Runnable submit=()->{if(!available(a)||owner.dialog!=dialog||!dialog.isShowing())return;try{String raw=input.getText().toString();String url=raw.trim().isEmpty()?BrowserPreferences.home(a):GeckoNavigationPolicy.normalizeInput(raw);long before=a.session.navigationEpoch;a.session.browse(url,"正在打开网页…");if(a.session.navigationEpoch!=before&&a.session.navigating&&url.equals(a.session.navigationTarget)){dialog.dismiss();a.showPage(true);owner.refresh();}else notice.setText(a.session.status);}catch(IllegalArgumentException invalid){notice.setText(invalid.getMessage());input.setError(invalid.getMessage());}};
    dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
    dialog.show();
    // Apply after shared attachment styling; retain a larger native/font minimum.
    AddressDialogLayout.ensureTouchTarget(input,a.dp(48));
    final AddressDialogLayout addressLayout=new AddressDialogLayout(a,dialog,heading,title,box.getChildAt(0),box,inputRow,input,notice,form);
    addressLayout.attach();
    // The shared form styling runs on attachment and changes a final field to DONE.
    input.setImeOptions((input.getImeOptions()&~EditorInfo.IME_MASK_ACTION)|EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_EXTRACT_UI);
    final ViewTreeObserver focusObserver=input.getViewTreeObserver();
    ViewTreeObserver.OnWindowFocusChangeListener focus=new ViewTreeObserver.OnWindowFocusChangeListener(){
      @Override public void onWindowFocusChanged(boolean focused){
        if(focused){owner.showKeyboard(dialog,input);if(focusObserver.isAlive())focusObserver.removeOnWindowFocusChangeListener(this);ViewTreeObserver currentObserver=input.getViewTreeObserver();if(currentObserver!=focusObserver&&currentObserver.isAlive())currentObserver.removeOnWindowFocusChangeListener(this);}
      }
    };
    focusObserver.addOnWindowFocusChangeListener(focus);
    final android.os.IBinder inputWindow=input.getWindowToken();
    dialog.setOnDismissListener(ignored->{
      addressLayout.close();
      if(focusObserver.isAlive())focusObserver.removeOnWindowFocusChangeListener(focus);
      ViewTreeObserver currentObserver=input.getViewTreeObserver();if(currentObserver!=focusObserver&&currentObserver.isAlive())currentObserver.removeOnWindowFocusChangeListener(focus);
      // Hide only this native dialog's keyboard; never focus or edit a website input.
      InputMethodManager keyboard=(InputMethodManager)a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
      if(keyboard!=null&&inputWindow!=null)keyboard.hideSoftInputFromWindow(inputWindow,0);
      if(owner.dialog==dialog)owner.dialog=null;if(owner.editor==input)owner.editor=null;
    });
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->submit.run());dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{input.setText(BrowserPreferences.home(a));submit.run();});
    input.setOnEditorActionListener((v,action,event)->{if(action==EditorInfo.IME_ACTION_GO||event!=null&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER&&event.getAction()==KeyEvent.ACTION_DOWN){submit.run();return true;}return false;});
    owner.focusEditor(true);
  }
  /** React only to native layout/notice events; never poll or touch web inputs. */
  private static final class AddressDialogLayout implements ViewTreeObserver.OnGlobalLayoutListener,View.OnAttachStateChangeListener,android.text.TextWatcher {
    final MainActivity a;final AlertDialog dialog;final LinearLayout heading,box,inputRow;final View label,decor;final TextView title;
    final EditText input;final TextView notice;final ScrollView form;final android.graphics.Rect visible=new android.graphics.Rect();
    final int normalLeft,normalTop,normalRight,normalBottom;
    ViewTreeObserver observer;boolean compact,closed;int titleHeight,labelHeight,emptyNoticeHeight;
    AddressDialogLayout(MainActivity a,AlertDialog dialog,LinearLayout heading,TextView title,View label,LinearLayout box,LinearLayout inputRow,EditText input,TextView notice,ScrollView form){
      this.a=a;this.dialog=dialog;this.heading=heading;this.title=title;this.label=label;this.box=box;this.inputRow=inputRow;this.input=input;this.notice=notice;this.form=form;decor=dialog.getWindow().getDecorView();
      normalLeft=box.getPaddingLeft();normalTop=box.getPaddingTop();normalRight=box.getPaddingRight();normalBottom=box.getPaddingBottom();
    }
    static void ensureTouchTarget(EditText input,int minimum){int height=Math.max(minimum,Math.max(input.getMinHeight(),input.getMinimumHeight()));input.setMinHeight(height);input.setMinimumHeight(height);}
    void attach(){decor.addOnAttachStateChangeListener(this);listen();notice.addTextChangedListener(this);}
    private void listen(){
      if(closed)return;ViewTreeObserver current=decor.getViewTreeObserver();if(current==observer)return;
      if(observer!=null&&observer.isAlive())observer.removeOnGlobalLayoutListener(this);
      // An unattached View's floating observer is merged and killed on attach.
      // Remove the merged registration before binding the live observer once.
      current.removeOnGlobalLayoutListener(this);observer=current;observer.addOnGlobalLayoutListener(this);
    }
    @Override public void onViewAttachedToWindow(View view){listen();}
    @Override public void onViewDetachedFromWindow(View view){close();}
    @Override public void onGlobalLayout(){update();}
    @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
    @Override public void onTextChanged(CharSequence s,int start,int before,int count){}
    @Override public void afterTextChanged(android.text.Editable value){update();}
    void update(){
      if(closed||!dialog.isShowing())return;
      decor.getWindowVisibleDisplayFrame(visible);
      View button=dialog.getButton(AlertDialog.BUTTON_POSITIVE);
      if(button==null||!(button.getParent() instanceof View))return;
      int footer=((View)button.getParent()).getMeasuredHeight();
      if(visible.height()<=0||footer<=0||box.getMeasuredHeight()<=0)return;
      if(!compact){
        titleHeight=heading.getMeasuredHeight();labelHeight=label.getMeasuredHeight();
        if(TextUtils.isEmpty(notice.getText()))emptyNoticeHeight=notice.getMeasuredHeight();
      }
      if(titleHeight<=0||labelHeight<=0)return;
      // ScrollView measures the form at its natural height, even when the
      // platform's AlertDialogLayout gives its middle panel only 71 pixels.
      int normalBody=box.getMeasuredHeight();
      if(compact){normalBody+=normalTop+normalBottom-box.getPaddingTop()-box.getPaddingBottom()+labelHeight-Math.max(0,inputRow.getMeasuredHeight()-input.getMeasuredHeight());if(notice.getVisibility()==View.GONE)normalBody+=emptyNoticeHeight;}
      boolean constrained=visible.height()<titleHeight+normalBody+footer+decor.getPaddingTop()+decor.getPaddingBottom();
      if(constrained!=compact){
        compact=constrained;
        // Reuse the exact native title, not a duplicate node or a smaller font.
        // Only the title moves; the focused editor never detaches/reparents.
        if(compact){heading.removeView(title);LinearLayout.LayoutParams inline=new LinearLayout.LayoutParams(-2,-2);inline.rightMargin=a.dp(8);inputRow.addView(title,0,inline);}
        else{inputRow.removeView(title);heading.addView(title,new LinearLayout.LayoutParams(-1,-2));}
        heading.setVisibility(compact?View.GONE:View.VISIBLE);label.setVisibility(compact?View.GONE:View.VISIBLE);
        box.setPadding(normalLeft,compact?a.dp(4):normalTop,normalRight,compact?a.dp(4):normalBottom);
        form.scrollTo(0,0);
      }
      int noticeVisibility=compact&&TextUtils.isEmpty(notice.getText())?View.GONE:View.VISIBLE;
      if(notice.getVisibility()!=noticeVisibility)notice.setVisibility(noticeVisibility);
    }
    void close(){
      if(closed)return;closed=true;
      decor.removeOnAttachStateChangeListener(this);
      if(observer!=null&&observer.isAlive())observer.removeOnGlobalLayoutListener(this);
      ViewTreeObserver current=decor.getViewTreeObserver();if(current!=observer&&current.isAlive())current.removeOnGlobalLayoutListener(this);
      notice.removeTextChangedListener(this);
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
