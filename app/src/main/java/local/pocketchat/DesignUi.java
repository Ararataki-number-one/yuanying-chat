package local.pocketchat;

import android.app.*;import android.content.*;import android.content.res.ColorStateList;import android.graphics.*;import android.graphics.drawable.*;import android.os.*;import android.view.*;import android.widget.*;import java.util.*;

/** Native design system. Website content and network/identity policies are not restyled here. */
final class DesignUi {
  static int BG=0xfff4f7fb,CARD=0xffffffff,FIELD=0xfff8fafc,LINE=0xffe0e7f0,TEXT=0xff172033,MUTED=0xff64748b,BLUE=0xff2468f2,CYAN=0xff2468f2,PURPLE=0xff2468f2,GREEN=0xff16845b,RED=0xffc93747;
  static final String[] NAV={"会话","环境","下载","网络","设置"},GLYPHS={"chat","window","download","globe","settings"};
  static int dp(Context c,int n){return Ui.dp(c,n);}
  static TextView text(Context c,String value,int size,int color){TextView v=new TextView(c);v.setText(value);v.setTextSize(size);v.setTextColor(AppAppearance.text(color));v.setIncludeFontPadding(false);v.setLineSpacing(dp(c,3),1);return v;}
  static GradientDrawable surface(Context c,int color,int radius,int stroke){GradientDrawable d=Ui.shape(c,color,radius);d.setStroke(dp(c,1),stroke);return d;}
  static GradientDrawable gradient(Context c){return surface(c,0xff1268ff,14,Color.TRANSPARENT);}
  static Drawable glass(Context c,int radius){return new RippleDrawable(ColorStateList.valueOf(0x142468f2),new AppAppearance.Glass(c,radius),surface(c,Color.WHITE,radius,Color.TRANSPARENT));}
  static void chrome(Activity a){AppAppearance.window(a.getWindow());}
  static LinearLayout column(Context c){LinearLayout v=new LinearLayout(c);v.setOrientation(LinearLayout.VERTICAL);return v;}
  static LinearLayout row(Context c){LinearLayout v=new LinearLayout(c);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
  static LinearLayout card(Context c){LinearLayout box=column(c);box.setPadding(dp(c,16),dp(c,14),dp(c,16),dp(c,12));box.setBackground(surface(c,CARD,18,Color.TRANSPARENT));return box;}
  static LinearLayout group(Context c){LinearLayout box=column(c);box.setBackground(surface(c,CARD,18,Color.TRANSPARENT));box.setClipToOutline(true);return box;}
  static void groupedRow(LinearLayout group,View row){
    Context c=group.getContext();
    if(group.getChildCount()>0){View line=new View(c);line.setBackgroundColor(LINE);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,Math.max(1,dp(c,1)/2));p.leftMargin=dp(c,60);p.rightMargin=dp(c,16);group.addView(line,p);}
    group.addView(row,new LinearLayout.LayoutParams(-1,-2));
  }
  static ArrayAdapter<String> spinnerAdapter(Context c,String[] labels){return new ArrayAdapter<String>(c,android.R.layout.simple_spinner_dropdown_item,labels){
    TextView style(android.view.View view){TextView text=(TextView)view;text.setTextColor(TEXT);text.setTextSize(15);text.setSingleLine(false);text.setMaxLines(3);text.setMinHeight(dp(c,48));text.setGravity(Gravity.CENTER_VERTICAL);text.setPadding(dp(c,12),dp(c,10),dp(c,28),dp(c,10));return text;}
    @Override public android.view.View getView(int position,android.view.View reused,android.view.ViewGroup parent){return style(super.getView(position,reused,parent));}
    @Override public android.view.View getDropDownView(int position,android.view.View reused,android.view.ViewGroup parent){return style(super.getDropDownView(position,reused,parent));}
  };}
  static void addCard(LinearLayout parent,View card){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(parent.getContext(),10);parent.addView(card,p);}
  static final class ActionButton extends Button {
    ActionButton(Context c){super(c);}
    @Override public void setEnabled(boolean enabled){super.setEnabled(enabled);setAlpha(enabled?1f:.45f);}
  }
  static int actionWidth(Button button,int minimumDp){return Math.max(dp(button.getContext(),minimumDp),(int)Math.ceil(button.getPaint().measureText(button.getText().toString()))+button.getCompoundPaddingLeft()+button.getCompoundPaddingRight()+dp(button.getContext(),2));}
  static Button button(Context c,String title,boolean primary,Runnable action){
    Button b=new ActionButton(c);b.setText(title);b.setAllCaps(false);b.setTextSize(14);b.setIncludeFontPadding(false);
    boolean destructive=title.startsWith("删除")||title.startsWith("清空")||title.equals("放弃修改");
    b.setTextColor(primary?Color.WHITE:destructive?RED:TEXT);b.setMinWidth(0);b.setMinimumWidth(0);
    b.setMinHeight(dp(c,48));b.setMinimumHeight(dp(c,48));
    b.setPadding(dp(c,12),dp(c,6),dp(c,12),dp(c,6));b.setStateListAnimator(null);
    b.setBackground(new RippleDrawable(ColorStateList.valueOf(primary?0x33ffffff:0x182563eb),primary?(destructive?surface(c,RED,14,Color.TRANSPARENT):gradient(c)):surface(c,FIELD,14,Color.TRANSPARENT),surface(c,Color.WHITE,14,Color.TRANSPARENT)));
    b.setOnClickListener(v->action.run());b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));return b;
  }
  static void action(LinearLayout box,String label,boolean primary,Runnable run){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(box.getContext(),10);box.addView(button(box.getContext(),label,primary,run),p);}
  static void feedback(Activity a,String message){if(a instanceof MainActivity)((MainActivity)a).status(message);else SavedFileActions.problem(a,message);}
  static Runnable protectEdits(Activity a,AlertDialog dialog,java.util.function.BooleanSupplier dirty){
    final AlertDialog[] prompt={null};
    Runnable close=()->{
      if(!dirty.getAsBoolean()){dialog.dismiss();return;}
      if(prompt[0]!=null&&prompt[0].isShowing())return;
      prompt[0]=AppAppearance.dialog(a).setTitle("保留正在填写的内容？")
        .setMessage("继续编辑可保留本次填写；放弃修改后会退出此表单。")
        .setPositiveButton("继续编辑",null).setNegativeButton("放弃修改",(d,w)->dialog.dismiss()).show();
      prompt[0].getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(RED);
    };
    dialog.setCanceledOnTouchOutside(false);
    dialog.setOnKeyListener((d,key,event)->{if(key!=KeyEvent.KEYCODE_BACK)return false;if(event.getAction()==KeyEvent.ACTION_UP)close.run();return true;});
    dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener(v->close.run());return close;
  }
  static void empty(LinearLayout box,String title,String detail,String action,Runnable run){
    Context c=box.getContext();LinearLayout card=card(c);card.setPadding(dp(c,20),dp(c,28),dp(c,20),dp(c,24));ImageView mark=icon(c,"tray",MUTED,44);card.addView(mark);TextView h=text(c,title,17,TEXT);h.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));h.setPadding(0,dp(c,16),0,0);card.addView(h);note(card,detail);
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
  static LinearLayout setting(Context c,String glyph,String title,String detail,String tag,Runnable action){
    LinearLayout r=row(c);r.setMinimumHeight(dp(c,64));r.setPadding(dp(c,16),dp(c,13),dp(c,16),dp(c,13));
    ImageView icon=icon(c,glyph,BLUE,30);r.addView(icon);LinearLayout labels=column(c);labels.setPadding(dp(c,14),0,dp(c,12),0);
    labels.addView(text(c,title,16,TEXT));if(!detail.isEmpty()){TextView sub=text(c,detail,13,MUTED);sub.setPadding(0,dp(c,5),0,0);labels.addView(sub);}
    r.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
    if(!tag.isEmpty())r.addView(badge(c,tag,MUTED));
    else if(action!=null){ImageView arrow=new ImageView(c);arrow.setImageDrawable(new Ui.Icon("chevron-right",MUTED));r.addView(arrow,new LinearLayout.LayoutParams(dp(c,14),dp(c,20)));}
    r.setBackground(new RippleDrawable(ColorStateList.valueOf(0x142468f2),surface(c,CARD,0,Color.TRANSPARENT),null));
    if(action!=null){r.setClickable(true);r.setFocusable(true);r.setOnClickListener(v->action.run());}return r;
  }
  static void field(LinearLayout box,String title,String value){
    Context c=box.getContext();LinearLayout row=row(c);boolean large=c.getResources().getConfiguration().fontScale>=1.4f;row.setOrientation(large?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);row.setGravity(Gravity.TOP);row.setPadding(0,dp(c,9),0,dp(c,9));
    TextView name=text(c,title,13,MUTED);row.addView(name,new LinearLayout.LayoutParams(large?-1:dp(c,88),-2));
    TextView val=text(c,value,15,TEXT);val.setTextIsSelectable(true);if(large)val.setPadding(0,dp(c,5),0,0);row.addView(val,new LinearLayout.LayoutParams(large?-1:0,-2,large?0:1));box.addView(row);
  }
  static EditText input(LinearLayout box,String title,String value,String hint){Context c=box.getContext();TextView label=text(c,title,13,MUTED);label.setPadding(0,dp(c,16),0,dp(c,8));if(!title.isEmpty())box.addView(label);EditText e=new EditText(c);e.setSingleLine(true);NativeControls.prepare(e);e.setContentDescription(title);label.setLabelFor(e.getId());e.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_NEXT);e.setText(value);e.setHint(hint);box.addView(e,new LinearLayout.LayoutParams(-1,-2));return e;}
  static void visiblePassword(EditText input){
    Context c=input.getContext();LinearLayout parent=(LinearLayout)input.getParent();int index=parent.indexOfChild(input);ViewGroup.LayoutParams layout=input.getLayoutParams();
    input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
    input.setImeOptions(input.getImeOptions()|android.view.inputmethod.EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
    input.setTransformationMethod(null);
    parent.removeView(input);FrameLayout row=new FrameLayout(c);parent.addView(row,index,layout);
    input.setPadding(input.getPaddingLeft(),input.getPaddingTop(),dp(c,76),input.getPaddingBottom());row.addView(input,new FrameLayout.LayoutParams(-1,-2));
    Button toggle=ReferenceUi.link(c,"隐藏",()->{});toggle.setContentDescription("隐藏密码");
    toggle.setOnClickListener(v->{
      int start=input.getSelectionStart(),end=input.getSelectionEnd();boolean hide=input.getTransformationMethod()==null;
      input.setTransformationMethod(hide?android.text.method.PasswordTransformationMethod.getInstance():null);
      if(start>=0&&end>=0)input.setSelection(Math.min(start,input.length()),Math.min(end,input.length()));
      toggle.setText(hide?"显示":"隐藏");toggle.setContentDescription(hide?"显示密码":"隐藏密码");
    });
    row.addView(toggle,new FrameLayout.LayoutParams(dp(c,68),-1,Gravity.END|Gravity.CENTER_VERTICAL));
  }
  static EditText searchInput(LinearLayout parent,String hint){
    Context c=parent.getContext();LinearLayout field=column(c);EditText input=input(field,"","",hint);field.removeView(input);
    FrameLayout host=new FrameLayout(c);host.addView(input,new FrameLayout.LayoutParams(-1,-2));
    Ui.Icon search=new Ui.Icon("search",MUTED);search.setBounds(0,0,dp(c,18),dp(c,18));input.setCompoundDrawables(search,null,null,null);input.setCompoundDrawablePadding(dp(c,8));input.setPadding(input.getPaddingLeft(),input.getPaddingTop(),dp(c,52),input.getPaddingBottom());input.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);
    Button clear=ReferenceUi.iconButton(c,"close","清除搜索内容",()->input.setText(""));clear.setVisibility(View.GONE);host.addView(clear,new FrameLayout.LayoutParams(dp(c,48),dp(c,48),Gravity.END|Gravity.CENTER_VERTICAL));
    input.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void afterTextChanged(android.text.Editable value){}public void onTextChanged(CharSequence s,int start,int before,int count){clear.setVisibility(s.length()==0?View.GONE:View.VISIBLE);}});
    parent.addView(host,new LinearLayout.LayoutParams(-1,-2));return input;
  }
  static LinearLayout tabs(Context c,String[] labels,int selected,java.util.function.IntConsumer onClick){return ReferenceUi.tabs(c,labels,selected,onClick);}
  static LinearLayout nav(Activity a,int selected,java.util.function.IntConsumer action,Button[] buttons){return ReferenceUi.nav(a,selected,action,buttons);}
  static void markNav(Activity a,Button[] tabs,int selected){ReferenceUi.markNav(tabs,selected);}
  static LinearLayout screen(Activity a){chrome(a);LinearLayout root=column(a);root.setFitsSystemWindows(true);root.setBackground(new Stars(a));return root;}
  static LinearLayout body(Activity a,LinearLayout root,String title,Runnable back){LinearLayout head=row(a);head.setPadding(dp(a,12),dp(a,8),dp(a,12),dp(a,8));if(back!=null){Button b=ReferenceUi.iconButton(a,"back","返回",back);head.addView(b,new LinearLayout.LayoutParams(dp(a,48),dp(a,48)));}TextView heading=text(a,title,24,TEXT);heading.setTypeface(Typeface.DEFAULT_BOLD);heading.setPadding(dp(a,8),0,0,0);head.addView(heading,new LinearLayout.LayoutParams(0,-2,1));root.addView(head);LinearLayout box=column(a);box.setPadding(dp(a,14),0,dp(a,14),dp(a,18));ScrollView scroll=new ScrollView(a);scroll.setFillViewport(true);scroll.addView(box);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));return box;}
  static void section(LinearLayout box,String title,String detail){TextView h=text(box.getContext(),title,13,MUTED);h.setPadding(dp(box.getContext(),16),dp(box.getContext(),22),dp(box.getContext(),16),dp(box.getContext(),8));if(Build.VERSION.SDK_INT>=28)h.setAccessibilityHeading(true);box.addView(h);if(!detail.isEmpty())note(box,detail);}
  static void scope(MainActivity a,LinearLayout box){
    LinearLayout row=row(a);TextView label=text(a,"环境 · "+Profiles.display(a,Profiles.slot(a)),13,MUTED);label.setSingleLine(true);label.setEllipsize(android.text.TextUtils.TruncateAt.END);
    row.addView(label,new LinearLayout.LayoutParams(0,-2,1));Button change=button(a,"切换",false,()->a.startActivity(new Intent(a,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
    change.setTextSize(12);row.addView(change,new LinearLayout.LayoutParams(dp(a,64),dp(a,48)));box.addView(row);
  }
  static void route(LinearLayout box,String entrance,String exit){
    Context c=box.getContext();LinearLayout route=column(c);route.setPadding(dp(c,12),dp(c,6),dp(c,12),dp(c,6));route.setBackground(surface(c,FIELD,12,Color.TRANSPARENT));
    String[] labels={"入口","固定出口","目的地"},values={entrance,exit,"ChatGPT"},icons={"globe","lock","chat"};
    for(int i=0;i<labels.length;i++){
      LinearLayout stage=row(c);stage.setPadding(0,dp(c,6),0,dp(c,6));ImageView icon=new ImageView(c);icon.setImageDrawable(new Ui.Icon(icons[i],i==1?BLUE:MUTED));stage.addView(icon,new LinearLayout.LayoutParams(dp(c,18),dp(c,18)));
      LinearLayout content=column(c);content.setPadding(dp(c,10),0,0,0);TextView label=text(c,labels[i],12,MUTED);content.addView(label);TextView name=text(c,values[i],14,TEXT);name.setMaxLines(3);name.setEllipsize(android.text.TextUtils.TruncateAt.END);name.setPadding(0,dp(c,3),0,0);content.addView(name);stage.addView(content,new LinearLayout.LayoutParams(0,-2,1));route.addView(stage);
    }
    LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(c,12);box.addView(route,p);
  }
  static AlertDialog message(Activity a,String title,String text){return AppAppearance.dialog(a).setTitle(title).setMessage(text).setPositiveButton("知道了",null).show();}
  static final class Stars extends Drawable {
    static final List<java.lang.ref.WeakReference<Stars>> instances=new ArrayList<>();
    static final Handler main=new Handler(Looper.getMainLooper());
    final Paint p=new Paint(3);final float[] xs=new float[100],ys=new float[100];
    boolean enabled;LinearGradient gradient;
    Stars(Context c){
      // Settings and geometry are prepared outside draw; even a plain background
      // must not wait for a SQLite reader while handling a frame.
      enabled=AppSettings.bool(c,"starBackground",false);
      Random random=new Random(87);for(int i=0;i<xs.length;i++){xs[i]=random.nextFloat();ys[i]=random.nextFloat();}
      synchronized(instances){instances.removeIf(ref->ref.get()==null);instances.add(new java.lang.ref.WeakReference<>(this));}
    }
    static void refresh(Context c){setting(AppSettings.bool(c,"starBackground",false));}
    static void setting(boolean value){
      if(Looper.myLooper()!=Looper.getMainLooper()){main.post(()->setting(value));return;}
      synchronized(instances){instances.removeIf(ref->ref.get()==null);for(java.lang.ref.WeakReference<Stars> ref:instances){Stars stars=ref.get();if(stars!=null&&stars.enabled!=value){stars.enabled=value;stars.invalidateSelf();}}}
    }
    @Override protected void onBoundsChange(Rect b){gradient=new LinearGradient(0,0,b.width(),b.height()/2f,new int[]{0x180453a2,0x000453a2},null,Shader.TileMode.CLAMP);}
    public void draw(Canvas canvas){
      UiPerfStats.starDraw();canvas.drawColor(BG);if(!enabled)return;
      Rect b=getBounds();for(int i=0;i<xs.length;i++){p.setColor(i%4==0?0x552a78c7:0x222598dc);canvas.drawCircle(xs[i]*b.width(),ys[i]*b.height(),i%9==0?1.6f:.7f,p);}
      p.setShader(gradient);canvas.drawRect(b,p);p.setShader(null);
    }
    public void setAlpha(int a){}public void setColorFilter(ColorFilter f){}public int getOpacity(){return PixelFormat.OPAQUE;}
  }
}
