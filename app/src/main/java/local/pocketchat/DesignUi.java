package local.pocketchat;

import android.app.*;import android.content.*;import android.content.res.ColorStateList;import android.graphics.*;import android.graphics.drawable.*;import android.os.*;import android.view.*;import android.widget.*;import java.util.*;

/** Native design system. Website content and network/identity policies are not restyled here. */
final class DesignUi {
  static final int BG=0xfff4f7fb,CARD=0xffffffff,FIELD=0xfff8fafc,LINE=0xffe0e7f0,TEXT=0xff172033,MUTED=0xff64748b,BLUE=0xff2468f2,CYAN=0xff2468f2,PURPLE=0xff2468f2,GREEN=0xff16845b,RED=0xffc93747;
  static final String[] NAV={"会话","环境","下载","网络","设置"},GLYPHS={"chat","window","download","globe","settings"};
  static int dp(Context c,int n){return Ui.dp(c,n);}
  static TextView text(Context c,String value,int size,int color){TextView v=new TextView(c);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setIncludeFontPadding(false);v.setLineSpacing(dp(c,3),1);return v;}
  static GradientDrawable surface(Context c,int color,int radius,int stroke){GradientDrawable d=Ui.shape(c,color,radius);d.setStroke(dp(c,1),stroke);return d;}
  static GradientDrawable gradient(Context c){GradientDrawable d=new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT,new int[]{BLUE,BLUE});d.setCornerRadius(dp(c,12));d.setStroke(dp(c,1),CYAN);return d;}
  static void chrome(Activity a){a.getWindow().setStatusBarColor(BG);a.getWindow().setNavigationBarColor(BG);a.getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | (Build.VERSION.SDK_INT>=26?View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR:0));}
  static LinearLayout column(Context c){LinearLayout v=new LinearLayout(c);v.setOrientation(1);return v;}
  static LinearLayout row(Context c){LinearLayout v=new LinearLayout(c);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
  static LinearLayout card(Context c){LinearLayout box=column(c);box.setPadding(dp(c,14),dp(c,10),dp(c,14),dp(c,8));box.setBackground(surface(c,CARD,14,LINE));return box;}
  static ArrayAdapter<String> spinnerAdapter(Context c,String[] labels){return new ArrayAdapter<String>(c,android.R.layout.simple_spinner_dropdown_item,labels){
    TextView style(android.view.View view){TextView text=(TextView)view;text.setTextColor(TEXT);text.setTextSize(15);return text;}
    @Override public android.view.View getView(int position,android.view.View reused,android.view.ViewGroup parent){return style(super.getView(position,reused,parent));}
    @Override public android.view.View getDropDownView(int position,android.view.View reused,android.view.ViewGroup parent){return style(super.getDropDownView(position,reused,parent));}
  };}
  static void addCard(LinearLayout parent,View card){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(parent.getContext(),10);parent.addView(card,p);}
  static final class ActionButton extends Button {
    ActionButton(Context c){super(c);}
    @Override public void setEnabled(boolean enabled){super.setEnabled(enabled);setAlpha(enabled?1f:.45f);}
  }
  static Button button(Context c,String title,boolean primary,Runnable action){
    Button b=new ActionButton(c);b.setText(title);b.setAllCaps(false);b.setTextSize(14);b.setIncludeFontPadding(false);
    b.setTextColor(primary?Color.WHITE:TEXT);b.setMinWidth(0);b.setMinimumWidth(0);
    b.setMinHeight(dp(c,48));b.setMinimumHeight(dp(c,48));
    b.setPadding(dp(c,12),dp(c,8),dp(c,12),dp(c,8));b.setStateListAnimator(null);
    b.setBackground(new RippleDrawable(ColorStateList.valueOf(primary?0x33ffffff:0x182563eb),primary?gradient(c):surface(c,CARD,12,LINE),null));
    b.setOnClickListener(v->action.run());return b;
  }
  static void action(LinearLayout box,String label,boolean primary,Runnable run){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(box.getContext(),48));p.topMargin=dp(box.getContext(),10);box.addView(button(box.getContext(),label,primary,run),p);}
  static void feedback(Activity a,String message){if(a instanceof MainActivity)((MainActivity)a).status(message);else Toast.makeText(a,message,Toast.LENGTH_SHORT).show();}
  static Runnable protectEdits(Activity a,AlertDialog dialog,java.util.function.BooleanSupplier dirty){
    final AlertDialog[] prompt={null};
    Runnable close=()->{
      if(!dirty.getAsBoolean()){dialog.dismiss();return;}
      if(prompt[0]!=null&&prompt[0].isShowing())return;
      prompt[0]=new AlertDialog.Builder(a).setTitle("保留正在填写的内容？")
        .setMessage("继续编辑可保留本次填写；放弃修改后会退出此表单。")
        .setPositiveButton("继续编辑",null).setNegativeButton("放弃修改",(d,w)->dialog.dismiss()).show();
      prompt[0].getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(RED);
    };
    dialog.setCanceledOnTouchOutside(false);
    dialog.setOnKeyListener((d,key,event)->{if(key!=KeyEvent.KEYCODE_BACK)return false;if(event.getAction()==KeyEvent.ACTION_UP)close.run();return true;});
    dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener(v->close.run());return close;
  }
  static void empty(LinearLayout box,String title,String detail,String action,Runnable run){
    Context c=box.getContext();LinearLayout card=card(c);TextView h=text(c,title,16,TEXT);h.setTypeface(Typeface.DEFAULT_BOLD);card.addView(h);note(card,detail);
    if(run!=null)action(card,action,false,run);addCard(box,card);
  }
  static LinearLayout progress(Context c,String title,String detail){
    LinearLayout card=card(c),row=row(c);ProgressBar spinner=new ProgressBar(c);spinner.setIndeterminateTintList(ColorStateList.valueOf(BLUE));
    row.addView(spinner,new LinearLayout.LayoutParams(dp(c,24),dp(c,24)));TextView label=text(c,title,14,TEXT);label.setPadding(dp(c,12),0,0,0);label.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    row.addView(label,new LinearLayout.LayoutParams(0,-2,1));card.addView(row);if(!detail.isEmpty())note(card,detail);return card;
  }
  static void rebuild(LinearLayout box,boolean preserveScroll,Runnable render){
    ViewParent parent=box.getParent();ScrollView scroll=parent instanceof ScrollView?(ScrollView)parent:null;
    int y=preserveScroll&&scroll!=null?scroll.getScrollY():0;Object renderToken=new Object();box.setTag(renderToken);
    box.removeAllViews();render.run();if(scroll!=null)scroll.post(()->{if(box.getTag()==renderToken)scroll.scrollTo(0,y);});
  }
  static TextView badge(Context c,String label,int color){TextView t=text(c,label,12,color);t.setGravity(Gravity.CENTER);t.setPadding(dp(c,8),dp(c,4),dp(c,8),dp(c,4));t.setBackground(surface(c,(color&0x00ffffff)|0x11000000,7,Color.TRANSPARENT));return t;}
  static void note(LinearLayout box,String s){TextView t=text(box.getContext(),s,13,MUTED);t.setPadding(0,dp(box.getContext(),10),0,dp(box.getContext(),6));box.addView(t);}
  static ImageView icon(Context c,String glyph,int color,int size){ImageView v=new ImageView(c);v.setImageDrawable(new Ui.Icon(glyph,color));v.setPadding(dp(c,7),dp(c,7),dp(c,7),dp(c,7));v.setBackground(surface(c,(color&0xffffff)|0x11000000,10,Color.TRANSPARENT));v.setLayoutParams(new LinearLayout.LayoutParams(dp(c,size),dp(c,size)));return v;}
  static LinearLayout setting(Context c,String glyph,String title,String detail,String tag,Runnable action){LinearLayout r=row(c);r.setPadding(dp(c,10),dp(c,12),dp(c,10),dp(c,12));ImageView icon=icon(c,glyph,CYAN,34);r.addView(icon);LinearLayout labels=column(c);labels.setPadding(dp(c,10),0,dp(c,8),0);labels.addView(text(c,title,15,TEXT));if(!detail.isEmpty()){TextView sub=text(c,detail,13,MUTED);sub.setPadding(0,dp(c,4),0,0);labels.addView(sub);}r.addView(labels,new LinearLayout.LayoutParams(0,-2,1));r.addView(tag.isEmpty()?text(c,"›",22,MUTED):badge(c,tag,MUTED));r.setBackground(new RippleDrawable(ColorStateList.valueOf(0x182468f2),surface(c,CARD,10,Color.TRANSPARENT),null));if(action!=null){r.setClickable(true);r.setFocusable(true);r.setOnClickListener(v->action.run());}return r;}
  static void field(LinearLayout box,String title,String value){
    Context c=box.getContext();LinearLayout row=row(c);row.setGravity(Gravity.TOP);row.setPadding(0,dp(c,7),0,dp(c,7));
    TextView name=text(c,title,12,MUTED);row.addView(name,new LinearLayout.LayoutParams(dp(c,76),-2));
    TextView val=text(c,value,14,TEXT);val.setTextIsSelectable(true);row.addView(val,new LinearLayout.LayoutParams(0,-2,1));box.addView(row);
  }
  static EditText input(LinearLayout box,String title,String value,String hint){Context c=box.getContext();TextView label=text(c,title,13,MUTED);label.setPadding(0,dp(c,12),0,dp(c,6));if(!title.isEmpty())box.addView(label);EditText e=new EditText(c);e.setTextSize(14);e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setSingleLine(true);e.setContentDescription(title);e.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_NEXT);e.setText(value);e.setHint(hint);e.setPadding(dp(c,10),0,dp(c,10),0);e.setBackground(surface(c,CARD,12,LINE));box.addView(e,new LinearLayout.LayoutParams(-1,dp(c,48)));return e;}
  static LinearLayout tabs(Context c,String[] labels,int selected,java.util.function.IntConsumer onClick){return ReferenceUi.tabs(c,labels,selected,onClick);}
  static LinearLayout nav(Activity a,int selected,java.util.function.IntConsumer action,Button[] buttons){return ReferenceUi.nav(a,selected,action,buttons);}
  static void markNav(Activity a,Button[] tabs,int selected){ReferenceUi.markNav(tabs,selected);}
  static LinearLayout screen(Activity a){chrome(a);LinearLayout root=column(a);root.setFitsSystemWindows(true);root.setBackground(new Stars(a));return root;}
  static LinearLayout body(Activity a,LinearLayout root,String title,Runnable back){LinearLayout head=row(a);head.setPadding(dp(a,12),dp(a,8),dp(a,12),dp(a,8));if(back!=null){Button b=button(a,"‹",false,back);b.setContentDescription("返回");head.addView(b,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));}TextView heading=text(a,title,20,TEXT);heading.setTypeface(Typeface.DEFAULT_BOLD);heading.setPadding(dp(a,8),0,0,0);head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));root.addView(head);LinearLayout box=column(a);box.setPadding(dp(a,14),0,dp(a,14),dp(a,18));ScrollView scroll=new ScrollView(a);scroll.setFillViewport(true);scroll.addView(box);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));return box;}
  static void section(LinearLayout box,String title,String detail){TextView h=text(box.getContext(),title,15,TEXT);h.setTypeface(Typeface.DEFAULT_BOLD);h.setPadding(0,dp(box.getContext(),12),0,dp(box.getContext(),4));box.addView(h);if(!detail.isEmpty())note(box,detail);}
  static void scope(MainActivity a,LinearLayout box){
    LinearLayout row=row(a);TextView label=text(a,"环境 · "+Profiles.display(a,Profiles.slot(a)),13,MUTED);label.setSingleLine(true);label.setEllipsize(android.text.TextUtils.TruncateAt.END);
    row.addView(label,new LinearLayout.LayoutParams(0,-2,1));Button change=button(a,"切换",false,()->a.startActivity(new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
    change.setTextSize(12);row.addView(change,new LinearLayout.LayoutParams(dp(a,64),dp(a,48)));box.addView(row);
  }
  static AlertDialog message(Activity a,String title,String text){return new AlertDialog.Builder(a).setTitle(title).setMessage(text).setPositiveButton("知道了",null).show();}
  static final class Stars extends Drawable {final Paint p=new Paint(3);final Context c;Stars(Context c){this.c=c;}public void draw(Canvas canvas){canvas.drawColor(BG);if(!AppSettings.bool(c,"starBackground",false))return;Rect b=getBounds();Random r=new Random(87);for(int i=0;i<100;i++){float x=r.nextFloat()*b.width(),y=r.nextFloat()*b.height();p.setColor(i%4==0?0x552a78c7:0x222598dc);canvas.drawCircle(x,y,i%9==0?1.6f:.7f,p);}p.setShader(new LinearGradient(0,0,b.width(),b.height()/2f,new int[]{0x180453a2,0x000453a2},null,Shader.TileMode.CLAMP));canvas.drawRect(b,p);p.setShader(null);}public void setAlpha(int a){}public void setColorFilter(ColorFilter f){}public int getOpacity(){return PixelFormat.OPAQUE;}}
}
