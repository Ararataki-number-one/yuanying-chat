package local.pocketchat;

import android.app.*;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.RippleDrawable;
import java.io.IOException;
import android.os.Build;
import android.text.*;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.*;
import org.json.*;
import java.util.*;

/** One editor owns profile identity, browser policy and preferences. Network connects separately. */
final class EnvironmentEditorUi {
  static final int BASIC=0, NETWORK=1, BROWSER=2, PREFERENCES=3;
  static final String[] SECTIONS={"基本信息","网络配置","浏览器","使用偏好"};

  static JSONObject current(MainActivity a){
    JSONObject values=AppPrefs.values(a),meta=ProfileCatalog.get(a).item(Profiles.slot(a));
    try{
      values.put("name",meta.optString("name"));values.put("group",meta.optString("group"));values.put("notes",meta.optString("notes"));
      if(a.session!=null&&!BrowserPreferences.startBrowser(a)){
        JSONObject desired=DeferredBrowserSettings.desired(a.session);
        values.put("privacyLevel",desired.optInt("privacyLevel"));
        values.put("desktopSite",desired.optBoolean("desktopSite"));
      }
    }catch(JSONException ignored){}
    return values;
  }
  static void returnToList(MainActivity a){if(a.getIntent().getBooleanExtra("returnToEnvironmentList",false)){a.getIntent().removeExtra("returnToEnvironmentList");a.startActivity(new android.content.Intent(a,WindowHomeActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK|android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}}
  static void show(MainActivity a){editTab(a,BASIC);}
  static void editTab(MainActivity a,int tab){
    EnvironmentSpec.Identity expected=editorIdentity(a,null);
    if(expected==null){unavailable(a);returnToList(a);return;}
    ProfileCatalog catalog=ProfileCatalog.get(a);
    JSONObject draft=J.parse(catalog.item(expected.slot).optString("draft"));
    if(draft.length()>0){
      ReferenceUi.Modal prompt=new ReferenceUi.Modal(a,"有未应用的环境草稿");
      prompt.body.addView(ReferenceUi.modalWarning(a,"file","检测到尚未应用的草稿","继续编辑可恢复上次填写的内容；草稿不会改变运行中的环境。"),new LinearLayout.LayoutParams(-1,-2));
      LinearLayout secondaryCard=ReferenceUi.modalActionCard(a);
      ReferenceUi.modalRowAction(secondaryCard,"new","编辑已保存配置",false,()->{prompt.dismiss();edit(a,current(a),tab,expected);});
      LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2);sp.topMargin=a.dp(10);
      prompt.body.addView(secondaryCard,sp);
      prompt.cancel=()->{prompt.dismiss();returnToList(a);};
      prompt.buttons("取消",prompt.cancel,"继续草稿",()->{prompt.dismiss();edit(a,draft,tab,expected);});
      prompt.show();
    }else edit(a,current(a),tab,expected);
  }
  static void edit(MainActivity a,JSONObject value){edit(a,value,BASIC,editorIdentity(a,null));}

  private static int tone(int light,int dark){return AppAppearance.dark()?dark:light;}
  private static int appleBlue(){return ReferenceUi.brandBlue();}
  private static int appleRedText(){return ReferenceUi.redInk();}
  private static int appleGreenText(){return ReferenceUi.greenInk();}
  private static int appleAmberText(){return ReferenceUi.amberInk();}
  private static int appleSecondary(){return ReferenceUi.secondaryInk();}
  private static int appleChevron(){return ReferenceUi.chevronInk();}

  private static final class AppleSurface extends Drawable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF face=new RectF(),edge=new RectF();
    private final float density,radiusDp;
    private final int lightFill,darkFill,lightRim,darkRim;
    AppleSurface(Context c,float radiusDp,int lightFill,int darkFill,int lightRim,int darkRim){
      density=c.getResources().getDisplayMetrics().density;this.radiusDp=radiusDp;
      this.lightFill=lightFill;this.darkFill=darkFill;this.lightRim=lightRim;this.darkRim=darkRim;
    }
    AppleSurface(Context c,float radiusDp,int lightFill,int darkFill){this(c,radiusDp,lightFill,darkFill,0,0);}
    @Override protected void onBoundsChange(Rect b){face.set(b);edge.set(face);edge.inset(.28f*density,.28f*density);}
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      paint.setStyle(Paint.Style.FILL);paint.setColor(dark?darkFill:lightFill);
      canvas.drawRoundRect(face,r,r,paint);
      int rim=dark?darkRim:lightRim;
      if(rim!=0){
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(.55f*density);paint.setColor(rim);
        canvas.drawRoundRect(edge,Math.max(0f,r-.28f*density),Math.max(0f,r-.28f*density),paint);
      }
    }
    @Override public void setAlpha(int a){paint.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){paint.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  private static void appleSection(LinearLayout parent,String title){
    Context c=parent.getContext();
    TextView h=new TextView(c);h.setText(title);h.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,12f);
    h.setTypeface(ReferenceUi.TYPE_SEMIBOLD);h.setLetterSpacing(0.045f);h.setTextColor(tone(0xff4e535e,0xff949ba8));ReferenceUi.crisp(h);
    h.setPadding(DesignUi.dp(c,16),DesignUi.dp(c,parent.getChildCount()==0?6:20),DesignUi.dp(c,16),DesignUi.dp(c,6));
    if(Build.VERSION.SDK_INT>=28)h.setAccessibilityHeading(true);
    parent.addView(h,new LinearLayout.LayoutParams(-1,-2));
  }

  private static void polishSettingsGroup(LinearLayout group){
    group.setElevation(0f);
    group.setBackground(new ReferenceUi.CardSurfaceDrawable(group.getContext(),20f));
    group.setClipToOutline(true);
  }

  private static int glyphInk(String glyph){
    switch(glyph){
      case "browser": return appleBlue();
      case "shield": return appleGreenText();
      default: return tone(0xff565b66,0xffa4aab6);
    }
  }
  private static Drawable glyphTile(Context c,String glyph){
    switch(glyph){
      case "browser": return new AppleSurface(c,9,0xffeef4ff,0xff1b2638,0x200067d8,0x336da4ff);
      case "shield": return new AppleSurface(c,9,0xfff1fbf5,0xff13221c,0x2415804e,0x3334d38b);
      default: return new AppleSurface(c,9,0xfff4f5f8,0xff232732,0x12111827,0x1affffff);
    }
  }

  private static void polishRowIcon(LinearLayout group,String glyph){
    View last=group.getChildAt(group.getChildCount()-1);
    if(!(last instanceof android.view.ViewGroup))return;
    android.view.ViewGroup row=(android.view.ViewGroup)last;
    View first=row.getChildAt(0);
    if(first instanceof ImageView){
      ImageView icon=(ImageView)first;
      Context c=icon.getContext();
      Drawable tile=glyphTile(c,glyph);
      int sz=DesignUi.dp(c,tile!=null?32:22),pad=DesignUi.dp(c,tile!=null?6:1);
      icon.setLayoutParams(new LinearLayout.LayoutParams(sz,sz));
      icon.setPadding(pad,pad,pad,pad);
      icon.setImageDrawable(new Ui.Icon(glyph,glyphInk(glyph)));
      icon.setBackground(tile);
    }
    View tail=row.getChildAt(row.getChildCount()-1);
    if(tail instanceof ImageView&&tail!=first){
      ((ImageView)tail).setImageDrawable(new Ui.Icon("chevron-right",appleChevron()));
    }
  }

  private static final class DualChevronIcon extends Drawable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path=new Path();
    private final int color;
    DualChevronIcon(int color){
      this.color=color;
      paint.setStyle(Paint.Style.STROKE);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
      path.moveTo(8f,9.5f);path.lineTo(12f,5.5f);path.lineTo(16f,9.5f);
      path.moveTo(8f,14.5f);path.lineTo(12f,18.5f);path.lineTo(16f,14.5f);
    }
    @Override public void draw(Canvas canvas){
      Rect b=getBounds();if(b.isEmpty())return;
      canvas.save();canvas.translate(b.left,b.top);canvas.scale(b.width()/24f,b.height()/24f);
      paint.setColor(color);paint.setStrokeWidth(1.9f);
      canvas.drawPath(path,paint);
      canvas.restore();
    }
    @Override public void setAlpha(int a){paint.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){paint.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  private static void styleSpinner(Context c,Spinner spinner){
    NativeControls.prepare(spinner);
    LayerDrawable bg=new LayerDrawable(new Drawable[]{
        new AppleSurface(c,10,0x00000000,0x00000000),
        new DualChevronIcon(appleChevron())});
    bg.setLayerSize(1,DesignUi.dp(c,15),DesignUi.dp(c,15));
    bg.setLayerGravity(1,Gravity.END|Gravity.CENTER_VERTICAL);
    bg.setLayerInset(1,0,0,DesignUi.dp(c,4),0);
    spinner.setBackground(bg);
    spinner.setPadding(0,DesignUi.dp(c,2),DesignUi.dp(c,24),DesignUi.dp(c,2));
  }

  private static LinearLayout editorCard(Context context){
    LinearLayout card=DesignUi.card(context);
    card.setElevation(0f);
    card.setBackground(new ReferenceUi.CardSurfaceDrawable(context,20f));
    card.setClipToOutline(true);
    return card;
  }

  private static void appleFooterNote(LinearLayout parent,String text){
    Context c=parent.getContext();
    TextView note=ReferenceUi.prose(ReferenceUi.workspaceText(c,text,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false));
    note.setTypeface(ReferenceUi.TYPE_REGULAR);
    note.setPadding(DesignUi.dp(c,16),DesignUi.dp(c,8),DesignUi.dp(c,16),0);
    parent.addView(note,new LinearLayout.LayoutParams(-1,-2));
  }

  private static void styleAppleSwitch(Switch option){ReferenceUi.styleSwitch(option);}

  private static Button solidPrimary(Context context,String label,Runnable run){
    Button button=DesignUi.button(context,label,true,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14.5f);
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.015f);ReferenceUi.crisp(button);
    button.setTextColor(ReferenceUi.primaryOnSolid());
    Drawable face=new AppleSurface(context,24,0xff16171a,0xfff6f7f9,0x16ffffff,0x18000000);
    button.setBackground(new RippleDrawable(
        ColorStateList.valueOf(tone(0x24ffffff,0x1a000000)),face,DesignUi.surface(context,Color.WHITE,24,Color.TRANSPARENT)));
    return button;
  }

  private static Button softPrimary(Context context,String label,Runnable run){
    Button button=DesignUi.button(context,label,false,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14.5f);
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.015f);ReferenceUi.crisp(button);
    button.setTextColor(appleBlue());
    Drawable face=new AppleSurface(context,12,0xffeef0f4,0xff272c37,0x18111827,0x26ffffff);
    button.setBackground(new RippleDrawable(ColorStateList.valueOf(tone(0x12111827,0x20ffffff)),face,
        DesignUi.surface(context,Color.WHITE,12,Color.TRANSPARENT)));
    return button;
  }

  private static void cardDivider(LinearLayout parent,int topDp){
    Context context=parent.getContext();
    View line=new View(context);
    line.setBackground(new AppleSurface(context,0,0x14111827,0x18ffffff));
    line.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,Math.max(1,Math.round(ReferenceUi.dpF(context,0.5f))));
    if(topDp>0)params.topMargin=DesignUi.dp(context,topDp);
    parent.addView(line,params);
  }

  private static void disclosureLink(LinearLayout parent,String label,Runnable run){
    Context context=parent.getContext();
    Button link=ReferenceUi.link(context,label,run);
    link.setTextSize(ReferenceUi.BODY_SIZE);
    link.setTextColor(appleBlue());
    link.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));
    link.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
    link.setMinHeight(DesignUi.dp(context,48));link.setMinimumHeight(DesignUi.dp(context,48));
    link.setPadding(0,DesignUi.dp(context,12),0,DesignUi.dp(context,12));
    Ui.Icon chevron=new Ui.Icon("chevron-right",appleChevron());
    int iconSize=DesignUi.dp(context,14);
    chevron.setBounds(0,0,iconSize,iconSize);
    link.setCompoundDrawables(null,null,chevron,null);
    link.setCompoundDrawablePadding(DesignUi.dp(context,6));
    ReferenceUi.readable(link);
    parent.addView(link,new LinearLayout.LayoutParams(-1,-2));
  }

  private static EditText countedInput(LinearLayout form,String title,boolean required,String value,String hint,int limit){
    Context context=form.getContext();
    boolean first=form.getChildCount()==0;
    EditText input=DesignUi.input(form,title,value,hint);
    input.setBackground(new ReferenceUi.FieldWell(context));
    input.setPadding(DesignUi.dp(context,14),DesignUi.dp(context,11),DesignUi.dp(context,14),DesignUi.dp(context,11));
    input.setMinHeight(DesignUi.dp(context,46));
    input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(limit)});
    int labelIndex=form.indexOfChild(input)-1;
    TextView label=(TextView)form.getChildAt(labelIndex);
    int top=first?0:DesignUi.dp(context,16);
    label.setPadding(0,0,0,0);
    label.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,13f);
    label.setTextColor(appleSecondary());
    label.setTypeface(ReferenceUi.TYPE_SEMIBOLD);label.setLetterSpacing(0.015f);
    ReferenceUi.crisp(label);
    if(input.getId()==View.NO_ID)input.setId(View.generateViewId());
    label.setLabelFor(input.getId());
    LinearLayout left=DesignUi.row(context);
    form.removeViewAt(labelIndex);
    left.addView(label,new LinearLayout.LayoutParams(-2,-2));
    if(required){
      TextView tag=new TextView(context);tag.setText("必填");tag.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,11f);
      tag.setTypeface(ReferenceUi.TYPE_SEMIBOLD);tag.setLetterSpacing(0.025f);tag.setTextColor(appleBlue());ReferenceUi.crisp(tag);
      tag.setPadding(DesignUi.dp(context,6),DesignUi.dp(context,2),DesignUi.dp(context,6),DesignUi.dp(context,2));
      tag.setBackground(new AppleSurface(context,7,0xffeef4ff,0xff1b2638));
      LinearLayout.LayoutParams tagLayout=new LinearLayout.LayoutParams(-2,-2);
      tagLayout.setMarginStart(DesignUi.dp(context,6));
      left.addView(tag,tagLayout);
    }
    TextView count=ReferenceUi.mono(ReferenceUi.crisp(ReferenceUi.workspaceText(context,"",ReferenceUi.SECONDARY_SIZE,appleSecondary(),false)));
    count.setFontFeatureSettings("tnum");
    count.setPaddingRelative(DesignUi.dp(context,8),0,0,0);
    count.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout heading=DesignUi.row(context);
    heading.setPadding(DesignUi.dp(context,2),top,DesignUi.dp(context,2),DesignUi.dp(context,7));
    heading.addView(left,new LinearLayout.LayoutParams(0,-2,1));
    heading.addView(count,new LinearLayout.LayoutParams(-2,-2));
    form.addView(heading,labelIndex,new LinearLayout.LayoutParams(-1,-2));
    count.setText(context.getString(R.string.secondary_character_count,input.length(),limit));
    input.addTextChangedListener(new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence text,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence text,int start,int before,int count){}
      @Override public void afterTextChanged(Editable text){count.setText(context.getString(R.string.secondary_character_count,text.length(),limit));}
    });
    return input;
  }

  private static void addGroupShortcuts(LinearLayout form,EditText group){
    Context context=form.getContext();
    LinearLayout row=DesignUi.row(context);
    row.setPadding(0,DesignUi.dp(context,4),0,0);
    String[] labels={"工作","个人","清空分组"};
    String[] values={"工作","个人",""};
    Button[] shortcuts=new Button[labels.length];
    for(int i=0;i<labels.length;i++){
      String value=values[i];
      boolean clearAction=value.isEmpty();
      Button shortcut=ReferenceUi.link(context,labels[i],()->{
        group.setText(value);
        group.setSelection(group.length());
      });
      shortcut.setContentDescription(clearAction?"清空当前分组输入":"填入分组 "+value);
      shortcut.setTextSize(ReferenceUi.ACTION_SIZE);
      ReferenceUi.readable(shortcut);
      shortcut.setGravity(Gravity.CENTER);
      shortcut.setMinWidth(0);shortcut.setMinimumWidth(0);
      shortcut.setMinHeight(DesignUi.dp(context,44));
      shortcut.setMinimumHeight(DesignUi.dp(context,44));
      if(clearAction){
        shortcut.setPadding(DesignUi.dp(context,6),0,DesignUi.dp(context,2),0);
        row.addView(new View(context),new LinearLayout.LayoutParams(0,1,1));
        row.addView(shortcut,new LinearLayout.LayoutParams(-2,-2));
      }else{
        shortcut.setPadding(DesignUi.dp(context,13),0,DesignUi.dp(context,13),0);
        LinearLayout.LayoutParams chipLayout=new LinearLayout.LayoutParams(-2,-2);
        if(i>0)chipLayout.setMarginStart(DesignUi.dp(context,8));
        row.addView(shortcut,chipLayout);
      }
      shortcuts[i]=shortcut;
    }

    Runnable updateSelection=()->{
      String current=group.getText().toString();
      for(int i=0;i<shortcuts.length;i++){
        Button shortcut=shortcuts[i];
        boolean clearAction=values[i].isEmpty();
        if(clearAction){
          boolean hasGroup=!current.isEmpty();
          shortcut.setSelected(false);
          shortcut.setEnabled(hasGroup);
          shortcut.setTextColor(appleSecondary());
          continue;
        }
        boolean selected=values[i].equals(current);
        shortcut.setSelected(selected);
        shortcut.setTextColor(selected?appleBlue():ReferenceUi.inkPrimary());
        shortcut.setTypeface(selected?ReferenceUi.TYPE_SEMIBOLD:ReferenceUi.TYPE_MEDIUM);
        shortcut.setLetterSpacing(0.015f);ReferenceUi.crisp(shortcut);
        Drawable face=selected
            ?new AppleSurface(context,7,0xffeef4ff,0xff1b2638,0x280067d8,0x3d6da4ff)
            :new AppleSurface(context,7,0xfff6f7f9,0xff232732,0x12111827,0x18ffffff);
        int vInset=DesignUi.dp(context,7);
        shortcut.setBackground(new AppAppearance.GlassRipple(
            new InsetDrawable(face,0,vInset,0,vInset),
            new InsetDrawable(DesignUi.surface(context,Color.WHITE,7,Color.TRANSPARENT),0,vInset,0,vInset)));
      }
    };
    updateSelection.run();
    group.addTextChangedListener(new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence text,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence text,int start,int before,int count){}
      @Override public void afterTextChanged(Editable text){updateSelection.run();}
    });
    LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(-1,-2);
    form.addView(row,layout);
  }

  private static LinearLayout editorBody(MainActivity a,LinearLayout root,Runnable back){
    root.setClipChildren(false);root.setClipToPadding(false);
    root.setBackgroundColor(ReferenceUi.canvasBg());
    LinearLayout body=DesignUi.column(a);
    body.setPadding(a.dp(16),a.dp(4),a.dp(16),a.dp(98));
    ScrollView scroll=new ScrollView(a);
    scroll.setFillViewport(true);
    scroll.setClipToPadding(false);
    NativeControls.prepare(scroll);
    scroll.addView(body,new ScrollView.LayoutParams(-1,-2));
    FrameLayout header=ReferenceUi.horologyHeader(a,"编辑 · "+Profiles.display(a,Profiles.slot(a)),
        "分组、网络、浏览器与使用偏好",back,scroll);
    root.addView(header,new LinearLayout.LayoutParams(-1,-2));
    FrameLayout viewport=new FrameLayout(a);
    viewport.setClipChildren(true);viewport.setClipToPadding(true);
    viewport.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
    FrameLayout stage=new FrameLayout(a);
    stage.setClipChildren(false);stage.setClipToPadding(false);
    stage.addView(viewport,new FrameLayout.LayoutParams(-1,-1));
    root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));
    return body;
  }

  static void edit(MainActivity a,JSONObject initial,int tab,EnvironmentSpec.Identity identity){
    // Old drafts may lack newly introduced metadata; inherit its current value.
    ChatSession owner=BrowserPreferences.engine(a)==EnvironmentEngine.GECKO?a.session:null;
    if(!editorCurrent(a,identity,owner)){unavailable(a);returnToList(a);return;}
    JSONObject existing=current(a);final Runnable[] exit={null};final boolean[] saving={false};final JSONObject[] browserBaseline={null};final Dialog dialog=new ThemedDialog(a){@Override public void onBackPressed(){if(exit[0]!=null)exit[0].run();else super.onBackPressed();}};
    LinearLayout root=DesignUi.screen(a),outer=editorBody(a,root,()->{if(exit[0]!=null)exit[0].run();});
    root.setFocusableInTouchMode(true);
    LinearLayout tabs=DesignUi.column(a);outer.addView(tabs);
    LinearLayout basic=DesignUi.column(a),network=DesignUi.column(a),browser=DesignUi.column(a),preferences=DesignUi.column(a);
    FrameLayoutHost host=new FrameLayoutHost(a,basic,network,browser,preferences);outer.addView(host);

    LinearLayout info=editorCard(a);
    info.setPadding(a.dp(16),a.dp(16),a.dp(16),a.dp(16));
    EditText name=countedInput(info,"环境名称",true,initial.optString("name",existing.optString("name")),"例如：工作账号",24);
    EditText group=countedInput(info,"分组",false,initial.optString("group",existing.optString("group")),"留空为未分组",12);
    addGroupShortcuts(info,group);
    EditText notes=countedInput(info,"备注",false,initial.optString("notes",existing.optString("notes")),"用途说明",120);
    notes.setSingleLine(false);
    notes.setMinLines(3);
    notes.setMaxLines(4);
    notes.setGravity(Gravity.TOP|Gravity.START);
    ReferenceUi.readable(notes);
    DesignUi.addCard(basic,info);

    LinearLayout net=editorCard(a);
    net.setPadding(a.dp(16),a.dp(14),a.dp(16),a.dp(16));
    DesignUi.field(net,"网络方式",DesignNetworkUi.mode(a));
    if(owner!=null){
      cardDivider(net,0);
      String statusLabel=owner.offline?"手机离线":owner.networkReady?"已连接":"待连接";
      int statusTone=owner.offline?appleRedText():owner.networkReady?appleGreenText():appleAmberText();
      LinearLayout statusRow=DesignUi.row(a);
      statusRow.setPadding(0,a.dp(9),0,a.dp(9));
      TextView statusKey=ReferenceUi.workspaceText(a,"连接状态",ReferenceUi.ACTION_SIZE,ReferenceUi.specKeyInk(),false);
      statusKey.setTypeface(ReferenceUi.TYPE_REGULAR);
      statusRow.addView(statusKey,new LinearLayout.LayoutParams(a.dp(88),-2));
      ImageView dot=new ImageView(a);
      dot.setImageDrawable(new ReferenceUi.HaloDotDrawable(a,statusTone));
      dot.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      LinearLayout.LayoutParams dotParams=new LinearLayout.LayoutParams(a.dp(10),a.dp(10));
      dotParams.setMarginEnd(a.dp(6));
      statusRow.addView(dot,dotParams);
      TextView statusVal=new TextView(a);statusVal.setText(statusLabel);statusVal.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,13.5f);
      statusVal.setTypeface(ReferenceUi.TYPE_SEMIBOLD);statusVal.setTextColor(statusTone);ReferenceUi.crisp(statusVal);
      statusRow.addView(statusVal,new LinearLayout.LayoutParams(0,-2,1));
      net.addView(statusRow,new LinearLayout.LayoutParams(-1,-2));
    }
    DesignUi.addCard(network,net);

    LinearLayout kernelCard=SettingsWorkspaceStyle.group(a);
    polishSettingsGroup(kernelCard);
    SettingsWorkspaceStyle.row(a,kernelCard,"浏览器内核与首页","查看本环境的内核，修改默认首页","browser",()->BrowserSettingsUi.show(a));
    polishRowIcon(kernelCard,"browser");
    DesignUi.addCard(browser,kernelCard);
    final boolean[] desktopSelected={initial.optBoolean("desktopSite",existing.optBoolean("desktopSite"))};
    final int[] privacySelected={owner==null?1:Math.max(0,Math.min(2,initial.optInt("privacyLevel",owner.privacy.level())))};
    final Runnable[] renderDisplayChoices={null},renderPrivacyChoices={null};
    if(owner==null){
      appleFooterNote(browser,"Chromium 的网页显示、站点权限等设置可在浏览器菜单中调整。");
    }else{
      appleSection(browser,"网页显示");
      LinearLayout display=editorCard(a);
      display.setPadding(0,0,0,0);
      renderDisplayChoices[0]=()->{
        display.removeAllViews();
        ReferenceUi.modalChoice(display,"手机版网站","默认移动排版，单手阅读更轻便",!desktopSelected[0],()->{desktopSelected[0]=false;renderDisplayChoices[0].run();});
        ReferenceUi.modalChoice(display,"电脑版网站","展示完整侧栏与工具，按手机宽度排版可双指缩放",desktopSelected[0],()->{desktopSelected[0]=true;renderDisplayChoices[0].run();});
      };
      renderDisplayChoices[0].run();
      browser.addView(display,new LinearLayout.LayoutParams(-1,-2));
      appleFooterNote(browser,"电脑版按手机宽度排版，可双指缩放。回复期间可保存，结束后自动应用。");
      appleSection(browser,"隐私保护");
      LinearLayout protection=editorCard(a);
      protection.setPadding(0,0,0,0);
      String[] privacyLabels={"兼容","标准","强化"};
      String[] privacyHints={"仅拦截常见追踪，优先保障登录验证与音视频","平衡隐私隔离与主流网页兼容（推荐）","增强反指纹与严格隔离，可能影响验证和音视频"};
      renderPrivacyChoices[0]=()->{
        protection.removeAllViews();
        for(int i=0;i<privacyLabels.length;i++){
          final int idx=i;
          ReferenceUi.modalChoice(protection,privacyLabels[i],privacyHints[i],privacySelected[0]==i,()->{privacySelected[0]=idx;renderPrivacyChoices[0].run();});
        }
        protection.addView(ReferenceUi.modalDivider(a,16));
        LinearLayout linkBox=DesignUi.column(a);linkBox.setPadding(a.dp(16),0,a.dp(16),0);
        disclosureLink(linkBox,"保护详情",()->ReferenceUi.message(a,"隐私保护",owner.privacy.summary()));
        protection.addView(linkBox,new LinearLayout.LayoutParams(-1,-2));
      };
      renderPrivacyChoices[0].run();
      browser.addView(protection,new LinearLayout.LayoutParams(-1,-2));
      appleFooterNote(browser,"强化保护可能影响验证和音视频。");
      appleSection(browser,"环境与诊断");
      LinearLayout toolsCard=SettingsWorkspaceStyle.group(a);
      polishSettingsGroup(toolsCard);
      SettingsWorkspaceStyle.row(a,toolsCard,"环境模板与生效状态","配置浏览器模板与网页语言","window",()->{
        FingerprintTemplateUi.show(a,(spec,done)->owner.applyIdentityTemplate(a,spec,issue->{
          // The parent editor remains open under the template dialog. Refresh its
          // browser fields so a later name/preferences save cannot revert a template.
          if((issue==null||issue.isEmpty())&&!a.isDestroyed()&&a.session==owner&&dialog.isShowing()){
            boolean desktop=spec.desktop();int level=Math.max(0,Math.min(2,spec.protectionLevel()));
            desktopSelected[0]=desktop;privacySelected[0]=level;
            if(renderDisplayChoices[0]!=null)renderDisplayChoices[0].run();
            if(renderPrivacyChoices[0]!=null)renderPrivacyChoices[0].run();
            if(browserBaseline[0]!=null)try{browserBaseline[0].put("desktopSite",desktop);browserBaseline[0].put("privacyLevel",level);}catch(Exception ignored){}
          }
          done.accept(issue);
        }));
      });
      polishRowIcon(toolsCard,"window");
      SettingsWorkspaceStyle.row(a,toolsCard,"查看环境自检","检查当前环境隔离与模板状态","shield",()->EnvironmentAuditUi.show(a));
      polishRowIcon(toolsCard,"shield");
      SettingsWorkspaceStyle.row(a,toolsCard,"浏览器信息",GeckoWebView.VERSION,"info",()->{
        android.util.DisplayMetrics metrics=a.getResources().getDisplayMetrics();
        ReferenceUi.Modal details=new ReferenceUi.Modal(a,"浏览器信息");
        LinearLayout specs=ReferenceUi.modalGroup(a);
        ReferenceUi.modalFieldRow(specs,"内核",GeckoWebView.VERSION,true);
        ReferenceUi.modalFieldRow(specs,"网页显示",BrowserDisplay.label(owner.privacy.desktop),false);
        ReferenceUi.modalFieldRow(specs,"系统","Android "+Build.VERSION.RELEASE+" / API "+Build.VERSION.SDK_INT,false);
        ReferenceUi.modalFieldRow(specs,"屏幕",metrics.widthPixels+" × "+metrics.heightPixels,false);
        ReferenceUi.modalFieldRow(specs,"语言",Locale.getDefault().toLanguageTag(),false);
        ReferenceUi.modalFieldRow(specs,"时区",TimeZone.getDefault().getID(),false);
        ReferenceUi.modalFieldRow(specs,"定位","不向网页授权",false);
        details.body.addView(specs,new LinearLayout.LayoutParams(-1,-2));
        ReferenceUi.modalSection(details.body,"User-Agent");
        LinearLayout uaCard=ReferenceUi.modalGroup(a);uaCard.setPadding(a.dp(16),a.dp(12),a.dp(16),a.dp(12));
        String uaValue=a.remote.getSettings().getUserAgentString();
        TextView ua=ReferenceUi.workspaceText(a,uaValue,ReferenceUi.SECONDARY_SIZE,DesignUi.TEXT,false);
        ua.setTypeface(android.graphics.Typeface.MONOSPACE);ua.setTextIsSelectable(true);
        uaCard.addView(ua,new LinearLayout.LayoutParams(-1,-2));
        details.body.addView(uaCard,new LinearLayout.LayoutParams(-1,-2));
        ReferenceUi.modalFooterNote(details.body,"网页显示方式支持手机版 / 电脑版；原生语言与模板可在“环境模板”中配置。独立时区和深层指纹控制的支持状态以模板及自检为准。");
        details.buttons("关闭",details::dismiss,"复制 UA",()->{
          android.content.ClipboardManager clipboard=(android.content.ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
          if(clipboard!=null){clipboard.setPrimaryClip(android.content.ClipData.newPlainText("User-Agent",uaValue));details.primary().setText("已复制");}
        });details.show();
      });
      polishRowIcon(toolsCard,"info");
      browser.addView(toolsCard,new LinearLayout.LayoutParams(-1,-2));
    }

    Switch[] options=new Switch[AppPrefs.KEYS.length];
    String[] headings={"会话与恢复","下载与存储","连接检测"};
    String[][] preferenceGroups={{"saveDraft","restoreScroll"},{"wifiDownloads","cleanTemporaryCache"},{"automaticLatencyChecks"}};
    List<String> preferenceKeys=Arrays.asList(AppPrefs.KEYS);
    for(int section=0;section<preferenceGroups.length;section++){
      appleSection(preferences,headings[section]);
      LinearLayout card=editorCard(a);
      card.setPadding(a.dp(16),a.dp(4),a.dp(16),a.dp(4));
      int added=0;
      for(String key:preferenceGroups[section]){
        int i=preferenceKeys.indexOf(key);if(i<0)continue;
        if(added>0)cardDivider(card,0);
        options[i]=new Switch(a);options[i].setText(AppPrefs.LABELS[i]);
        NativeControls.prepare(options[i]);
        options[i].setTextColor(DesignUi.TEXT);options[i].setTextSize(15);
        options[i].setPadding(0,a.dp(10),0,a.dp(10));
        ReferenceUi.readable(options[i]);
        options[i].setChecked(initial.has(AppPrefs.KEYS[i])?initial.optBoolean(AppPrefs.KEYS[i]):AppPrefs.enabled(a,AppPrefs.KEYS[i]));
        styleAppleSwitch(options[i]);
        card.addView(options[i],new LinearLayout.LayoutParams(-1,-2));
        added++;
      }
      preferences.addView(card,new LinearLayout.LayoutParams(-1,-2));
      if(section==1){
        LinearLayout storageCard=SettingsWorkspaceStyle.group(a);
        polishSettingsGroup(storageCard);
        SettingsWorkspaceStyle.row(a,storageCard,"下载位置与存储","查看保存目录与可清理旧临时文件","tray",()->storage(a));
        polishRowIcon(storageCard,"tray");
        LinearLayout.LayoutParams storageParams=new LinearLayout.LayoutParams(-1,-2);
        storageParams.topMargin=a.dp(10);
        preferences.addView(storageCard,storageParams);
      }
      if(section==2){
        appleFooterNote(preferences,"自动检测会访问公开测试地址；关闭可减少后台请求，仍可手动检测。");
      }
    }

    java.util.function.Supplier<JSONObject> read=()->{
      JSONObject value=J.obj("name",name.getText().toString().trim(),"group",group.getText().toString().trim(),"notes",notes.getText().toString().trim());
      if(owner!=null)try{
        int level=privacySelected[0];boolean desktop=desktopSelected[0];
        value.put("privacyLevel",level);value.put("desktopSite",desktop);
        value.put(BrowserEditIntent.EDITED,BrowserEditIntent.fieldsChanged(browserBaseline[0],level,desktop));
      }catch(JSONException ignored){}
      for(int i=0;i<options.length;i++)if(options[i]!=null)try{value.put(AppPrefs.KEYS[i],options[i].isChecked());}catch(Exception ignored){}return value;
    };
    final JSONObject baseline=read.get();browserBaseline[0]=baseline;
    exit[0]=()->{
      if(saving[0]){a.status("正在保存环境，请稍候");return;}
      JSONObject value=read.get();boolean dirty=false;java.util.Iterator<String> keys=value.keys();while(keys.hasNext()){String key=keys.next();if(!java.util.Objects.equals(value.opt(key),baseline.opt(key))){dirty=true;break;}}
      if(!dirty){dialog.dismiss();return;}
      ReferenceUi.Modal prompt=new ReferenceUi.Modal(a,"退出前保留修改？").hideClose();
      prompt.body.addView(ReferenceUi.modalWarning(a,"file","当前修改尚未保存","存为草稿只会保存填写内容，不会改变运行中的环境。"),new LinearLayout.LayoutParams(-1,-2));
      LinearLayout discardCard=ReferenceUi.modalActionCard(a);
      ReferenceUi.modalRowAction(discardCard,"trash","放弃本次修改",true,()->{prompt.dismiss();dialog.dismiss();});
      LinearLayout.LayoutParams dpLayout=new LinearLayout.LayoutParams(-1,-2);dpLayout.topMargin=a.dp(10);
      prompt.body.addView(discardCard,dpLayout);
      prompt.buttons("继续编辑",prompt::dismiss,"存草稿并退出",()->{prompt.dismiss();if(saveDraft(a,identity,value,owner==null))dialog.dismiss();});
      prompt.show();
    };
    Button netButton=softPrimary(a,"配置网络",()->{
      if(!saveDraft(a,identity,read.get(),owner==null))return;
      a.getIntent().removeExtra("returnToEnvironmentList");dialog.dismiss();a.status("编辑内容已保存为草稿");a.hub.select(AppHub.NETWORK);
    });
    Ui.Icon netArrow=new Ui.Icon("chevron-right",appleBlue());
    int arrowSz=a.dp(15);
    netArrow.setBounds(0,0,arrowSz,arrowSz);
    netButton.setCompoundDrawables(null,null,netArrow,null);
    netButton.setCompoundDrawablePadding(a.dp(4));
    LinearLayout.LayoutParams netBtnParams=new LinearLayout.LayoutParams(-1,-2);
    netBtnParams.topMargin=a.dp(14);
    net.addView(netButton,netBtnParams);
    appleFooterNote(network,"网络线路按环境独立配置；点击“配置网络”会先暂存当前编辑内容为草稿，再跳转至网络页。");
    updateTabs(a,tabs,host,tab);
    TextView validation=ReferenceUi.workspaceText(a,"",ReferenceUi.ACTION_SIZE,appleRedText(),false);
    validation.setPadding(a.dp(14),a.dp(9),a.dp(14),a.dp(9));
    validation.setVisibility(android.view.View.GONE);
    validation.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
    LinearLayout dockHost=DesignUi.column(a);
    dockHost.setClipChildren(false);dockHost.setClipToPadding(false);
    dockHost.setBackground(EnvironmentWorkspaceStyle.scrollEdge(a));
    dockHost.setPadding(a.dp(10),a.dp(18),a.dp(10),a.dp(10));
    LinearLayout.LayoutParams valParams=new LinearLayout.LayoutParams(-1,-2);
    valParams.setMargins(a.dp(4),0,a.dp(4),a.dp(8));
    dockHost.addView(validation,valParams);
    LinearLayout actions=new LinearLayout(a){
      @Override protected int[] onCreateDrawableState(int extraSpace){
        return GlassMotion.childState(this,super.onCreateDrawableState(extraSpace+1));
      }
      @Override public void onVisibilityAggregated(boolean visible){
        super.onVisibilityAggregated(visible);if(!visible)GlassMotion.reset(this);
      }
    };
    actions.setOrientation(LinearLayout.HORIZONTAL);
    actions.setGravity(Gravity.CENTER_VERTICAL);
    actions.setBackground(DesignUi.glass(a,32));
    GlassMotion.press(actions,false);
    actions.setPadding(a.dp(12),a.dp(10),a.dp(10),a.dp(10));
    int actionIndex=0;
    for(Button button:new Button[]{ReferenceUi.link(a,"取消",()->exit[0].run()),ReferenceUi.link(a,"存草稿",()->{if(saveDraft(a,identity,read.get(),owner==null)){dialog.dismiss();a.status("环境草稿已保存，尚未应用");}}),solidPrimary(a,"保存环境",()->{
      if(saving[0])return;saving[0]=true;editingEnabled(root,false);validation.setText("正在保存…");validation.setTextColor(appleSecondary());validation.setBackground(new ReferenceUi.CardSurfaceDrawable(a,14f));validation.setVisibility(android.view.View.VISIBLE);
      JSONObject value=read.get();java.util.function.Consumer<Boolean> done=ok->{
        saving[0]=false;if(a.isDestroyed())return;if(ok){ReferenceUi.hapticConfirm(root);dialog.dismiss();return;}
        editingEnabled(root,true);
        if(value.optString("name").isEmpty()){updateTabs(a,tabs,host,BASIC);name.requestFocus();ReferenceUi.hapticReject(name);validation.setText("先给环境填写一个名称，再保存。");}
        else{if(owner!=null&&(value.optInt("privacyLevel")!=owner.privacy.level()||value.optBoolean("desktopSite")!=owner.privacy.wantsDesktop()))updateTabs(a,tabs,host,BROWSER);ReferenceUi.hapticReject(validation);validation.setText(a.lastUiStatus);}
        validation.setTextColor(appleRedText());validation.setBackground(new ReferenceUi.AccentBannerDrawable(a,-1));validation.setVisibility(android.view.View.VISIBLE);
      };
      if(owner==null)done.accept(applyNative(a,identity,value,name));
      else applySafely(a,value,name,()->editorCurrent(a,identity,owner),done);
    })}){
      ReferenceUi.readable(button);
      if(actionIndex==0)button.setTextColor(appleSecondary());
      else if(actionIndex==1)button.setTextColor(appleBlue());
      if(actionIndex<2&&button instanceof DesignUi.ActionButton)((DesignUi.ActionButton)button).pressedSurface(actions);
      button.setMinWidth(0);button.setMinimumWidth(0);
      button.setPadding(a.dp(8),a.dp(8),a.dp(8),a.dp(8));
      LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,actionIndex==2?1.55f:actionIndex==1?1f:.9f);
      p.setMargins(a.dp(2),0,a.dp(2),0);actions.addView(button,p);actionIndex++;
    }
    dockHost.addView(actions,new LinearLayout.LayoutParams(-1,-2));
    FrameLayout stage=(FrameLayout)root.getChildAt(root.getChildCount()-1);
    FrameLayout.LayoutParams dockParams=new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM);
    stage.addView(dockHost,dockParams);
    dialog.setOnDismissListener(d->returnToList(a));
    dialog.setCanceledOnTouchOutside(false);
    dialog.setContentView(root);
    Window window=dialog.getWindow();
    window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_HIDDEN);
    root.requestFocus();
    dialog.show();
    window.setBackgroundDrawableResource(android.R.color.transparent);
    window.setLayout(-1,-1);
    window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
    window.setStatusBarColor(DesignUi.BG);
    window.setNavigationBarColor(DesignUi.BG);
    AppAppearance.shown(dialog);
    for(Switch opt:options)if(opt!=null)styleAppleSwitch(opt);
  }
  static void updateTabs(MainActivity a,LinearLayout tabs,FrameLayoutHost host,int selected){
    int current=Math.max(0,Math.min(SECTIONS.length-1,selected));
    host.page(current);
    NativeControls.form(host);
    tabs.removeAllViews();
    LinearLayout track=DesignUi.row(a);
    track.setBackground(new ReferenceUi.RecessedBoxDrawable(a,14f));
    int inset=a.dp(3);
    track.setPadding(inset,inset,inset,inset);
    for(int i=0;i<SECTIONS.length;i++){
      int index=i;
      boolean active=index==current;
      Button control=ReferenceUi.link(a,SECTIONS[index],()->{ReferenceUi.hapticTick(track);updateTabs(a,tabs,host,index);});
      control.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,13f);
      control.setSingleLine(true);
      control.setTypeface(active?ReferenceUi.TYPE_SEMIBOLD:ReferenceUi.TYPE_MEDIUM);
      control.setLetterSpacing(0.005f);ReferenceUi.crisp(control);
      control.setTextColor(active?ReferenceUi.inkPrimary():appleSecondary());
      control.setSelected(active);
      control.setMinWidth(0);control.setMinimumWidth(0);
      control.setMinHeight(a.dp(36));control.setMinimumHeight(a.dp(36));
      control.setPadding(a.dp(4),a.dp(6),a.dp(4),a.dp(6));
      if(active){
        control.setBackground(new ReferenceUi.SegmentedThumbDrawable(a));
        control.setElevation(0f);
      }else{
        control.setBackground(Ui.ripple(a,Color.TRANSPARENT,10));
        control.setElevation(0f);
      }
      LinearLayout.LayoutParams slot=new LinearLayout.LayoutParams(0,-2,1);
      if(i>0)slot.setMarginStart(a.dp(2));
      track.addView(control,slot);
    }
    LinearLayout.LayoutParams trackLayout=new LinearLayout.LayoutParams(-1,-2);
    trackLayout.topMargin=a.dp(2);
    trackLayout.bottomMargin=a.dp(12);
    tabs.addView(track,trackLayout);
  }
  static boolean saveDraft(MainActivity a,EnvironmentSpec.Identity identity,JSONObject value,boolean nativeEditor){
    if(a.isDestroyed()||a.isFinishing())return false;
    ProfileCatalog catalog=ProfileCatalog.get(a);
    try{
      catalog.withIdentity(identity,()->{
        JSONObject draft=value;
        if(nativeEditor){
          // Native editing can update common fields while keeping Gecko's
          // draft browser choices available when that engine is opened again.
          draft=J.parse(catalog.item(identity.slot).optString("draft"));
          for(Iterator<String> keys=value.keys();keys.hasNext();){
            String key=keys.next();draft.put(key,value.get(key));
          }
        }
        catalog.draft(identity.slot,draft);return null;
      });
      return true;
    }catch(Exception changed){ReferenceUi.message(a,"环境草稿","环境已变化或草稿暂时无法保存，请重新打开环境后重试。");return false;}
  }
  static boolean validMetadata(MainActivity a,JSONObject value,EditText name){
    String title=value.optString("name").trim();
    if(title.isEmpty()||title.length()>24){name.setError("请输入 1–24 字名称");return false;}
    if(value.optString("group").length()>12||value.optString("notes").length()>120){a.status("分组最多 12 字，备注最多 120 字");return false;}
    return true;
  }
  static EnvironmentSpec.Identity editorIdentity(MainActivity a,ChatSession owner){
    if(a.isDestroyed()||a.isFinishing()||owner!=null&&(a.session!=owner||owner.deleted))return null;
    try{
      EnvironmentSpec.Identity identity=ProfileCatalog.get(a).identity(Profiles.slot(a));
      if(owner!=null&&(identity.slot!=Profiles.slot(owner.context)||identity.generation!=owner.environmentGeneration
          ||!identity.environmentId.equals(owner.environmentId)))return null;
      return identity;
    }catch(Exception unavailable){return null;}
  }
  static boolean editorCurrent(MainActivity a,EnvironmentSpec.Identity expected,ChatSession owner){
    return expected!=null&&expected.equals(editorIdentity(a,owner));
  }
  static void unavailable(MainActivity a){a.status("环境已变化或暂不可用。请重新打开环境编辑。");}
  // Preference memory can change before disk confirmation, and SQLite commits separately.
  static void saveFailed(MainActivity a){a.status("配置未能确认保存。填写内容仍保留，请重试。");}

  static boolean applyNative(MainActivity a,EnvironmentSpec.Identity identity,JSONObject value,EditText name){
    if(!editorCurrent(a,identity,null)){unavailable(a);return false;}
    if(!validMetadata(a,value,name))return false;
    ProfileCatalog catalog=ProfileCatalog.get(a);
    try{
      catalog.withIdentity(identity,()->{
        catalog.details(identity.slot,value.optString("group"),value.optString("notes"));
        if(!AppPrefs.apply(Profiles.context(a,identity.slot),value))throw new IOException("Environment preferences not committed");
        Profiles.rename(a,identity.slot,value.optString("name"));
        return null;
      });
    }catch(Exception changed){saveFailed(a);return false;}
    if(a.hub!=null)a.hub.refresh();
    a.status("环境配置已保存");return true;
  }
  static boolean apply(MainActivity a,JSONObject value,EditText name){
    ChatSession s=a.session;
    EnvironmentSpec.Identity identity=editorIdentity(a,s);
    if(s==null||identity==null){unavailable(a);return false;}
    if(!validMetadata(a,value,name))return false;
    int level=value.optInt("privacyLevel",s.privacy.level());
    if(level<0||level>2){a.status("请选择有效的保护等级");return false;}
    boolean desktop=value.optBoolean("desktopSite",s.privacy.wantsDesktop());
    boolean queueUnavailable=s.identity!=null&&s.identity.queueUnavailable;
    boolean preserveBrowser=BrowserEditIntent.preserveFailedCandidate(queueUnavailable,value);
    boolean change=!preserveBrowser&&level!=s.privacy.level();
    boolean displayChange=!preserveBrowser&&desktop!=s.privacy.wantsDesktop();
    boolean failedOverride=BrowserEditIntent.explicitFailedOverride(queueUnavailable,value);
    boolean browserIntent=BrowserEditIntent.browserIntent(queueUnavailable,value,change||displayChange,s.identityApplicationPending);
    // A failed candidate can contain locale-only changes even when the visible
    // fields now equal the running browser. Mirror the explicit replacement
    // before the existing safe queue can apply it.
    boolean deferred=browserIntent&&(failedOverride||browserBusy(s));

    ProfileCatalog catalog=ProfileCatalog.get(a);
    try{
      catalog.withIdentity(identity,()->{
        catalog.details(identity.slot,value.optString("group"),value.optString("notes"));
        SharedPreferences.Editor prefs=AppPrefs.edit(s.prefs,value);
        if(deferred){
          prefs.putInt(DeferredBrowserSettings.NEXT_PRIVACY_LEVEL,level).putBoolean(DeferredBrowserSettings.NEXT_DESKTOP_SITE,desktop);
        }else if(!preserveBrowser){
          catalog.browserDisplay(identity.slot,desktop);
          prefs.putInt("privacyLevel",level).remove(DeferredBrowserSettings.NEXT_PRIVACY_LEVEL).remove(DeferredBrowserSettings.NEXT_DESKTOP_SITE);
        }
        // A preference failure rolls back the catalog changes, including this draft removal.
        catalog.draft(identity.slot,null);
        if(!prefs.commit())throw new IOException("Environment preferences not committed");
        Profiles.rename(a,identity.slot,value.optString("name"));
        return null;
      });
    }catch(Exception changed){saveFailed(a);return false;}
    if(!editorCurrent(a,identity,s)){unavailable(a);return false;}
    if(browserIntent)s.browserIdentitySaved(level,desktop);
    if(!deferred&&browserIntent)s.applyBrowserSettings(change);
    s.audit.refresh(true);ProfileCatalog.get(a).heartbeat(s,true);if(a.hub!=null)a.hub.refresh();if(a.designChrome!=null)a.designChrome.update();a.status(preserveBrowser?"环境资料已保存；上次模板排队失败，期望配置已保留，请重新保存模板":deferred?"环境已保存，当前回复结束后自动应用网页设置":displayChange&&!s.networkReady?"环境配置已保存，加载网页时应用显示方式":"环境配置已保存");return true;
  }
  static String browserTaskReason(ChatSession s){return BrowserSettingsPolicy.reason(s.pending!=null,s.submitting,s.operation,s.transferActive,s.uploading(),false);}
  static boolean browserBusy(ChatSession s){boolean reply=BrowserSettingsPolicy.currentReply(MainActivity.chatUrl(s.web.getUrl()),WebReplyObserver.same(s.web.getUrl(),s.state.optString("url")),s.state.optBoolean("busy"),s.stateEpoch,s.navigationEpoch);return BrowserDisplay.busy(ProfileUi.working(s),s.navigating,s.connecting,s.recoveryScheduled,reply);}
  static void editingEnabled(android.view.View view,boolean enabled){view.setEnabled(enabled);if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)editingEnabled(group.getChildAt(i),enabled);}}
  static boolean guardedApply(MainActivity a,JSONObject value,EditText name,java.util.function.BooleanSupplier current){if(!current.getAsBoolean()){a.status("设置已由较新的配置替换，旧修改没有应用");return false;}return apply(a,value,name);}
  static void applySafely(MainActivity a,JSONObject value,EditText name,java.util.function.Consumer<Boolean> done){applySafely(a,value,name,()->true,done);}
  static void applySafely(MainActivity a,JSONObject value,EditText name,java.util.function.BooleanSupplier current,java.util.function.Consumer<Boolean> done){
    ChatSession s=a.session;
    java.util.function.BooleanSupplier live=()->s!=null&&a.session==s&&!s.deleted&&!a.isDestroyed()&&!a.isFinishing()&&current.getAsBoolean();
    if(!live.getAsBoolean()){a.status("环境已变化，请重新打开环境编辑");done.accept(false);return;}
    boolean preserveBrowser=BrowserEditIntent.preserveFailedCandidate(s.identity!=null&&s.identity.queueUnavailable,value);boolean browserChange=BrowserEditIntent.browserIntent(s.identity!=null&&s.identity.queueUnavailable,value,!preserveBrowser&&(value.optInt("privacyLevel",s.privacy.level())!=s.privacy.level()||value.optBoolean("desktopSite",s.privacy.wantsDesktop())!=s.privacy.wantsDesktop()),s.identityApplicationPending);
    if(value.optString("name").trim().isEmpty()||value.optString("name").trim().length()>24||!browserChange||!MainActivity.chatUrl(s.web.getUrl())||ProfileUi.working(s)){done.accept(guardedApply(a,value,name,live));return;}
    final String url=s.web.getUrl(),scope=s.pageMemory.scope();final long epoch=s.navigationEpoch;
    s.operation=true;s.configurationCapture=true;s.changed();a.status("正在保留网页草稿…");
    java.util.function.Consumer<String> fail=message->{DeferredBrowserSettings.release(s);s.changed();a.status(message);done.accept(false);};
    // Inspect uses the existing read-only driver and detects oversized drafts before
    // page-state's bounded snapshot could omit them.
    s.asyncDriver("inspect",J.obj("expectedUrl",url),2500,inspected->{
      if(!live.getAsBoolean()||!WebReplyObserver.same(url,inspected.optString("url"))||epoch!=s.navigationEpoch||!scope.equals(s.pageMemory.scope())){
        fail.accept("网页状态已改变，请稍后重试；环境设置尚未应用");return;
      }
      s.state=inspected;s.stateEpoch=epoch;if(inspected.optBoolean("busy")){DeferredBrowserSettings.release(s);done.accept(guardedApply(a,value,name,live));return;}
      if(inspected.optString("draft").length()>300000||inspected.optString("draftRaw").length()>300000){fail.accept("网页草稿过长，请先保存或发送，再切换显示方式");return;}
      s.asyncDriver("page-state",J.obj("expectedUrl",url),2500,state->{
        if(!live.getAsBoolean()||!PageMemory.completeDraft(state)||epoch!=s.navigationEpoch||!WebReplyObserver.same(url,s.web.getUrl())||!scope.equals(s.pageMemory.scope())||!state.optString("draft").equals(inspected.optString("draft"))){
          fail.accept("网页草稿暂时无法保留，请稍后重试；环境设置尚未应用");return;
        }
        if(PageMemory.hasDraft(state)&&(!LocalDraftPolicy.enabled(s.context)||value.opt("saveDraft") instanceof Boolean&&!value.optBoolean("saveDraft"))){fail.accept("本机草稿保存已关闭或将关闭，请先手动保留并发送或清空输入，再切换网页显示");return;}
        long draftRevision=LocalDraftPolicy.revision(s.context);s.pageMemory.remember(scope,url,state);String draft=state.optString("draft");
        try{s.webStore.worker.execute(()->{
          boolean saved=archiveEditorDraft(s,url,draft,draftRevision);
          s.handler.post(()->{
            DeferredBrowserSettings.release(s);s.changed();if(a.isDestroyed()||a.isFinishing()){done.accept(false);return;}
            if(!live.getAsBoolean()||!saved||PageMemory.hasDraft(state)&&(!LocalDraftPolicy.enabled(s.context)||draftRevision!=LocalDraftPolicy.revision(s.context))||epoch!=s.navigationEpoch||!WebReplyObserver.same(url,s.web.getUrl())||!scope.equals(s.pageMemory.scope())){a.status("草稿保留未完成或网页已改变，环境设置尚未应用");done.accept(false);return;}
            done.accept(guardedApply(a,value,name,live));
          });
        });}catch(RuntimeException ignored){fail.accept("草稿暂时无法保存，请稍后重试；环境设置尚未应用");}
      });
    });
  }
  static boolean archiveEditorDraft(ChatSession s,String url,String draft,long revision){
    if(draft.isEmpty())return true;
    try{
      EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(Profiles.slot(s.context),s.environmentGeneration,s.environmentId);
      // Match the manual draft copy's catalog-before-archive lock order.
      return ProfileCatalog.get(s.context).withIdentity(identity,()->!s.deleted
          &&DraftArchive.get(s.context).save(url,draft,"切换网页显示前的草稿",revision));
    }catch(Exception unavailable){return false;}
  }
  static boolean storageCurrent(MainActivity a,ChatSession session){
    if(session==null||a.isDestroyed()||a.isFinishing()||a.session!=session||a.remote!=session.web||session.deleted)return false;
    try{JSONObject environment=ProfileCatalog.get(a).item(Profiles.slot(a));
      return environment.optBoolean("created")&&!environment.optBoolean("deleting")&&!environment.optBoolean("resetting")&&environment.optInt("generation")==session.environmentGeneration&&session.environmentId.equals(environment.optString("environmentId"));
    }catch(RuntimeException unavailable){return false;}
  }
  static void storage(MainActivity a){
    ChatSession session=a.session;
    ProfileCatalog catalog=ProfileCatalog.get(a);EnvironmentSpec.Identity identity;
    try{identity=catalog.identity(Profiles.slot(a));}
    catch(java.io.IOException unavailable){return;}
    if(a.isDestroyed()||a.isFinishing()||session!=null&&!storageCurrent(a,session))return;
    JSONObject scan=AppPrefs.temporaryCache(a,System.currentTimeMillis(),false);
    java.util.concurrent.atomic.AtomicBoolean visible=new java.util.concurrent.atomic.AtomicBoolean(true);
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(a,"数据与存储 · "+Profiles.display(a,Profiles.slot(a)));
    LinearLayout summary=ReferenceUi.modalGroup(a);
    ReferenceUi.modalFieldRow(summary,"下载位置",DefaultDownloads.description(a),true);
    ReferenceUi.modalFieldRow(summary,"可清理旧临时文件",scan.optInt("count")+" 个 / "+NetworkMetricsUi.amount(scan.optLong("bytes")),false);
    ReferenceUi.modalFieldRow(summary,"任务引用中间文件",scan.optInt("protected")+" 个",false);
    final TextView[] attachmentValue={null};
    if(session!=null){
      LinearLayout attachRow=ReferenceUi.modalFieldRow(summary,"附件缓存","等待当前文件准备结束后统计（仅统计，不删除已交付或引用未确认副本）",false);
      attachmentValue[0]=(TextView)attachRow.getChildAt(1);
    }
    dialog.body.addView(summary,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalFooterNote(dialog.body,"清理按钮仅处理超过 30 天且未被任务引用的下载中间文件。聊天、草稿、登录与已保存文件保留。");
    dialog.buttons("关闭",dialog::dismiss,"清理旧临时文件",()->{
      dialog.dismiss();
      if(a.isDestroyed()||a.isFinishing()||a.session!=session||session!=null&&!storageCurrent(a,session))return;
      try{
        JSONObject result=catalog.withIdentity(identity,()->AppPrefs.temporaryCache(a,System.currentTimeMillis(),true));
        a.status("已清理 "+result.optInt("removed")+" 个旧临时文件");
      }catch(Exception changed){ReferenceUi.message(a,"数据与存储","环境已变化或暂时无法清理，请重新打开后重试。");}
    });
    dialog.setOnDismissListener(d->visible.set(false));dialog.show();
    if(session==null)return;
    java.lang.ref.WeakReference<MainActivity> host=new java.lang.ref.WeakReference<>(a);java.lang.ref.WeakReference<ReferenceUi.Modal> window=new java.lang.ref.WeakReference<>(dialog);android.os.Handler main=a.handler;
    try{session.web.uploadWorker.execute(()->{
      if(!visible.get())return;GeckoUploadFiles.Usage usage=GeckoUploadFiles.usage(session.context);GeckoUploadFiles.Cleanup cleanup=session.web.lastUploadCleanup;
      main.post(()->{
        MainActivity owner=host.get();ReferenceUi.Modal shown=window.get();if(owner==null||shown==null||!visible.get()||!shown.isShowing())return;
        if(!storageCurrent(owner,session)){shown.dismiss();return;}
        String text=(usage.complete?"":"至少 ")+usage.files+" 个文件 / "+NetworkMetricsUi.amount(usage.bytes)+(usage.complete?"":"（统计不完整）")+"\n已交付或引用未确认的副本继续保留；文件准备期间占用可能变化。";
        if(cleanup!=null)text+="\n最近未交付副本清理："+cleanup.removedFiles+" 个文件 / "+NetworkMetricsUi.amount(cleanup.removedBytes)+(cleanup.complete()?"；已清理或未生成副本":"；仍有 "+cleanup.failedEntries+" 项未能清理");
        if(attachmentValue[0]!=null){attachmentValue[0].setText(text);shown.resize();}
      });
    });}catch(java.util.concurrent.RejectedExecutionException closed){if(visible.get()&&dialog.isShowing()&&attachmentValue[0]!=null){attachmentValue[0].setText("附件缓存统计暂不可用，现有副本已保留。");dialog.resize();}}
  }
  static final class FrameLayoutHost extends android.widget.FrameLayout {
    final LinearLayout[] pages;FrameLayoutHost(MainActivity a,LinearLayout... views){super(a);pages=views;for(LinearLayout v:views)addView(v);}
    void page(int n){for(int i=0;i<pages.length;i++)pages[i].setVisibility(i==n?android.view.View.VISIBLE:android.view.View.GONE);}
  }
}
