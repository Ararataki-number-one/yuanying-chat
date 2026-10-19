package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.res.*;
import android.graphics.Color;
import android.graphics.drawable.*;
import android.os.Build;
import android.view.*;
import android.widget.*;
import java.util.*;

/** App-wide, event-driven appearance. Never recreates a browser or reloads a document. */
final class AppAppearance {
  static final String KEY="appearanceMode";
  static final String[] MODES={"system","light","dark"},LABELS={"跟随系统","始终白天","始终黑夜"};
  private static String mode="system";
  private static boolean dark;
  private static boolean installed;
  private static final Set<Activity> activities=Collections.newSetFromMap(new WeakHashMap<>());
  private static final Set<Dialog> dialogs=Collections.newSetFromMap(new WeakHashMap<>());
  static boolean dark(){return dark;}
  static String mode(){return mode;}
  static String label(){return LABELS[Arrays.asList(MODES).indexOf(mode)];}
  static int color(int value){return AppearanceColors.color(value,dark);}
  static int text(int value){return AppearanceColors.text(value,dark);}
  static int theme(){return dark?R.style.AppThemeDark:R.style.AppThemeLight;}
  static void install(Application app){
    // Gecko renderers run the same Application under an isolated UID. They must
    // never open the catalogue or register the UI settings receiver.
    if(android.os.Process.myUid()!=app.getApplicationInfo().uid)return;
    if(Build.VERSION.SDK_INT>=28&&!AppearanceColors.ownsUi(app.getPackageName(),Application.getProcessName()))return;
    installed=true;
    refresh(app);
    IntentFilter filter=new IntentFilter(app.getPackageName()+".APPEARANCE_CHANGED");
    BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent i){refresh(c);}};
    if(Build.VERSION.SDK_INT>=33)app.registerReceiver(receiver,filter,Context.RECEIVER_NOT_EXPORTED);else app.registerReceiver(receiver,filter);
  }
  static void choose(Activity a,String value){
    String selected=AppearanceColors.mode(value);if(selected.equals(mode))return;
    AppSettings.put(a,KEY,selected);refresh(a);
    a.sendBroadcast(new Intent(a.getPackageName()+".APPEARANCE_CHANGED").setPackage(a.getPackageName()));
  }
  static void refresh(Context context){
    if(!installed)return;
    String selected=AppearanceColors.mode(AppSettings.get(context,KEY,"system"));
    boolean system=(context.getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
    boolean next=AppearanceColors.dark(selected,system),changed=next!=dark||!selected.equals(mode);
    mode=selected;dark=next;palette();
    if(!changed)return;
    for(Activity a:new ArrayList<>(activities))if(!a.isDestroyed()){a.setTheme(theme());window(a.getWindow());apply(a.getWindow().getDecorView());}
    for(Dialog d:new ArrayList<>(dialogs))if(d.isShowing()){dialogWindow(d);apply(d.getWindow().getDecorView());}
    ChatSession session=ChatSession.peek();if(session!=null&&!session.deleted&&session.web!=null)session.web.applyAppearance();
  }
  private static void palette(){
    DesignUi.BG=color(0xfff4f7fb);DesignUi.CARD=color(Color.WHITE);DesignUi.FIELD=color(0xfff8fafc);DesignUi.LINE=color(0xffe0e7f0);
    DesignUi.TEXT=color(0xff172033);DesignUi.MUTED=color(0xff64748b);DesignUi.BLUE=DesignUi.CYAN=DesignUi.PURPLE=color(0xff2468f2);DesignUi.GREEN=color(0xff16845b);DesignUi.RED=color(0xffc93747);
    ReferenceUi.BG=DesignUi.BG;ReferenceUi.CHAT_BG=color(0xfff9fbfe);ReferenceUi.WHITE=DesignUi.CARD;ReferenceUi.TEXT=DesignUi.TEXT;
    ReferenceUi.MUTED=DesignUi.MUTED;ReferenceUi.LINE=DesignUi.LINE;ReferenceUi.BLUE=DesignUi.BLUE;ReferenceUi.BLUE_SOFT=color(0xffedf4ff);ReferenceUi.GREEN=DesignUi.GREEN;ReferenceUi.ORANGE=color(0xffa96c0a);ReferenceUi.RED=DesignUi.RED;
    Ui.INK=color(0xff1e293b);Ui.MUTED=DesignUi.MUTED;Ui.PAPER=color(0xfff4f6fa);Ui.SOFT=color(0xffeaf1ff);
  }
  static void attach(Activity a){refresh(a);activities.add(a);a.setTheme(theme());}
  static void detach(Activity a){activities.remove(a);}
  static void window(Window w){
    if(w==null)return;
    w.setStatusBarColor(ReferenceUi.CHAT_BG);w.setNavigationBarColor(DesignUi.CARD);
    int flags=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
    View decor=w.getDecorView();decor.setSystemUiVisibility(dark?decor.getSystemUiVisibility()&~flags:decor.getSystemUiVisibility()|flags);
    if(Build.VERSION.SDK_INT>=29){w.setNavigationBarContrastEnforced(false);w.setStatusBarContrastEnforced(false);decor.setForceDarkAllowed(false);}
    if(Build.VERSION.SDK_INT>=30&&w.getInsetsController()!=null)w.getInsetsController().setSystemBarsAppearance(dark?0:WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
    w.setBackgroundDrawable(new ColorDrawable(DesignUi.BG));
  }
  static void watch(Dialog d){dialogs.add(d);}
  static void shown(Dialog d){watch(d);dialogWindow(d);apply(d.getWindow().getDecorView());}
  private static void dialogWindow(Dialog d){
    if(d.getWindow()==null)return;
    d.getContext().setTheme(d instanceof AlertDialog?(dark?R.style.ChatDialogDark:R.style.ChatDialogTheme):theme());
    d.getWindow().setStatusBarColor(color(d.getWindow().getStatusBarColor()));d.getWindow().setNavigationBarColor(color(d.getWindow().getNavigationBarColor()));
    if(d instanceof AlertDialog)d.getWindow().setBackgroundDrawable(DesignUi.surface(d.getContext(),DesignUi.CARD,24,Color.TRANSPARENT));
    int flags=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;View decor=d.getWindow().getDecorView();
    decor.setSystemUiVisibility(dark?decor.getSystemUiVisibility()&~flags:decor.getSystemUiVisibility()|flags);
    if(Build.VERSION.SDK_INT>=29)decor.setForceDarkAllowed(false);
  }
  static AlertDialog.Builder dialog(Context c){
    return new AlertDialog.Builder(c,dark?R.style.ChatDialogDark:R.style.ChatDialogTheme){
      @Override public AlertDialog create(){AlertDialog d=super.create();watch(d);d.getWindow().getDecorView().addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
        @Override public void onViewAttachedToWindow(View v){shown(d);}
        @Override public void onViewDetachedFromWindow(View v){}
      });return d;}
    };
  }
  /** Called only on an appearance event / initial window presentation, not each frame. */
  static void apply(View v){
    if(v instanceof GeckoWebView||v instanceof org.mozilla.geckoview.GeckoView||v instanceof android.webkit.WebView)return;
    drawable(v.getBackground());
    if(v instanceof TextView){
      TextView t=(TextView)v;t.setTextColor(colors(t.getTextColors(),true));t.setHintTextColor(colors(t.getHintTextColors(),true));t.setLinkTextColor(colors(t.getLinkTextColors(),true));
      for(Drawable icon:t.getCompoundDrawables())drawable(icon);
    }
    if(v instanceof ImageView&&((ImageView)v).getDrawable() instanceof Ui.Icon)drawable(((ImageView)v).getDrawable());
    if(v instanceof CompoundButton){CompoundButton b=(CompoundButton)v;b.setButtonTintList(controlColors());if(v instanceof Switch){((Switch)v).setThumbTintList(controlColors());((Switch)v).setTrackTintList(new ColorStateList(new int[][]{{android.R.attr.state_checked},{}},new int[]{color(0xff8fb4ff),DesignUi.LINE}));}}
    if(v instanceof ProgressBar){((ProgressBar)v).setIndeterminateTintList(ColorStateList.valueOf(DesignUi.BLUE));((ProgressBar)v).setProgressTintList(ColorStateList.valueOf(DesignUi.BLUE));}
    if(v instanceof ViewGroup){ViewGroup group=(ViewGroup)v;for(int i=0;i<group.getChildCount();i++)apply(group.getChildAt(i));}
    v.invalidate();
  }
  private static ColorStateList controlColors(){return new ColorStateList(new int[][]{{-android.R.attr.state_enabled},{android.R.attr.state_checked},{}},new int[]{DesignUi.LINE,DesignUi.BLUE,DesignUi.MUTED});}
  private static ColorStateList colors(ColorStateList source,boolean foreground){
    if(source==null)return ColorStateList.valueOf(DesignUi.TEXT);
    int[][] states={{-android.R.attr.state_enabled},{android.R.attr.state_pressed},{android.R.attr.state_checked},{android.R.attr.state_selected},{android.R.attr.state_focused},{}};
    int[] values=new int[states.length];for(int i=0;i<values.length;i++){int value=source.getColorForState(states[i],source.getDefaultColor());values[i]=foreground?text(value):color(value);}return new ColorStateList(states,values);
  }
  private static void drawable(Drawable d){
    if(d instanceof Glass)((Glass)d).refresh();
    else if(d instanceof Surface)((Surface)d).refresh();
    else if(d instanceof ColorDrawable)((ColorDrawable)d).setColor(color(((ColorDrawable)d).getColor()));
    else if(d instanceof Ui.Icon){Ui.Icon icon=(Ui.Icon)d;icon.color=text(icon.color);icon.invalidateSelf();}
    if(d instanceof LayerDrawable){LayerDrawable layers=(LayerDrawable)d;for(int i=0;i<layers.getNumberOfLayers();i++)drawable(layers.getDrawable(i));}
    else if(d instanceof InsetDrawable)drawable(((InsetDrawable)d).getDrawable());
  }
  static final class Surface extends GradientDrawable {
    int fill,border,width;
    Surface(int fill){this.fill=fill;refresh();}
    @Override public void setStroke(int width,int border){this.width=width;this.border=border;super.setStroke(width,color(border));}
    void refresh(){super.setColor(color(fill));super.setStroke(width,color(border));invalidateSelf();}
  }
  /** A small tinted material, without a screen-wide blur or browser snapshot. */
  static final class Glass extends GradientDrawable {
    final int edge;
    Glass(Context c,int radius){edge=Math.max(1,Math.round(c.getResources().getDisplayMetrics().density*.5f));setCornerRadius(Ui.dp(c,radius));setOrientation(Orientation.TOP_BOTTOM);refresh();}
    void refresh(){
      setColors(dark?new int[]{0xf036363b,0xe62a2a2f}:new int[]{0xfaffffff,0xe6eeeef3});
      setStroke(edge,dark?0x386e6e77:0x99ffffff);invalidateSelf();
    }
  }
}
