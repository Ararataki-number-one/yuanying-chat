package local.pocketchat;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Build;
import android.text.Editable;
import android.text.InputFilter;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import org.json.JSONObject;

/** Native draft and preview; GitHub owns authentication and the final submission. */
final class FeedbackUi {
  static final String DRAFT="feedbackDraftV1";

  private static int tone(int light,int dark){return AppAppearance.dark()?dark:light;}
  private static int appleBlue(){return ReferenceUi.brandBlue();}
  private static int appleGreenText(){return ReferenceUi.greenInk();}
  private static int appleRedText(){return ReferenceUi.redInk();}
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

  private static void styleAppleSheet(Activity a,ReferenceUi.Modal modal,boolean showClose){
    modal.root.setBackground(new ReferenceUi.CardSurfaceDrawable(a,24f,0xfff2f3f6,0xff121318));
    modal.root.setClipChildren(false);
    modal.head.setClipChildren(false);modal.head.setClipToPadding(false);
    if(!showClose)modal.hideClose();
  }
  private static void styleAppleSheet(Activity a,ReferenceUi.Modal modal){styleAppleSheet(a,modal,true);}
  private static LinearLayout sheetCard(Context c){
    LinearLayout card=DesignUi.column(c);
    card.setElevation(0f);
    card.setBackground(new ReferenceUi.CardSurfaceDrawable(c,20f));
    card.setClipToOutline(true);
    return card;
  }
  private static void styleAppleSwitch(Switch option){ReferenceUi.styleSwitch(option);}

  static void open(Activity activity){
    JSONObject saved=J.parse(AppSettings.get(activity,DRAFT,"{}"));
    ReferenceUi.Modal form=new ReferenceUi.Modal(activity,"问题与建议");
    styleAppleSheet(activity,form);
    boolean[] suggestion={saved.optBoolean("suggestion")};

    LinearLayout typeSwitch=DesignUi.row(activity);
    typeSwitch.setBackground(new ReferenceUi.SegmentedTrackDrawable(activity));
    int inset=DesignUi.dp(activity,3);
    typeSwitch.setPadding(inset,inset,inset,inset);
    String[] kindLabels={"遇到问题","改进建议"};
    Button[] kindButtons=new Button[kindLabels.length];
    Runnable[] syncKinds={null};
    syncKinds[0]=()->{
      for(int i=0;i<kindButtons.length;i++){
        boolean active=(i==1)==suggestion[0];
        Button option=kindButtons[i];
        option.setSelected(active);
        option.setTextColor(active?ReferenceUi.inkPrimary():appleSecondary());
        option.setTypeface(active?ReferenceUi.TYPE_SEMIBOLD:ReferenceUi.TYPE_MEDIUM);
        option.setLetterSpacing(0.005f);ReferenceUi.crisp(option);
        if(active){
          option.setBackground(new ReferenceUi.SegmentedThumbDrawable(activity));
          option.setElevation(0f);
        }else{
          option.setBackground(Ui.ripple(activity,Color.TRANSPARENT,10));
          option.setElevation(0f);
        }
      }
    };
    for(int i=0;i<kindLabels.length;i++){
      final boolean isSuggestion=i==1;
      Button option=ReferenceUi.link(activity,kindLabels[i],()->{
        ReferenceUi.hapticTick(typeSwitch);
        suggestion[0]=isSuggestion;
        syncKinds[0].run();
      });
      option.setTextSize(ReferenceUi.BODY_SIZE);
      option.setMinHeight(DesignUi.dp(activity,36));
      option.setMinimumHeight(DesignUi.dp(activity,36));
      option.setPadding(DesignUi.dp(activity,8),DesignUi.dp(activity,6),
          DesignUi.dp(activity,8),DesignUi.dp(activity,6));
      ReferenceUi.readable(option);
      LinearLayout.LayoutParams slot=new LinearLayout.LayoutParams(0,-2,1);
      if(i>0)slot.setMarginStart(DesignUi.dp(activity,2));
      typeSwitch.addView(option,slot);
      kindButtons[i]=option;
    }
    syncKinds[0].run();
    LinearLayout.LayoutParams segLayout=new LinearLayout.LayoutParams(-1,-2);
    segLayout.topMargin=DesignUi.dp(activity,2);
    segLayout.bottomMargin=DesignUi.dp(activity,12);
    form.body.addView(typeSwitch,segLayout);

    LinearLayout fieldsCard=sheetCard(activity);
    fieldsCard.setPadding(DesignUi.dp(activity,14),DesignUi.dp(activity,14),
        DesignUi.dp(activity,14),DesignUi.dp(activity,14));
    EditText title=countedInput(fieldsCard,"一句话说明",saved.optString("title"),
        "例如：选择图片后没有出现附件",FeedbackReport.TITLE_LIMIT);
    EditText details=countedInput(fieldsCard,"详细说明",saved.optString("details"),
        "做了什么、实际发生什么、希望怎样改善？",FeedbackReport.DETAIL_LIMIT);
    details.setSingleLine(false);
    details.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE
        |InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
    details.setMinLines(3);
    details.setMaxLines(7);
    details.setGravity(Gravity.TOP|Gravity.START);
    ReferenceUi.readable(details);
    form.body.addView(fieldsCard,new LinearLayout.LayoutParams(-1,-2));

    TextView attachmentHint=ReferenceUi.workspaceText(activity,
        "将附带应用版本；请勿填写密码、订阅链接等私密信息。",
        ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
    ReferenceUi.balancedBreaks(attachmentHint);
    attachmentHint.setPadding(DesignUi.dp(activity,14),DesignUi.dp(activity,7),
        DesignUi.dp(activity,14),DesignUi.dp(activity,10));
    form.body.addView(attachmentHint);

    LinearLayout optionsCard=sheetCard(activity);
    optionsCard.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,4),
        DesignUi.dp(activity,16),DesignUi.dp(activity,4));
    Switch system=new Switch(activity);
    system.setText("附带手机型号和 Android 版本");
    NativeControls.prepare(system);
    system.setTextSize(ReferenceUi.BODY_SIZE);
    system.setTextColor(ReferenceUi.TEXT);
    system.setPadding(0,DesignUi.dp(activity,8),0,DesignUi.dp(activity,8));
    ReferenceUi.readable(system);
    system.setChecked(saved.optBoolean("system",true));
    styleAppleSwitch(system);
    optionsCard.addView(system,new LinearLayout.LayoutParams(-1,-2));

    TextView error=notice(activity);
    Runnable save=()->AppSettings.put(activity,DRAFT,J.obj(
        "suggestion",suggestion[0],
        "title",title.getText().toString(),
        "details",details.getText().toString(),
        "system",system.isChecked()).toString());
    form.setOnDismissListener(ignored->save.run());

    divider(optionsCard,0,0);
    Button progress=ReferenceUi.link(activity,"查看反馈与处理进度",()->{
      save.run();
      if(!openUrl(activity,FeedbackReport.ISSUES,error))showNotice(form,error,error.getText(),true);
    });
    progress.setTextSize(ReferenceUi.BODY_SIZE);
    progress.setTextColor(appleBlue());
    progress.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));
    progress.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
    progress.setMinHeight(DesignUi.dp(activity,48));
    progress.setMinimumHeight(DesignUi.dp(activity,48));
    progress.setPadding(0,DesignUi.dp(activity,11),0,DesignUi.dp(activity,11));
    Ui.Icon progressArrow=new Ui.Icon("chevron-right",appleChevron());
    int arrowSize=DesignUi.dp(activity,14);
    progressArrow.setBounds(0,0,arrowSize,arrowSize);
    progress.setCompoundDrawables(null,null,progressArrow,null);
    progress.setCompoundDrawablePadding(DesignUi.dp(activity,6));
    ReferenceUi.readable(progress);
    optionsCard.addView(progress,new LinearLayout.LayoutParams(-1,-2));
    form.body.addView(optionsCard,new LinearLayout.LayoutParams(-1,-2));

    Button clear=ReferenceUi.link(activity,"清空草稿",()->{
      if(title.length()==0&&details.length()==0)return;
      ReferenceUi.Modal confirm=new ReferenceUi.Modal(activity,"清空反馈草稿？").hideClose();
      styleAppleSheet(activity,confirm,false);
      confirm.body.addView(ReferenceUi.modalImpactPair(activity,
          "将清空尚未提交的标题与说明","当前填写的标题和详细说明将被清除，无法恢复。",
          "以下设置会保留","反馈类型和设备信息开关不会被重置。"),new LinearLayout.LayoutParams(-1,-2));
      confirm.buttons("保留",confirm::dismiss,"清空",()->{
        title.setText("");
        details.setText("");
        save.run();
        confirm.dismiss();
      });
      confirm.show();
    });
    clear.setTextSize(ReferenceUi.ACTION_SIZE);
    clear.setTextColor(appleRedText());
    clear.setGravity(Gravity.CENTER);
    clear.setMinHeight(DesignUi.dp(activity,48));
    clear.setMinimumHeight(DesignUi.dp(activity,48));
    clear.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,8),DesignUi.dp(activity,16),DesignUi.dp(activity,8));
    ReferenceUi.readable(clear);
    Runnable syncClear=()->clear.setEnabled(title.length()>0||details.length()>0);
    syncClear.run();
    TextWatcher clearWatcher=new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence s,int start,int before,int count){}
      @Override public void afterTextChanged(Editable s){syncClear.run();}
    };
    title.addTextChangedListener(clearWatcher);
    details.addTextChangedListener(clearWatcher);
    LinearLayout.LayoutParams dangerLayout=new LinearLayout.LayoutParams(-2,-2);
    dangerLayout.gravity=Gravity.CENTER_HORIZONTAL;
    dangerLayout.topMargin=DesignUi.dp(activity,10);
    dangerLayout.bottomMargin=DesignUi.dp(activity,8);
    form.body.addView(clear,dangerLayout);
    form.body.addView(error,new LinearLayout.LayoutParams(-1,-2));

    actions(form,"保存草稿",()->{save.run();form.dismiss();},"预览反馈",true,()->{
      save.run();
      FeedbackReport report=new FeedbackReport(suggestion[0],
          title.getText().toString(),details.getText().toString(),AppVersion.name(activity),
          system.isChecked()?Build.MANUFACTURER+" "+Build.MODEL+" / Android "+Build.VERSION.RELEASE:"");
      String problem=report.error();
      showNotice(form,error,problem,true);
      if(!problem.isEmpty()){
        // Make validation feedback visible even after the form has started scrolling.
        error.post(()->error.requestRectangleOnScreen(new android.graphics.Rect(
            0,0,error.getWidth(),error.getHeight()),true));
        return;
      }
      preview(activity,report,form);
    });
    form.show();
    styleAppleSwitch(system);
  }

  static void preview(Activity activity,FeedbackReport report){
    preview(activity,report,null);
  }

  private static void preview(Activity activity,FeedbackReport report,ReferenceUi.Modal form){
    ReferenceUi.Modal preview=new ReferenceUi.Modal(activity,"预览公开反馈");
    styleAppleSheet(activity,preview);
    LinearLayout payload=sheetCard(activity);
    payload.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,14),
        DesignUi.dp(activity,16),DesignUi.dp(activity,14));
    TextView heading=ReferenceUi.workspaceText(activity,report.issueTitle(),15,DesignUi.TEXT,true);
    heading.setTextIsSelectable(true);
    if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);
    payload.addView(heading);
    divider(payload,10,0);
    addPreviewBody(activity,payload,report.body());
    preview.body.addView(payload,new LinearLayout.LayoutParams(-1,-2));

    String url=report.url();
    if(url==null){
      LinearLayout longHint=ReferenceUi.modalBanner(activity,"info","内容较长，建议复制后粘贴提交","在 GitHub 提交页粘贴已复制的正文，可添加截图后提交。草稿仍保存在本机。",true);
      LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.topMargin=DesignUi.dp(activity,10);
      preview.body.addView(longHint,lp);
    }
    TextView status=notice(activity);
    Button copyAction=ReferenceUi.link(activity,"复制反馈内容",()->{
      ReferenceUi.hapticConfirm(preview.root);
      copy(activity,report.body());
      showNotice(preview,status,"已复制，可粘贴到 GitHub 正文。",false);
    });
    copyAction.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14f);
    int copyInk=appleBlue();
    copyAction.setTextColor(copyInk);
    copyAction.setTypeface(ReferenceUi.TYPE_SEMIBOLD);copyAction.setLetterSpacing(0.010f);ReferenceUi.crisp(copyAction);
    copyAction.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
    copyAction.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,10),DesignUi.dp(activity,16),DesignUi.dp(activity,6));
    Ui.Icon clipboard=new Ui.Icon("clipboard",copyInk);
    int iconSize=DesignUi.dp(activity,16);
    clipboard.setBounds(0,0,iconSize,iconSize);
    copyAction.setCompoundDrawables(clipboard,null,null,null);
    copyAction.setCompoundDrawablePadding(DesignUi.dp(activity,6));
    LinearLayout.LayoutParams copyLayout=new LinearLayout.LayoutParams(-2,-2);
    copyLayout.topMargin=DesignUi.dp(activity,4);
    preview.body.addView(copyAction,copyLayout);
    status.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,2),DesignUi.dp(activity,16),0);
    preview.body.addView(status,new LinearLayout.LayoutParams(-1,-2));

    preview.footer.setOrientation(LinearLayout.VERTICAL);
    TextView scope=label(activity,"公开范围");
    scope.setPadding(DesignUi.dp(activity,16),0,DesignUi.dp(activity,16),0);
    preview.footer.addView(scope);
    TextView disclosure=ReferenceUi.workspaceText(activity,
        "在 GitHub 提交后，标题、正文和附带的应用信息将公开。提交需登录。",
        ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
    disclosure.setPadding(DesignUi.dp(activity,16),DesignUi.dp(activity,3),DesignUi.dp(activity,16),DesignUi.dp(activity,12));
    preview.footer.addView(disclosure);
    actions(preview,"返回修改",preview::dismiss,url==null?"复制并打开提交页":"打开 GitHub 提交",true,()->{
      if(url==null)copy(activity,report.body());
      if(openUrl(activity,url==null?report.baseUrl():url,status)){
        showNotice(preview,status,"已打开提交页。提交后可在反馈列表查看。草稿已保留。",false);
      }else{
        showNotice(preview,status,status.getText(),true);
      }
    });
    if(form!=null){
      preview.setOnDismissListener(ignored->{
        if(!activity.isFinishing()&&!activity.isDestroyed())form.show();
      });
      form.hide();
    }
    preview.show();
  }

  private static EditText countedInput(LinearLayout box,String title,String value,String hint,int limit){
    Context context=box.getContext();
    boolean first=box.getChildCount()==0;
    EditText input=DesignUi.input(box,title,value,hint);
    input.setBackground(new ReferenceUi.FieldWell(context));
    input.setPadding(DesignUi.dp(context,13),DesignUi.dp(context,10),DesignUi.dp(context,13),DesignUi.dp(context,10));
    input.setMinHeight(DesignUi.dp(context,44));
    input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(limit)});
    int labelIndex=box.indexOfChild(input)-1;
    TextView label=(TextView)box.getChildAt(labelIndex);
    label.setPadding(0,0,0,0);
    label.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,13f);
    label.setTextColor(appleSecondary());
    label.setTypeface(ReferenceUi.TYPE_SEMIBOLD);label.setLetterSpacing(0.015f);
    ReferenceUi.crisp(label);
    if(input.getId()==View.NO_ID)input.setId(View.generateViewId());
    label.setLabelFor(input.getId());
    TextView count=ReferenceUi.mono(ReferenceUi.crisp(ReferenceUi.workspaceText(context,"",ReferenceUi.SECONDARY_SIZE,appleSecondary(),false)));
    count.setFontFeatureSettings("tnum");
    count.setPaddingRelative(DesignUi.dp(context,8),0,0,0);
    count.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout heading=DesignUi.row(context);
    heading.setBaselineAligned(true);
    heading.setPadding(DesignUi.dp(context,2),first?0:DesignUi.dp(context,14),DesignUi.dp(context,2),DesignUi.dp(context,6));
    box.removeViewAt(labelIndex);
    heading.addView(label,new LinearLayout.LayoutParams(0,-2,1));
    heading.addView(count,new LinearLayout.LayoutParams(-2,-2));
    box.addView(heading,labelIndex,new LinearLayout.LayoutParams(-1,-2));
    count.setText(context.getString(R.string.secondary_character_count,input.length(),limit));
    input.addTextChangedListener(new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence s,int start,int before,int count){}
      @Override public void afterTextChanged(Editable s){count.setText(context.getString(R.string.secondary_character_count,s.length(),limit));}
    });
    return input;
  }

  private static Button grayAction(Activity activity,String label,Runnable run){
    Button button=DesignUi.button(activity,label,false,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    ReferenceUi.stylePill(button,false,false);
    return button;
  }

  private static Button solidPrimary(Activity activity,String label,Runnable run){
    Button button=DesignUi.button(activity,label,true,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    ReferenceUi.stylePill(button,true,false);
    return button;
  }

  private static Button softPrimary(Activity activity,String label,Runnable run){
    Button button=DesignUi.button(activity,label,false,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14.5f);
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.015f);ReferenceUi.crisp(button);
    button.setTextColor(appleBlue());
    Drawable face=new AppleSurface(activity,12,0xffeef4ff,0xff1b2638,0x200067d8,0x336da4ff);
    button.setBackground(new AppAppearance.GlassRipple(face,
        DesignUi.surface(activity,Color.WHITE,12,Color.TRANSPARENT)));
    return button;
  }

  private static void actions(ReferenceUi.Modal panel,String secondary,Runnable back,
      String primary,boolean solid,Runnable proceed){
    Activity activity=panel.a;
    panel.footer.setOrientation(LinearLayout.VERTICAL);
    LinearLayout buttons=DesignUi.row(activity);
    Button previous=grayAction(activity,secondary,back);
    Button next=solid?solidPrimary(activity,primary,proceed):softPrimary(activity,primary,proceed);
    ReferenceUi.styleDualButton(previous);
    ReferenceUi.styleDualButton(next);
    buttons.addView(previous,new LinearLayout.LayoutParams(0,-2,1));
    LinearLayout.LayoutParams nextLayout=new LinearLayout.LayoutParams(0,-2,1.5f);
    nextLayout.setMarginStart(DesignUi.dp(activity,10));
    buttons.addView(next,nextLayout);
    panel.footer.addView(buttons,new LinearLayout.LayoutParams(-1,-2));
  }

  private static void divider(LinearLayout parent,int top,int bottom){
    Context context=parent.getContext();
    View line=new View(context);
    line.setBackground(new AppleSurface(context,0,0x14111827,0x18ffffff));
    line.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams spacing=new LinearLayout.LayoutParams(-1,
        Math.max(1,Math.round(ReferenceUi.dpF(context,0.5f))));
    spacing.topMargin=DesignUi.dp(context,top);
    spacing.bottomMargin=DesignUi.dp(context,bottom);
    parent.addView(line,spacing);
  }

  private static void addPreviewBody(Activity activity,LinearLayout issue,String markdown){
    StringBuilder paragraph=new StringBuilder();
    boolean codeBlock=false;
    for(String line:markdown.split("\n",-1)){
      String marker=line.trim();
      boolean heading=!codeBlock&&line.startsWith("## ");
      boolean separator=!codeBlock&&marker.equals("---");
      if(heading||separator){
        addPreviewParagraph(activity,issue,paragraph);
        if(heading){
          TextView section=ReferenceUi.workspaceText(activity,line.substring(3).trim(),
              ReferenceUi.ACTION_SIZE,DesignUi.MUTED,true);
          section.setPadding(0,DesignUi.dp(activity,10),0,0);
          if(Build.VERSION.SDK_INT>=28)section.setAccessibilityHeading(true);
          issue.addView(section);
        }else{
          divider(issue,10,4);
        }
        continue;
      }
      if(marker.startsWith("```")||marker.startsWith("~~~"))codeBlock=!codeBlock;
      if(paragraph.length()>0||!marker.isEmpty())paragraph.append(line).append('\n');
    }
    addPreviewParagraph(activity,issue,paragraph);
  }

  private static void addPreviewParagraph(Activity activity,LinearLayout issue,StringBuilder paragraph){
    int end=paragraph.length();
    while(end>0&&paragraph.charAt(end-1)=='\n')end--;
    if(end>0){
      TextView body=ReferenceUi.workspaceText(activity,paragraph.substring(0,end),
          ReferenceUi.BODY_SIZE,DesignUi.TEXT,false);
      body.setPadding(0,DesignUi.dp(activity,4),0,0);
      body.setTextIsSelectable(true);
      body.setHorizontallyScrolling(false);
      issue.addView(body);
    }
    paragraph.setLength(0);
  }

  private static TextView label(Activity activity,String text){
    TextView label=ReferenceUi.workspaceText(activity,text,ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,true);
    if(Build.VERSION.SDK_INT>=28)label.setAccessibilityHeading(true);
    return label;
  }

  private static TextView notice(Activity activity){
    TextView result=ReferenceUi.workspaceText(activity,"",ReferenceUi.ACTION_SIZE,DesignUi.TEXT,false);
    result.setPadding(0,DesignUi.dp(activity,6),0,0);
    result.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    result.setVisibility(View.GONE);
    return result;
  }

  private static void showNotice(ReferenceUi.Modal modal,TextView view,CharSequence text,boolean failed){
    view.setTextColor(failed?appleRedText():appleGreenText());
    view.setText(text);
    view.setVisibility(text.length()==0?View.GONE:View.VISIBLE);
    modal.resize();
  }

  static void copy(Activity activity,String value){
    ClipboardManager clipboard=(ClipboardManager)activity.getSystemService(Context.CLIPBOARD_SERVICE);
    clipboard.setPrimaryClip(ClipData.newPlainText("反馈内容",value));
  }

  static boolean openUrl(Activity activity,String url,TextView error){
    try{
      activity.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE));
      return true;
    }catch(ActivityNotFoundException|SecurityException unavailable){
      error.setText("未找到可打开 GitHub 的浏览器。可先复制反馈，稍后在项目 Issues 中提交。");
      return false;
    }
  }
}
