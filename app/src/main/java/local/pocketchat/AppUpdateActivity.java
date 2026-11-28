package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.util.Locale;

/** Small app-wide page; no browser session is created, stopped or reloaded here. */
public class AppUpdateActivity extends ThemedActivity {
  LinearLayout box;ProgressBar downloadProgress,unknownSpinner;TextView downloadDetails,downloadPercent;final Handler handler=new Handler(Looper.getMainLooper());String rendered="",installMessage="";long pendingInstall;boolean permissionPending;int originSlot=-1;
  ReleaseHistory history;LinearLayout historyBody;long historyClient,historyRevision=-1;boolean historyExpanded,technicalExpanded;int historyVisible=10;String expandedHistory="",expandedTechnical="";
  final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1000);}};
  @Override public void onCreate(Bundle state){super.onCreate(state);originSlot=getIntent().getIntExtra("originSlot",-1);if(state!=null){originSlot=state.getInt("originSlot",originSlot);pendingInstall=state.getLong("install");installMessage=state.getString("installMessage","");permissionPending=state.getBoolean("permission");historyExpanded=state.getBoolean("historyExpanded");technicalExpanded=state.getBoolean("technicalExpanded");historyVisible=Math.max(10,Math.min(100,state.getInt("historyVisible",10)));expandedHistory=state.getString("expandedHistory","");expandedTechnical=state.getString("expandedTechnical","");}if(!AppUpdates.validSlot(originSlot))originSlot=AppSettings.defaultSlot(this);history=ReleaseHistory.get(this);openPage();}
  @Override protected void onResume(){super.onResume();historyClient=history.attach(originSlot);if(historyExpanded)history.load(historyClient,historyVisible,false);handler.removeCallbacks(tick);handler.post(tick);AppUpdates.schedule(this);if(permissionPending){permissionPending=false;if(getPackageManager().canRequestPackageInstalls())install();else installIssue("尚未允许安装更新，可稍后再次点击安装");}}
  @Override protected void onPause(){handler.removeCallbacks(tick);history.detach(historyClient);historyClient=0;super.onPause();}
  @Override protected void onSaveInstanceState(Bundle state){state.putInt("originSlot",originSlot);state.putLong("install",pendingInstall);state.putString("installMessage",installMessage);state.putBoolean("permission",permissionPending);state.putBoolean("historyExpanded",historyExpanded);state.putBoolean("technicalExpanded",technicalExpanded);state.putInt("historyVisible",historyVisible);state.putString("expandedHistory",expandedHistory);state.putString("expandedTechnical",expandedTechnical);super.onSaveInstanceState(state);}
  void refresh(){Bundle status=AppUpdates.call(this,"status",null);String fingerprint="dark:"+AppAppearance.dark()+"\ninstallMessage:"+installMessage+"\n";for(String key:new String[]{"state","message","version","versionDisplay","bytes","checkedAt","autoCheck","autoDownload","wifiOnly","verifiedSerial","packageDeleteRetry","packageUri","latestVersion","latestDisplay","latestCheckedAt","latestRevision","channel","canChangeChannel"})fingerprint+=key+":"+String.valueOf(status.get(key))+"\n";String phase=status.getString("state","");if("available".equals(phase)||"error".equals(phase))fingerprint+="resume:"+status.getBoolean("canResume");if(!fingerprint.equals(rendered)){rendered=fingerprint;DesignUi.rebuild(box,true,()->render(status));}updateProgress(status);refreshHistory(status.getString("latestVersion",""));
    if(pendingInstall>0){String kind=status.getString("state","");if(status.containsKey("verifyRequestedSerial")&&status.getLong("verifyRequestedSerial")!=pendingInstall){pendingInstall=0;}else if("ready".equals(kind)&&status.getLong("verifiedSerial")==pendingInstall){pendingInstall=0;install();}else if(!"ready".equals(kind)&&!"verifying".equals(kind)){pendingInstall=0;}}
  }
  void action(String name){installMessage="";Bundle extras=new Bundle();if(AppUpdates.validSlot(originSlot))extras.putInt("originSlot",originSlot);AppUpdates.call(this,name,extras);rendered="";refresh();}

  private void openPage(){
    LinearLayout root=DesignUi.screen(this);
    root.setClipChildren(false);root.setClipToPadding(false);
    root.setBackgroundColor(ReferenceUi.canvasBg());
    ScrollView scroll=new ScrollView(this);
    scroll.setFillViewport(true);
    NativeControls.prepare(scroll);
    box=DesignUi.column(this);
    box.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,6),DesignUi.dp(this,16),DesignUi.dp(this,24));
    scroll.addView(box,new ScrollView.LayoutParams(-1,-2));
    FrameLayout header=ReferenceUi.horologyHeader(this,"应用更新","版本状态、下载进度与通道设置",this::finish,scroll);
    root.addView(header,new LinearLayout.LayoutParams(-1,-2));
    FrameLayout viewport=new FrameLayout(this);
    viewport.setClipChildren(true);viewport.setClipToPadding(true);
    viewport.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
    root.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));
    setContentView(root);
  }

  private static int tone(int light,int dark){return AppAppearance.dark()?dark:light;}
  private static int appleBlue(){return ReferenceUi.brandBlue();}
  private static int appleGreenText(){return ReferenceUi.greenInk();}
  private static int appleRedText(){return ReferenceUi.redInk();}
  private static int appleSecondary(){return ReferenceUi.secondaryInk();}
  private static int appleChevron(){return ReferenceUi.chevronInk();}
  private static int appleSeparator(){return tone(0x14111827,0x18ffffff);}

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
    @Override protected void onBoundsChange(Rect b){face.set(b);edge.set(face);edge.inset(.25f*density,.25f*density);}
    @Override public void draw(Canvas canvas){
      if(face.isEmpty())return;
      boolean dark=AppAppearance.dark();
      float r=Math.min(radiusDp*density,Math.min(face.width(),face.height())*.5f);
      paint.setStyle(Paint.Style.FILL);paint.setColor(dark?darkFill:lightFill);
      canvas.drawRoundRect(face,r,r,paint);
      int rim=dark?darkRim:lightRim;
      if(rim!=0){
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(.5f*density);paint.setColor(rim);
        canvas.drawRoundRect(edge,Math.max(0f,r-.25f*density),Math.max(0f,r-.25f*density),paint);
      }
    }
    @Override public void setAlpha(int a){paint.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){paint.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  private static final class AlertIcon extends Drawable {
    private final Paint stroke=new Paint(Paint.ANTI_ALIAS_FLAG),fill=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int color;
    AlertIcon(int color){
      this.color=color;
      stroke.setStyle(Paint.Style.STROKE);stroke.setStrokeCap(Paint.Cap.ROUND);stroke.setStrokeJoin(Paint.Join.ROUND);
      fill.setStyle(Paint.Style.FILL);
    }
    @Override public void draw(Canvas canvas){
      Rect b=getBounds();if(b.isEmpty())return;
      canvas.save();canvas.translate(b.left,b.top);canvas.scale(b.width()/24f,b.height()/24f);
      stroke.setColor(color);stroke.setStrokeWidth(1.85f);fill.setColor(color);
      canvas.drawCircle(12f,12f,9f,stroke);
      canvas.drawLine(12f,7.4f,12f,13.2f,stroke);
      canvas.drawCircle(12f,16.5f,1.05f,fill);
      canvas.restore();
    }
    @Override public void setAlpha(int a){stroke.setAlpha(a);fill.setAlpha(a);invalidateSelf();}
    @Override public void setColorFilter(ColorFilter f){stroke.setColorFilter(f);fill.setColorFilter(f);invalidateSelf();}
    @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }

  private static final class UpChevronIcon extends Drawable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path=new Path();
    private final int color;
    UpChevronIcon(int color){
      this.color=color;
      paint.setStyle(Paint.Style.STROKE);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
      path.moveTo(7f,14.5f);path.lineTo(12f,9.5f);path.lineTo(17f,14.5f);
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

  private void appleSection(LinearLayout parent,String title){
    TextView h=new TextView(this);h.setText(title);h.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,12f);
    h.setTypeface(ReferenceUi.TYPE_SEMIBOLD);h.setLetterSpacing(0.045f);h.setTextColor(tone(0xff4e535e,0xff949ba8));ReferenceUi.crisp(h);
    h.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,parent.getChildCount()==0?6:20),DesignUi.dp(this,16),DesignUi.dp(this,6));
    if(Build.VERSION.SDK_INT>=28)h.setAccessibilityHeading(true);
    parent.addView(h,new LinearLayout.LayoutParams(-1,-2));
  }

  private void appleDivider(LinearLayout parent,int topDp,int startDp){
    View rule=new View(this);
    rule.setBackgroundColor(appleSeparator());
    rule.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,Math.max(1,Math.round(ReferenceUi.dpF(this,0.5f))));
    if(topDp>0)lp.topMargin=DesignUi.dp(this,topDp);
    if(startDp>0){lp.setMarginStart(DesignUi.dp(this,startDp));lp.setMarginEnd(DesignUi.dp(this,16));}
    parent.addView(rule,lp);
  }

  private void appleFooterNote(LinearLayout parent,String text){
    TextView note=ReferenceUi.prose(DownloadWorkspaceStyle.text(this,text,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false));
    note.setTypeface(ReferenceUi.TYPE_REGULAR);
    note.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,8),DesignUi.dp(this,16),0);
    parent.addView(note,new LinearLayout.LayoutParams(-1,-2));
  }

  private LinearLayout updateCard(){
    LinearLayout card=DesignUi.card(this);
    card.setElevation(0f);
    card.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,16),DesignUi.dp(this,16),DesignUi.dp(this,14));
    card.setBackground(new ReferenceUi.CardSurfaceDrawable(this,20f));
    return card;
  }

  private void statusDetail(LinearLayout card,String text,boolean failed){
    TextView detail=ReferenceUi.prose(DownloadWorkspaceStyle.text(this,text,failed?ReferenceUi.ACTION_SIZE:ReferenceUi.BODY_SIZE,failed?appleRedText():ReferenceUi.inkPrimary(),false));
    detail.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    detail.setPadding(0,DesignUi.dp(this,8),0,0);
    card.addView(detail,new LinearLayout.LayoutParams(-1,-2));
  }

  private Button solidPrimary(String title,Runnable run){
    Button button=DesignUi.button(this,title,true,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    ReferenceUi.stylePill(button,true,false);
    return button;
  }

  private Button softPrimary(String title,Runnable run){
    Button button=DesignUi.button(this,title,false,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14.5f);
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.015f);ReferenceUi.crisp(button);
    button.setTextColor(appleBlue());
    Drawable face=new AppleSurface(this,12,0xffeef4ff,0xff1b2638,0x200067d8,0x336da4ff);
    button.setBackground(new AppAppearance.GlassRipple(face,
        DesignUi.surface(this,Color.WHITE,12,Color.TRANSPARENT)));
    return button;
  }

  private Button tactileSecondary(String title,Runnable run){
    return tactileSecondary(title,false,run);
  }

  private Button tactileSecondary(String title,boolean destructive,Runnable run){
    Button button=DesignUi.button(this,title,false,()->{});
    button.setOnClickListener(v->{ReferenceUi.hapticClick(v);run.run();});
    ReferenceUi.stylePill(button,false,destructive);
    return button;
  }

  private Button quietAction(String title,boolean destructive,Runnable run){
    Button button=ReferenceUi.link(this,title,()->{ReferenceUi.hapticClick(null);run.run();});
    ReferenceUi.crisp(button);
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14f);
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.010f);
    button.setTextColor(destructive?appleRedText():appleBlue());
    button.setPadding(DesignUi.dp(this,8),DesignUi.dp(this,8),DesignUi.dp(this,8),DesignUi.dp(this,8));
    return button;
  }

  private void disclosureAction(LinearLayout parent,String title,boolean expanded,Runnable run){
    Button button=ReferenceUi.link(this,title,()->{ReferenceUi.hapticTick(parent);run.run();});
    ReferenceUi.crisp(button);
    button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,14f);
    button.setTextColor(appleBlue());
    button.setTypeface(ReferenceUi.TYPE_SEMIBOLD);button.setLetterSpacing(0.010f);
    button.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
    button.setPadding(0,DesignUi.dp(this,10),0,DesignUi.dp(this,10));
    Drawable chevron=expanded?new UpChevronIcon(appleChevron()):new Ui.Icon("chevron-right",appleChevron());
    int iconSize=DesignUi.dp(this,16);
    chevron.setBounds(0,0,iconSize,iconSize);
    button.setCompoundDrawables(null,null,chevron,null);
    button.setCompoundDrawablePadding(DesignUi.dp(this,6));
    parent.addView(button,new LinearLayout.LayoutParams(-1,-2));
  }

  private void statusHeading(LinearLayout card,String status,String subtitle,String state,boolean failed,boolean complete){
    LinearLayout heading=DesignUi.row(this);
    heading.setGravity(Gravity.CENTER_VERTICAL);
    boolean active="available".equals(state)||"downloading".equals(state)||"waiting".equals(state)||"checking".equals(state)||"verifying".equals(state);
    int iconTone=failed?appleRedText():complete?appleGreenText():active?appleBlue():appleSecondary();
    Drawable badgeBg=failed
        ?new AppleSurface(this,14,0xfffff3f4,0xff241518,0x26dc2626,0x33ff7a82)
        :complete?new AppleSurface(this,14,0xfff1fbf5,0xff13221c,0x2415804e,0x3334d38b)
        :active?new AppleSurface(this,14,0xffeef4ff,0xff1b2638,0x200067d8,0x336da4ff)
        :new AppleSurface(this,14,0xfff4f5f8,0xff232732,0x12111827,0x1affffff);
    String glyph=complete?"check":"paused".equals(state)?"pause":"download";
    ImageView icon=DesignUi.icon(this,glyph,iconTone,44);
    if(failed)icon.setImageDrawable(new AlertIcon(iconTone));
    icon.setPadding(DesignUi.dp(this,10),DesignUi.dp(this,10),DesignUi.dp(this,10),DesignUi.dp(this,10));
    icon.setBackground(badgeBg);
    icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    heading.addView(icon);
    LinearLayout copy=DesignUi.column(this);
    copy.setPaddingRelative(DesignUi.dp(this,12),0,0,0);
    LinearLayout titleRow=DesignUi.row(this);
    titleRow.setGravity(Gravity.CENTER_VERTICAL);
    ImageView led=new ImageView(this);
    led.setImageDrawable(new ReferenceUi.HaloDotDrawable(this,iconTone));
    led.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams ledP=new LinearLayout.LayoutParams(DesignUi.dp(this,10),DesignUi.dp(this,10));
    ledP.setMarginEnd(DesignUi.dp(this,7));
    titleRow.addView(led,ledP);
    TextView label=ReferenceUi.heroTitle(this,status);
    label.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    titleRow.addView(label,new LinearLayout.LayoutParams(0,-2,1));
    copy.addView(titleRow);
    if(subtitle!=null&&!subtitle.isEmpty()){
      TextView meta=ReferenceUi.tabular(ReferenceUi.crisp(DownloadWorkspaceStyle.text(this,subtitle,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false)));
      meta.setPadding(0,DesignUi.dp(this,4),0,0);
      copy.addView(meta);
    }
    heading.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    card.addView(heading);
  }

  private void versionSummary(LinearLayout card,String installed,String latest,String packageVersion,String channelName,boolean installedNewer){
    LinearLayout strip=DesignUi.column(this);
    strip.setBackground(new ReferenceUi.RecessedBoxDrawable(this,14f));
    strip.setPadding(DesignUi.dp(this,12),DesignUi.dp(this,10),DesignUi.dp(this,12),DesignUi.dp(this,10));
    LinearLayout row=DesignUi.row(this);
    row.setGravity(Gravity.CENTER_VERTICAL);
    TextView current=ReferenceUi.mono(ReferenceUi.crisp(DownloadWorkspaceStyle.text(this,"当前安装版本 "+installed,ReferenceUi.ACTION_SIZE,appleSecondary(),false)));
    strip.addView(current,new LinearLayout.LayoutParams(-1,-2));
    String badgeLabel=channelName==null?"":channelName;
    if(latest.isEmpty()){
      TextView empty=DownloadWorkspaceStyle.text(this,"尚未取得新版",ReferenceUi.ACTION_SIZE,appleSecondary(),false);
      row.addView(empty,new LinearLayout.LayoutParams(0,-2,1));
    }else{
      if(latest.equals(installed))current.setTextColor(ReferenceUi.inkPrimary());
      int sep=latest.indexOf(" · ");
      String verPart=sep>0?latest.substring(0,sep):latest;
      if(sep>0)badgeLabel=latest.substring(sep+3);
      String available=getString(R.string.latest_available_version,verPart);
      TextView target=ReferenceUi.mono(ReferenceUi.crisp(DownloadWorkspaceStyle.text(this,available,ReferenceUi.BODY_SIZE,ReferenceUi.inkPrimary(),true)));
      row.addView(target,new LinearLayout.LayoutParams(0,-2,1));
    }
    if(!badgeLabel.isEmpty()){
      boolean stable="正式版".equals(badgeLabel);
      TextView badge=new TextView(this);badge.setText(badgeLabel);badge.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,11f);
      badge.setTypeface(ReferenceUi.TYPE_SEMIBOLD);badge.setLetterSpacing(0.025f);badge.setTextColor(stable?appleSecondary():appleBlue());ReferenceUi.crisp(badge);
      badge.setBackground(stable
          ?new AppleSurface(this,7,0x14111827,0x1effffff)
          :new AppleSurface(this,7,0xffeef4ff,0xff1b2638));
      badge.setPadding(DesignUi.dp(this,7),DesignUi.dp(this,3),DesignUi.dp(this,7),DesignUi.dp(this,3));
      LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-2,-2);
      bp.setMarginStart(DesignUi.dp(this,8));
      row.addView(badge,bp);
    }
    strip.addView(row,new LinearLayout.LayoutParams(-1,-2));
    if(!packageVersion.isEmpty()&&!packageVersion.equals(latest)){
      TextView pkg=DownloadWorkspaceStyle.text(this,"更新包 "+packageVersion,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      pkg.setFontFeatureSettings("tnum");
      pkg.setPadding(0,DesignUi.dp(this,4),0,0);
      strip.addView(pkg);
    }
    if(installedNewer){
      TextView newer=DownloadWorkspaceStyle.text(this,"当前已安装版本较新",ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      newer.setPadding(0,DesignUi.dp(this,4),0,0);
      strip.addView(newer);
    }
    LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);
    params.topMargin=DesignUi.dp(this,12);
    card.addView(strip,params);
  }

  void render(Bundle b){
    downloadProgress=null;unknownSpinner=null;downloadDetails=null;downloadPercent=null;
    String state=b.getString("state","idle"),version=b.getString("versionDisplay",b.getString("version","")),message=b.getString("message","");boolean downloading="downloading".equals(state)||"waiting".equals(state),resumable="paused".equals(state)||("available".equals(state)||"error".equals(state))&&b.getBoolean("canResume");boolean busy=downloading||"verifying".equals(state)||"checking".equals(state)||"deleting".equals(state);
    LinearLayout card=updateCard();
    boolean failed="error".equals(state);
    boolean deleteRetry=b.getBoolean("packageDeleteRetry");
    String status;
    switch(state){
      case "ready": status="更新包已下载";break;
      case "paused": status="下载已暂停";break;
      case "waiting": status="等待继续下载";break;
      case "available": status="发现新版本";break;
      case "checking": status="正在检查更新";break;
      case "downloading": status="正在下载";break;
      case "verifying": status="正在核验安装包";break;
      case "deleting": status="正在删除安装包";break;
      case "error": status=resumable?"下载失败":"更新失败";break;
      default: status=message.isEmpty()?"尚未检查更新":message;
    }
    String timeSummary="";
    long checkedAt=b.getLong("checkedAt"),latestChecked=b.getLong("latestCheckedAt");
    long displayTime=(!busy&&checkedAt>0)?checkedAt:latestChecked;
    if(displayTime>0)timeSummary="上次检查："+dateTime(displayTime);
    statusHeading(card,status,timeSummary,state,failed,"ready".equals(state));
    String latest=b.getString("latestDisplay",b.getString("latestVersion",""));
    String activeChannel=AppUpdatePolicy.channelName(b.getString("channel","stable"));
    versionSummary(card,AppVersion.display(this),latest,version,activeChannel,
        b.getLong("latestCode")>0&&b.getLong("latestCode")<AppUpdateFiles.installed(this));
    if(downloading||resumable){
      downloadProgress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
      downloadProgress.setMax(1000);
      int progressColor=failed?ReferenceUi.redSolid():"paused".equals(state)?appleChevron():ReferenceUi.brandAccent();
      downloadProgress.setProgressTintList(ColorStateList.valueOf(progressColor));
      downloadProgress.setProgressBackgroundTintList(ColorStateList.valueOf(tone(0x17111827,0x1fffffff)));
      LinearLayout.LayoutParams barLayout=new LinearLayout.LayoutParams(-1,DesignUi.dp(this,6));
      barLayout.topMargin=DesignUi.dp(this,12);
      card.addView(downloadProgress,barLayout);
      LinearLayout progressRow=DesignUi.row(this);
      progressRow.setGravity(Gravity.CENTER_VERTICAL);
      progressRow.setPadding(0,DesignUi.dp(this,8),0,0);
      unknownSpinner=new ProgressBar(this);
      unknownSpinner.setIndeterminateTintList(ColorStateList.valueOf(appleBlue()));
      unknownSpinner.setVisibility(View.GONE);
      LinearLayout.LayoutParams spinLayout=new LinearLayout.LayoutParams(DesignUi.dp(this,16),DesignUi.dp(this,16));
      spinLayout.setMarginEnd(DesignUi.dp(this,8));
      progressRow.addView(unknownSpinner,spinLayout);
      downloadDetails=DownloadWorkspaceStyle.text(this,"",ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      downloadDetails.setFontFeatureSettings("tnum");
      progressRow.addView(downloadDetails,new LinearLayout.LayoutParams(0,-2,1));
      downloadPercent=DownloadWorkspaceStyle.text(this,"",ReferenceUi.ACTION_SIZE,failed?appleRedText():DesignUi.TEXT,true);
      downloadPercent.setFontFeatureSettings("tnum");
      downloadPercent.setVisibility(View.GONE);
      progressRow.addView(downloadPercent,new LinearLayout.LayoutParams(-2,-2));
      card.addView(progressRow,new LinearLayout.LayoutParams(-1,-2));
    }
    if(!message.isEmpty()&&!message.equals(status)){
      // The updater can return to available or ready after a failed attempt.
      if(failed||deleteRetry||"available".equals(state)||"ready".equals(state)){
        statusDetail(card,message,failed||deleteRetry);
      }else inlineCaption(card,message,false);
    }
    if(!installMessage.isEmpty())statusDetail(card,installMessage,true);

    java.util.List<Button> secondaryButtons=new java.util.ArrayList<>();
    Button mainButton=null;
    if(downloading||resumable){
      mainButton=downloading?tactileSecondary("暂停下载",()->action("pause")):solidPrimary("继续下载",()->action("resume"));
      Runnable cancelFlow=()->{
        ReferenceUi.Modal confirm=new ReferenceUi.Modal(this,"取消这次下载？").hideClose();
        confirm.body.addView(ReferenceUi.modalBanner(this,"trash","将删除已下载部分","会删除本次已下载的临时文件。仅想稍后继续，请选择暂停下载。",false),new LinearLayout.LayoutParams(-1,-2));
        confirm.buttons("保留下载",confirm::dismiss,"取消下载",()->{confirm.dismiss();action("cancel");});
        confirm.show();
      };
      secondaryButtons.add(downloading?tactileSecondary("取消下载",true,cancelFlow):quietAction("取消下载",true,cancelFlow));
    }else if("ready".equals(state)){
      mainButton=solidPrimary("安装更新",()->{if(pendingInstall>0)return;installMessage="";Bundle result=AppUpdates.call(this,"verify",null);pendingInstall=result.getLong("requestedSerial");rendered="";refresh();});
      secondaryButtons.add(quietAction("删除安装包",true,()->confirmDeletePackage(b)));
    }else if("available".equals(state)){
      long bytes=b.getLong("bytes");
      String downloadLabel=bytes>0?"下载更新 · "+mb(bytes)+" MB":"下载更新";
      mainButton=solidPrimary(downloadLabel,()->action("download"));
    }
    boolean separateDeleteRetry=deleteRetry&&mainButton!=null;
    if(deleteRetry&&!separateDeleteRetry){
      mainButton=solidPrimary("重试删除安装包",()->confirmDeletePackage(b));
    }
    if(!busy){
      if(mainButton==null)mainButton=tactileSecondary("检查更新",()->action("check"));
      else if(secondaryButtons.isEmpty())secondaryButtons.add(tactileSecondary("检查更新",()->action("check")));
      else secondaryButtons.add(quietAction("检查更新",false,()->action("check")));
    }
    if(mainButton!=null){
      LinearLayout actionsBlock=DesignUi.column(this);
      LinearLayout.LayoutParams blockParams=new LinearLayout.LayoutParams(-1,-2);
      blockParams.topMargin=DesignUi.dp(this,14);
      if(secondaryButtons.size()>=2){
        card.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,16),DesignUi.dp(this,16),DesignUi.dp(this,8));
        actionsBlock.addView(mainButton,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout subRow=DesignUi.row(this);
        LinearLayout.LayoutParams subParams=new LinearLayout.LayoutParams(-1,-2);
        subParams.topMargin=DesignUi.dp(this,4);
        for(int i=0;i<secondaryButtons.size();i++){
          Button sub=secondaryButtons.get(i);
          sub.setMinHeight(DesignUi.dp(this,44));sub.setMinimumHeight(DesignUi.dp(this,44));
          LinearLayout.LayoutParams slot=new LinearLayout.LayoutParams(0,-2,1);
          if(i>0)slot.setMarginStart(DesignUi.dp(this,8));
          subRow.addView(sub,slot);
        }
        actionsBlock.addView(subRow,subParams);
      }else if(secondaryButtons.size()==1){
        LinearLayout singleRow=DesignUi.row(this);
        ReferenceUi.styleDualButton(mainButton);
        ReferenceUi.styleDualButton(secondaryButtons.get(0));
        singleRow.addView(mainButton,new LinearLayout.LayoutParams(0,-2,1.6f));
        LinearLayout.LayoutParams subSlot=new LinearLayout.LayoutParams(0,-2,1);
        subSlot.setMarginStart(DesignUi.dp(this,8));
        singleRow.addView(secondaryButtons.get(0),subSlot);
        actionsBlock.addView(singleRow,new LinearLayout.LayoutParams(-1,-2));
      }else{
        actionsBlock.addView(mainButton,new LinearLayout.LayoutParams(-1,-2));
      }
      card.addView(actionsBlock,blockParams);
    }
    if(separateDeleteRetry){
      Button retryDelete=quietAction("重试删除安装包",true,()->confirmDeletePackage(b));
      retryDelete.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
      card.addView(retryDelete,new LinearLayout.LayoutParams(-1,-2));
    }
    if(latestChecked>0&&!busy&&checkedAt>0&&latestChecked!=checkedAt){
      TextView fetched=DownloadWorkspaceStyle.text(this,"版本获取："+dateTime(latestChecked),ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      fetched.setFontFeatureSettings("tnum");
      fetched.setPadding(0,DesignUi.dp(this,8),0,0);
      card.addView(fetched);
    }
    DesignUi.addCard(box,card);
    renderNotes(b);
    appleSection(box,"更新偏好");
    LinearLayout options=updateCard();
    options.setPadding(0,DesignUi.dp(this,4),0,DesignUi.dp(this,4));
    toggle(options,"自动检查更新","autoCheck",b.getBoolean("autoCheck",true));
    toggle(options,"Wi-Fi 下自动下载新版","autoDownload",b.getBoolean("autoDownload",false),true);
    toggle(options,"手动下载也仅使用 Wi-Fi","wifiOnly",b.getBoolean("wifiOnly",true),true);
    box.addView(options,new LinearLayout.LayoutParams(-1,-2));
    appleFooterNote(box,"内置网络使用所选环境线路；其他模式沿用手机连接。自动检查每天一次，安装前会请你确认。");
    appleSection(box,"更新通道");
    LinearLayout channels=updateCard();
    channels.setPadding(0,DesignUi.dp(this,2),0,DesignUi.dp(this,2));
    channels.setClipToOutline(true);
    renderChannels(channels,b);
    box.addView(channels,new LinearLayout.LayoutParams(-1,-2));
    appleFooterNote(box,"自动检查与下载只使用所选通道，安装前仍需确认。");
    boolean canChangeChannel=b.getBoolean("canChangeChannel",true);
    if(canChangeChannel&&b.getLong("packageStoredBytes")>0)appleFooterNote(box,"切换通道会清理当前更新缓存。");
    if(!canChangeChannel)appleFooterNote(box,b.getBoolean("downloadRequested")?"请先完成或取消当前下载，再切换更新通道。":"正在处理更新，请稍候再切换通道。");
    renderHistory(b.getString("latestVersion",""));
  }
  void renderChannels(LinearLayout parent,Bundle status){
    String[] channels={"stable","beta","candidate"};
    String[] hints={"2.x · 稳定推荐","2.1.x · 提前体验","验证版本 · 尚不稳定"};
    String selected=status.getString("channel","stable");boolean enabled=status.getBoolean("canChangeChannel",true);
    for(int i=0;i<channels.length;i++){
      String channel=channels[i];
      boolean isSelected=channel.equals(selected);
      if(i>0)appleDivider(parent,0,16);
      LinearLayout row=DesignUi.row(this);
      row.setGravity(Gravity.CENTER_VERTICAL);
      row.setMinimumHeight(DesignUi.dp(this,56));
      row.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,10),DesignUi.dp(this,16),DesignUi.dp(this,10));
      row.setBackground(new AppAppearance.GlassRipple(new AppleSurface(this,0,0,0),DesignUi.surface(this,Color.WHITE,0,Color.TRANSPARENT)));
      row.setEnabled(enabled);
      row.setSelected(isSelected);
      row.setAlpha(enabled?1f:.45f);
      String label=AppUpdatePolicy.channelName(channel);
      row.setContentDescription(label+"，"+hints[i]+(isSelected?"，已选中":""));
      LinearLayout copy=DesignUi.column(this);
      TextView name=DownloadWorkspaceStyle.text(this,label,15,DesignUi.TEXT,isSelected);
      copy.addView(name);
      TextView desc=DownloadWorkspaceStyle.text(this,hints[i],ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      desc.setPadding(0,DesignUi.dp(this,2),0,0);
      copy.addView(desc);
      row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
      ImageView check=DesignUi.icon(this,"check",appleBlue(),18);
      check.setVisibility(isSelected?View.VISIBLE:View.INVISIBLE);
      check.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      row.addView(check);
      row.setOnClickListener(v->{
        if(!enabled||selected.equals(channel))return;
        Bundle request=new Bundle();request.putString("channel",channel);request.putInt("originSlot",originSlot);
        Bundle result=AppUpdates.call(this,"channel",request);
        installMessage=result.getString("channelError","");pendingInstall=0;permissionPending=false;technicalExpanded=false;redraw();
      });
      parent.addView(row,new LinearLayout.LayoutParams(-1,-2));
    }
  }
  String dateTime(long time){return android.text.format.DateFormat.getDateFormat(this).format(new java.util.Date(time))+" "+android.text.format.DateFormat.getTimeFormat(this).format(new java.util.Date(time));}
  void redraw(){rendered="";refresh();}
  void releaseLink(LinearLayout parent,String url){TextView link=DesignUi.text(this,"官方发布页："+url,13,appleSecondary());link.setTextIsSelectable(true);link.setPadding(0,DesignUi.dp(this,8),0,0);parent.addView(link);}
  private void inlineCaption(LinearLayout parent,String text,boolean spinning){
    if(spinning){
      LinearLayout row=DesignUi.row(this);row.setPadding(0,DesignUi.dp(this,8),0,DesignUi.dp(this,4));
      ProgressBar spin=new ProgressBar(this);spin.setIndeterminateTintList(ColorStateList.valueOf(appleBlue()));
      LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(DesignUi.dp(this,16),DesignUi.dp(this,16));sp.setMarginEnd(DesignUi.dp(this,8));
      row.addView(spin,sp);
      TextView t=DownloadWorkspaceStyle.text(this,text,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);t.setFontFeatureSettings("tnum");
      row.addView(t,new LinearLayout.LayoutParams(0,-2,1));
      parent.addView(row,new LinearLayout.LayoutParams(-1,-2));
      return;
    }
    TextView t=DownloadWorkspaceStyle.text(this,text,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
    t.setFontFeatureSettings("tnum");ReferenceUi.balancedBreaks(t);
    t.setPadding(0,DesignUi.dp(this,6),0,DesignUi.dp(this,2));
    parent.addView(t,new LinearLayout.LayoutParams(-1,-2));
  }
  void renderNotes(Bundle b){if(b.getString("latestVersion","").isEmpty())return;ReleaseNotes model=AppUpdateManager.get(this).latestNotes;appleSection(box,"更新说明");LinearLayout notes=updateCard();if(model.user.isEmpty())inlineCaption(notes,"此版本尚未提供简要更新说明，完整原文见技术详情",false);else ReleaseNotesRenderer.append(notes,model.user);if(!model.technical.isEmpty()){appleDivider(notes,10,0);disclosureAction(notes,technicalExpanded?"收起技术详情":"展开技术详情",technicalExpanded,()->{technicalExpanded=!technicalExpanded;redraw();});if(technicalExpanded){ReleaseNotesRenderer.append(notes,model.technical);releaseLink(notes,ReleaseHistoryPolicy.WEB+"/tag/"+b.getString("latestTag","v"+b.getString("latestVersion")+"-gecko"));}}box.addView(notes,new LinearLayout.LayoutParams(-1,-2));}
  void renderHistory(String ceiling){LinearLayout card=updateCard();card.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,6),DesignUi.dp(this,16),DesignUi.dp(this,6));disclosureAction(card,historyExpanded?"收起历史版本记录":"展开历史版本记录",historyExpanded,()->{historyExpanded=!historyExpanded;if(historyExpanded)history.load(historyClient,historyVisible,false);else{history.detach(historyClient);historyClient=history.attach(originSlot);}redraw();});historyBody=DesignUi.column(this);card.addView(historyBody);LinearLayout.LayoutParams cardParams=new LinearLayout.LayoutParams(-1,-2);cardParams.topMargin=DesignUi.dp(this,18);box.addView(card,cardParams);historyRevision=-1;refreshHistory(ceiling);}
  void refreshHistory(String ceiling){if(historyBody==null)return;Bundle state=history.status();long revision=state.getLong("revision");if(revision==historyRevision)return;historyRevision=revision;ScrollView scroller=null;for(ViewParent p=historyBody.getParent();p!=null;p=p.getParent())if(p instanceof ScrollView){scroller=(ScrollView)p;break;}String anchor="";int oldTop=0;int[] position=new int[2],viewport=new int[2];if(scroller!=null){scroller.getLocationOnScreen(viewport);for(int i=0;i<historyBody.getChildCount();i++){View row=historyBody.getChildAt(i);if(!(row.getTag() instanceof String))continue;row.getLocationOnScreen(position);if(position[1]+row.getHeight()>viewport[1]){anchor=(String)row.getTag();oldTop=position[1];break;}}}historyBody.removeAllViews();if(!historyExpanded)return;
    long fetched=state.getLong("fetchedAt");if(fetched>0)inlineCaption(historyBody,"本地记录 · 上次获取 "+dateTime(fetched),false);if(state.getBoolean("loading"))inlineCaption(historyBody,"正在读取历史记录…",true);if(!state.getString("error","").isEmpty())statusDetail(historyBody,state.getString("error"),true);
    java.util.List<ReleaseHistoryPolicy.Entry> rows=history.visible(historyVisible,ceiling);for(ReleaseHistoryPolicy.Entry entry:rows){LinearLayout row=DesignUi.column(this);row.setTag(entry.tag);appleDivider(row,8,0);TextView heading=DownloadWorkspaceStyle.text(this,entry.version+" · "+(entry.published>0?android.text.format.DateFormat.getDateFormat(this).format(new java.util.Date(entry.published)):"日期未提供"),15,DesignUi.TEXT,true);heading.setFontFeatureSettings("tnum");heading.setPadding(0,DesignUi.dp(this,12),0,0);row.addView(heading);
      boolean open=entry.tag.equals(expandedHistory);disclosureAction(row,open?"收起更新内容":"展开更新内容",open,()->{expandedHistory=open?"":entry.tag;expandedTechnical="";historyRevision=-1;refreshHistory(ceiling);});
      if(open){if(entry.notes.user.isEmpty())inlineCaption(row,"此版本的完整说明保留在技术详情中",false);else ReleaseNotesRenderer.append(row,entry.notes.user);if(!entry.notes.technical.isEmpty()){boolean technical=entry.tag.equals(expandedTechnical);disclosureAction(row,technical?"收起技术详情":"展开技术详情（历史原文）",technical,()->{expandedTechnical=technical?"":entry.tag;historyRevision=-1;refreshHistory(ceiling);});if(technical)ReleaseNotesRenderer.append(row,entry.notes.technical);}releaseLink(row,entry.url);}historyBody.addView(row);}
    if(rows.isEmpty()&&!state.getBoolean("loading"))inlineCaption(historyBody,"暂未取得历史版本记录",false);
    if(!state.getBoolean("loading")){
      LinearLayout footerRow=DesignUi.row(this);
      footerRow.setPadding(0,DesignUi.dp(this,6),0,0);
      Button refreshBtn=ReferenceUi.link(this,"刷新历史记录",()->{history.load(historyClient,historyVisible,true);historyRevision=-1;refreshHistory(ceiling);});
      refreshBtn.setTextSize(ReferenceUi.ACTION_SIZE);refreshBtn.setTextColor(appleBlue());ReferenceUi.readable(refreshBtn);
      footerRow.addView(refreshBtn,new LinearLayout.LayoutParams(-2,-2));
      if(historyVisible<100&&(history.visible(100,ceiling).size()>rows.size()||!state.getBoolean("eof")&&!state.getBoolean("capped"))){
        Button moreBtn=ReferenceUi.link(this,"加载更多",()->{historyVisible=Math.min(100,historyVisible+10);history.load(historyClient,historyVisible,false);historyRevision=-1;refreshHistory(ceiling);});
        moreBtn.setTextSize(ReferenceUi.ACTION_SIZE);moreBtn.setTextColor(appleBlue());ReferenceUi.readable(moreBtn);
        LinearLayout.LayoutParams moreParams=new LinearLayout.LayoutParams(-2,-2);moreParams.setMarginStart(DesignUi.dp(this,16));
        footerRow.addView(moreBtn,moreParams);
      }
      historyBody.addView(footerRow,new LinearLayout.LayoutParams(-1,-2));
      if(state.getBoolean("capped"))inlineCaption(historyBody,"已达到历史记录上限；更多版本："+ReleaseHistoryPolicy.WEB,false);
    }
    if(scroller!=null&&!anchor.isEmpty()){final ScrollView scroll=scroller;final String tag=anchor;final int top=oldTop;final LinearLayout shown=historyBody;shown.post(()->{if(historyBody!=shown)return;View row=shown.findViewWithTag(tag);if(row!=null){int[] at=new int[2];row.getLocationOnScreen(at);scroll.scrollTo(0,Math.max(0,scroll.getScrollY()+at[1]-top));}});}
  }
  void updateProgress(Bundle b){
    if(downloadProgress==null||downloadDetails==null)return;
    long total=b.getLong("total",b.getLong("bytes"));
    long received=Math.max(0,b.getLong("received"));
    long speed=b.getLong("bytesPerSecond"),seconds=b.getLong("remainingSeconds",-1);
    String state=b.getString("state","");
    boolean active="downloading".equals(state);
    boolean unknownActive=total<=0&&(active||"waiting".equals(state));
    downloadProgress.setVisibility(total>0?View.VISIBLE:View.GONE);
    if(unknownSpinner!=null)unknownSpinner.setVisibility(unknownActive?View.VISIBLE:View.GONE);
    String text="已下载 "+mb(received)+" MB";
    String pct="";
    if(total>0){
      int progress=(int)Math.min(1000,received*1000.0/total);
      downloadProgress.setProgress(progress);
      text=mb(received)+" / "+mb(total)+" MB";
      pct=(progress/10)+"%";
    }
    if(total>0&&active&&speed>0){
      text+="\n"+(speed>=1048576?mb(speed)+" MB/s":String.format(Locale.getDefault(),"%.0f KB/s",speed/1024.0));
      if(seconds>=0)text+=" · 约剩 "+(seconds<60?seconds+" 秒":(seconds+59)/60+" 分钟");
    }
    if(!text.contentEquals(downloadDetails.getText()))downloadDetails.setText(text);
    if(downloadPercent!=null){
      downloadPercent.setVisibility(pct.isEmpty()?View.GONE:View.VISIBLE);
      if(!pct.contentEquals(downloadPercent.getText()))downloadPercent.setText(pct);
    }
  }
  void toggle(LinearLayout parent,String text,String key,boolean value){
    toggle(parent,text,key,value,false);
  }
  void toggle(LinearLayout parent,String text,String key,boolean value,boolean divider){
    if(divider)appleDivider(parent,0,16);
    Switch option=new Switch(this);option.setText(text);option.setTextSize(15);option.setTextColor(DesignUi.TEXT);option.setChecked(value);NativeControls.prepare(option);
    ReferenceUi.styleSwitch(option);
    option.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,11),DesignUi.dp(this,16),DesignUi.dp(this,11));parent.addView(option,new LinearLayout.LayoutParams(-1,-2));option.setOnCheckedChangeListener((button,enabled)->{Bundle extras=new Bundle();extras.putBoolean(key,enabled);AppUpdates.call(this,"settings",extras);rendered="";});
  }
  static String mb(long bytes){return String.format(Locale.getDefault(),"%.1f",bytes/1048576.0);}
  void installIssue(String message){installMessage=message;rendered="";refresh();}
  AlertDialog confirmDeletePackage(Bundle shown){
    LinearLayout box=DesignUi.column(this);box.setPadding(DesignUi.dp(this,20),DesignUi.dp(this,8),DesignUi.dp(this,20),DesignUi.dp(this,8));
    box.addView(ReferenceUi.modalBanner(this,"trash","将删除已下载的更新安装包","会释放对应存储空间；更新偏好与通道设置会保留，之后可随时重新下载。",false),new LinearLayout.LayoutParams(-1,-2));
    return AppAppearance.dialog(this).setTitle("删除安装包？").setView(box).setNegativeButton("保留安装包",null).setPositiveButton("删除安装包",(dialog,which)->{pendingInstall=0;permissionPending=false;Bundle extras=new Bundle();extras.putLong("code",shown.getLong("code"));extras.putString("packageUri",shown.getString("packageUri",shown.getString("uri","")));Bundle result=AppUpdates.call(this,"deletePackage",extras);installMessage=result.getString("deleteError","");rendered="";refresh();}).show();
  }
  void install(){Bundle status=AppUpdates.call(this,"status",null);String target=status.getString("uri","");if(target.isEmpty()){installIssue("安装包尚未准备好，请重新下载");return;}
    if(!getPackageManager().canRequestPackageInstalls()){
      ReferenceUi.Modal guide=new ReferenceUi.Modal(this,"允许安装应用更新");
      LinearLayout card=ReferenceUi.modalGroup(this);
      LinearLayout row=DesignUi.row(this);row.setGravity(Gravity.TOP);
      row.setPadding(DesignUi.dp(this,16),DesignUi.dp(this,14),DesignUi.dp(this,16),DesignUi.dp(this,14));
      ImageView icon=new ImageView(this);icon.setImageDrawable(new ReferenceUi.IconTileDrawable(this,"shield",30,false,true));
      icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(DesignUi.dp(this,30),DesignUi.dp(this,30));ip.topMargin=DesignUi.dp(this,2);ip.setMarginEnd(DesignUi.dp(this,12));
      row.addView(icon,ip);
      LinearLayout copy=DesignUi.column(this);
      copy.addView(ReferenceUi.workspaceText(this,"需要开启本应用安装权限",15,DesignUi.TEXT,true));
      TextView detail=ReferenceUi.workspaceText(this,"在系统设置中允许本应用安装未知来源更新，返回后即可继续安装。",ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
      ReferenceUi.balancedBreaks(detail);
      detail.setPadding(0,DesignUi.dp(this,4),0,0);
      copy.addView(detail,new LinearLayout.LayoutParams(-1,-2));
      row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
      card.addView(row,new LinearLayout.LayoutParams(-1,-2));
      guide.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
      guide.buttons("稍后",guide::dismiss,"前往设置",()->{guide.dismiss();try{permissionPending=true;startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName())));}catch(Exception e){permissionPending=false;installIssue("请在手机设置中允许本应用安装未知应用");}});
      guide.show();return;
    }
    try{Uri uri=Uri.parse(target);Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("应用更新",uri));startActivity(intent);}catch(Exception e){installIssue("无法打开安装界面，请检查系统安装权限后重试");}
  }
}
