import java.util.*;

/** Measured-widget event adapter, not Android rendering/IME execution. */
public final class AddressDialogLayoutHost {
  static int checks,mutations;
  static void check(boolean good,String message){if(!good)throw new AssertionError(message);checks++;}
  static class Rect {int bottom;int height(){return bottom;}}
  interface Editable extends CharSequence {}
  interface TextWatcher {void beforeTextChanged(CharSequence s,int start,int count,int after);void onTextChanged(CharSequence s,int start,int before,int count);void afterTextChanged(Editable text);}
  static class TextUtils {static boolean isEmpty(CharSequence text){return text==null||text.length()==0;}}
  static class ViewTreeObserver {
    interface OnGlobalLayoutListener {void onGlobalLayout();}
    boolean alive=true;final List<OnGlobalLayoutListener> listeners=new ArrayList<>();
    void addOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.add(l);}
    void removeOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.remove(l);}
    boolean isAlive(){return alive;}
    void dispatch(){if(alive)for(OnGlobalLayoutListener l:new ArrayList<>(listeners))l.onGlobalLayout();}
  }
  static class View {
    interface OnAttachStateChangeListener {void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
    static final int VISIBLE=0,GONE=8;int measured,visibility=VISIBLE,left,top,right,bottom,available;View parent;
    ViewTreeObserver observer=new ViewTreeObserver();final List<OnAttachStateChangeListener> attachListeners=new ArrayList<>();
    Object getParent(){return parent;}int getMeasuredHeight(){return measured;}int getVisibility(){return visibility;}
    void setVisibility(int v){if(visibility!=v){visibility=v;mutations++;}}
    int getPaddingLeft(){return left;}int getPaddingTop(){return top;}int getPaddingRight(){return right;}int getPaddingBottom(){return bottom;}
    void setPadding(int l,int t,int r,int b){if(left!=l||top!=t||right!=r||bottom!=b){left=l;top=t;right=r;bottom=b;mutations++;}}
    ViewTreeObserver getViewTreeObserver(){return observer;}
    void addOnAttachStateChangeListener(OnAttachStateChangeListener l){attachListeners.add(l);}
    void removeOnAttachStateChangeListener(OnAttachStateChangeListener l){attachListeners.remove(l);}
    void attachWithMergedObserver(){ViewTreeObserver old=observer;observer=new ViewTreeObserver();observer.listeners.addAll(old.listeners);old.alive=false;for(OnAttachStateChangeListener l:new ArrayList<>(attachListeners))l.onViewAttachedToWindow(this);}
    void getWindowVisibleDisplayFrame(Rect rect){rect.bottom=available;}
  }
  static class LinearLayout extends View {
    static class LayoutParams {int rightMargin;LayoutParams(int w,int h){}}
    final List<View> children=new ArrayList<>();
    void removeView(View v){if(!children.remove(v))throw new AssertionError("Wrong parent");v.parent=null;mutations++;}
    void addView(View v,LayoutParams p){addView(v,children.size(),p);}
    void addView(View v,int index,LayoutParams p){if(v.parent!=null)throw new AssertionError("Already attached");children.add(index,v);v.parent=this;mutations++;}
  }
  static class TextView extends View {
    String text="";final List<TextWatcher> watchers=new ArrayList<>();
    CharSequence getText(){return text;}void addTextChangedListener(TextWatcher w){watchers.add(w);}void removeTextChangedListener(TextWatcher w){watchers.remove(w);}
    void setText(String value){text=value;for(TextWatcher w:new ArrayList<>(watchers))w.afterTextChanged(null);}
  }
  static class EditText extends TextView {int selection=8,minHeight,minimumHeight;boolean focused=true;int getMinHeight(){return minHeight;}int getMinimumHeight(){return minimumHeight;}void setMinHeight(int h){minHeight=h;}void setMinimumHeight(int h){minimumHeight=h;}}
  static class ScrollView extends View {int scrollCalls;void scrollTo(int x,int y){scrollCalls++;}}
  static class Window {final View decor=new View();View getDecorView(){return decor;}}
  static class AlertDialog {static final int BUTTON_POSITIVE=-1;boolean showing=true;final Window window=new Window();final View button=new View();Window getWindow(){return window;}View getButton(int id){return button;}boolean isShowing(){return showing;}}
  static class MainActivity {final float density;MainActivity(float d){density=d;}int dp(int n){return Math.round(n*density);}}

  /* PRODUCTION_CONTROLLER */

  static class Fixture {
    final MainActivity activity;final AlertDialog dialog=new AlertDialog();
    final LinearLayout heading=new LinearLayout(),box=new LinearLayout(),row=new LinearLayout();
    final TextView title=new TextView(),label=new TextView(),notice=new TextView();final EditText input=new EditText();
    final ScrollView scroll=new ScrollView();final View footer=new View();final AddressDialogLayout layout;
    int titleTextHeight=88,labelNatural=128,inputNatural=150,emptyNotice=46,buttonTouchHeight=144,viewport;
    Fixture(int available){this(available,3f);}
    Fixture(int available,float density){
      activity=new MainActivity(density);titleTextHeight=Math.round(88*density/3);labelNatural=Math.round(128*density/3);inputNatural=activity.dp(50);emptyNotice=Math.round(46*density/3);buttonTouchHeight=activity.dp(48);
      title.text="打开网址";input.text="https://chatgpt.com/c/retained";heading.top=activity.dp(18);box.top=activity.dp(8);box.bottom=activity.dp(12);footer.measured=activity.dp(56);
      heading.addView(title,new LinearLayout.LayoutParams(-1,-2));row.addView(input,new LinearLayout.LayoutParams(-1,-2));dialog.button.parent=footer;dialog.window.decor.available=available;
      AddressDialogLayout.ensureTouchTarget(input,activity.dp(48));
      layout=new AddressDialogLayout(activity,dialog,heading,title,label,box,row,input,notice,scroll);measure();layout.attach();
    }
    void measure(){
      input.measured=Math.max(inputNatural,Math.max(input.getMinHeight(),input.getMinimumHeight()));title.measured=titleTextHeight;label.measured=label.visibility==View.VISIBLE?labelNatural:0;
      notice.measured=notice.visibility==View.GONE?0:notice.text.isEmpty()?emptyNotice:300;
      row.measured=Math.max(input.measured,title.parent==row?title.measured:0);
      heading.measured=title.parent==heading?heading.top+title.measured:0;
      box.measured=box.top+box.bottom+label.measured+row.measured+notice.measured;
      viewport=Math.min(box.measured,Math.max(0,dialog.window.decor.available-heading.measured-footer.measured));
    }
    void event(){measure();dialog.window.decor.observer.dispatch();measure();}
    void fits(){check(input.measured>=144,"Input keeps >=48dp");check(buttonTouchHeight>=144,"Original button touch height kept");check(box.top+input.measured<=viewport,"Complete input above keyboard");check(heading.measured+viewport+footer.measured<=dialog.window.decor.available,"Footer above keyboard");}
  }
  public static void main(String[] ignored){
    Fixture f=new Fixture(381);f.event();
    check(f.layout.compact,"Original381px frame must enter compact mode, not just scroll71px");f.fits();
    check(f.title.parent==f.row&&f.title.text.equals("打开网址"),"Same title remains visible inline");
    check(f.row.children.size()==2&&f.input.parent==f.row,"Editor parent retained");
    check(f.label.visibility==View.GONE&&f.notice.visibility==View.GONE,"Only redundant short-height chrome hidden");
    check(f.input.focused&&f.input.selection==8&&f.input.text.equals("https://chatgpt.com/c/retained"),"Focus/selection/native draft not changed");
    int stable=mutations;for(int i=0;i<25;i++)f.event();check(mutations==stable,"Stable layouts do not request another layout");
    f.notice.setText("Long actionable invalid-address error");f.event();
    check(f.notice.visibility==View.VISIBLE,"Nonempty error never hidden");check(f.box.measured>f.viewport,"Long error remains in scrollable content");f.fits();
    f.notice.setText("");f.event();check(f.notice.visibility==View.GONE,"Empty notice reclaims space only while constrained");
    f.dialog.window.decor.available=1164;f.event();
    check(!f.layout.compact&&f.title.parent==f.heading,"Height restoration returns exact title to normal position");
    check(f.label.visibility==View.VISIBLE&&f.notice.visibility==View.VISIBLE,"Normal label and original empty-notice spacing restored");
    check(f.box.top==24&&f.box.bottom==36,"Original normal padding restored");
    check(f.row.children.size()==1&&f.input.parent==f.row,"Restoration never reparents input");
    check(f.heading.measured==142&&f.box.measured==384,"Normal measured dimensions preserved after compact roundtrip");
    check(f.dialog.window.decor.observer.listeners.size()==1&&f.notice.watchers.size()==1,"One event subscription only");
    f.dialog.window.decor.attachWithMergedObserver();check(f.dialog.window.decor.observer.listeners.size()==1,"Floating observer merge must retain exactly one live listener");
    f.layout.close();f.layout.close();check(f.dialog.window.decor.observer.listeners.isEmpty()&&f.notice.watchers.isEmpty()&&f.dialog.window.decor.attachListeners.isEmpty(),"Dismiss cleans all live listeners idempotently");
    stable=mutations;f.dialog.window.decor.available=381;f.notice.setText("after dismiss");f.event();check(mutations==stable,"Closed controller never changes a retained view");
    Fixture portrait=new Fixture(1800);portrait.event();check(!portrait.layout.compact&&portrait.title.parent==portrait.heading,"Tall portrait remains original from first presentation");
    Fixture firstIme=new Fixture(381);firstIme.event();check(firstIme.layout.compact,"First measurement already resized is handled");
    Fixture largerText=new Fixture(2000);largerText.inputNatural=177;largerText.buttonTouchHeight=163;largerText.labelNatural=180;largerText.event();check(!largerText.layout.compact,"Large-font portrait is not compact merely due orientation assumptions");
    Fixture dead=new Fixture(381);dead.dialog.window.decor.observer.alive=false;dead.layout.close();check(dead.notice.watchers.isEmpty(),"Dead observer does not prevent notice cleanup");
    Fixture fractional=new Fixture(1000,1.0625f);fractional.dialog.window.decor.available=fractional.heading.measured+fractional.box.measured+fractional.footer.measured-1;fractional.event();
    check(fractional.layout.compact,"Subpixel dp rounding must not hide the one-pixel shortage");stable=mutations;for(int i=0;i<25;i++)fractional.event();check(fractional.layout.compact&&mutations==stable,"Exact saved padding difference prevents a layout oscillation at fractional density");
    // Original S06 Android XML measured API35=142px and API32=129px at480dpi.
    for(int oldHeight:new int[]{142,129}){Fixture touch=new Fixture(381);touch.inputNatural=oldHeight;touch.event();check(touch.input.measured>=144,"Recorded sub-48dp native input must now measure at least144px");touch.fits();}
    EditText large=new EditText();large.setMinHeight(177);large.setMinimumHeight(163);AddressDialogLayout.ensureTouchTarget(large,144);check(large.getMinHeight()==177&&large.getMinimumHeight()==177,"Larger font minimum must never be reduced to48dp");
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false}");
  }
}
