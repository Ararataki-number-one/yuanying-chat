package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** User-initiated system document picker. This activity creates no Gecko session. */
public final class EnvironmentConfigBackupActivity extends ThemedActivity {
  static final int EXPORT=841,IMPORT=842;
  private static final String IMPORT_PICKER_PENDING="environmentConfigImportPending";
  final ExecutorService worker=Executors.newSingleThreadExecutor();
  volatile long owner=1;boolean busy;int picker;byte[] pending;
  TextView result;
  @Override public void onCreate(Bundle state){
    super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    if(state!=null&&state.getBoolean(IMPORT_PICKER_PENDING))picker=IMPORT;
    showHome();
  }

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

  private void appleSection(LinearLayout parent,String title){
    TextView h=new TextView(this);h.setText(title);h.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,12f);
    h.setTypeface(ReferenceUi.TYPE_SEMIBOLD);h.setLetterSpacing(0.045f);h.setTextColor(tone(0xff4e535e,0xff949ba8));ReferenceUi.crisp(h);
    h.setPadding(dp(16),dp(parent.getChildCount()==0?6:20),dp(16),dp(6));
    if(Build.VERSION.SDK_INT>=28)h.setAccessibilityHeading(true);
    parent.addView(h,new LinearLayout.LayoutParams(-1,-2));
  }

  private void styleAppleSheet(ReferenceUi.Modal dialog){
    dialog.root.setBackground(new ReferenceUi.CardSurfaceDrawable(this,24f,0xfff2f3f6,0xff121318));
    dialog.root.setClipChildren(false);
    dialog.head.setClipChildren(false);dialog.head.setClipToPadding(false);
  }
  private Drawable sheetGroupCard(){
    return new ReferenceUi.CardSurfaceDrawable(this,20f);
  }
  private void stylePrimary(Button button){
    ReferenceUi.stylePill(button,true,false);
  }
  private void styleGrayButton(Button button){
    ReferenceUi.stylePill(button,false,false);
  }
  private void polishSettingsGroup(LinearLayout group){
    group.setElevation(0f);
    group.setBackground(new ReferenceUi.CardSurfaceDrawable(this,20f));
    group.setClipToOutline(true);
  }
  private void polishRowIcon(LinearLayout group,String glyph){
    View last=group.getChildAt(group.getChildCount()-1);
    if(!(last instanceof ViewGroup))return;
    ViewGroup row=(ViewGroup)last;
    View first=row.getChildAt(0);
    if(first instanceof ImageView){
      ImageView icon=(ImageView)first;
      int sz=dp(22),pad=dp(1);
      icon.setLayoutParams(new LinearLayout.LayoutParams(sz,sz));
      icon.setPadding(pad,pad,pad,pad);
      boolean primary="backup".equals(glyph);
      icon.setImageDrawable(new Ui.Icon(glyph,primary?appleBlue():tone(0xff4a4e59,0xff9fa5b2)));
      icon.setBackground(null);
    }
    View tail=row.getChildAt(row.getChildCount()-1);
    if(tail instanceof ImageView&&tail!=first){
      ((ImageView)tail).setImageDrawable(new Ui.Icon("chevron-right",appleChevron()));
    }
  }
  private void applyEnvMonogram(LinearLayout group,String envName){
    View last=group.getChildAt(group.getChildCount()-1);
    if(!(last instanceof ViewGroup))return;
    ViewGroup row=(ViewGroup)last;
    if(row.getChildCount()==0)return;
    String trimmed=envName==null?"":envName.trim();
    String ch=trimmed.isEmpty()?"环":trimmed.substring(0,trimmed.offsetByCodePoints(0,1));
    TextView badge=ReferenceUi.workspaceText(this,ch,14,tone(0xff4a4e59,0xffd0d4de),true);
    badge.setGravity(Gravity.CENTER);
    badge.setBackground(new AppleSurface(this,9,0xfff8f9fb,0xff20222a,0x140f172a,0x1affffff));
    badge.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    int sz=dp(32);
    row.removeViewAt(0);
    row.addView(badge,0,new LinearLayout.LayoutParams(sz,sz));
    View tail=row.getChildAt(row.getChildCount()-1);
    if(tail instanceof ImageView){
      ((ImageView)tail).setImageDrawable(new Ui.Icon("chevron-right",appleChevron()));
    }
  }

  private void showHome(){
    LinearLayout root=DesignUi.screen(this);
    root.setClipChildren(false);root.setClipToPadding(false);
    root.setBackgroundColor(ReferenceUi.canvasBg());
    LinearLayout body=DesignUi.column(this);
    body.setPadding(dp(16),dp(8),dp(16),dp(24));
    ScrollView scroll=new ScrollView(this);
    scroll.setFillViewport(true);
    NativeControls.prepare(scroll);
    scroll.addView(body,new ScrollView.LayoutParams(-1,-2));
    FrameLayout header=ReferenceUi.horologyHeader(this,"环境配置备份","加密导出模板，恢复时创建新环境",this::finish,scroll);
    root.addView(header,new LinearLayout.LayoutParams(-1,-2));
    FrameLayout viewport=new FrameLayout(this);
    viewport.setClipChildren(true);viewport.setClipToPadding(true);
    viewport.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
    root.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));

    LinearLayout actions=SettingsWorkspaceStyle.group(this);
    polishSettingsGroup(actions);
    SettingsWorkspaceStyle.row(this,actions,"选择环境并备份","导出所选环境的加密配置","backup",this::chooseSource);
    polishRowIcon(actions,"backup");
    SettingsWorkspaceStyle.row(this,actions,"选择备份并恢复","解密后预览，创建新环境","undo",this::chooseBackupFile);
    polishRowIcon(actions,"undo");
    body.addView(actions,new LinearLayout.LayoutParams(-1,-2));

    result=ReferenceUi.prose(ReferenceUi.workspaceText(this,"",ReferenceUi.BODY_SIZE,DesignUi.TEXT,false));
    result.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    result.setPadding(dp(16),dp(12),dp(16),dp(12));
    result.setBackground(new ReferenceUi.CardSurfaceDrawable(this,20f));
    result.setVisibility(View.GONE);
    LinearLayout.LayoutParams resultParams=new LinearLayout.LayoutParams(-1,-2);
    resultParams.topMargin=dp(12);
    body.addView(result,resultParams);

    appleSection(body,"加密范围");
    LinearLayout scope=SettingsWorkspaceStyle.group(this);
    polishSettingsGroup(scope);
    int green=appleGreenText();
    scopeRow(scope,"check",green,green,true,"随备份导出","环境名称、浏览器模板、网页语言和使用偏好。");
    scopeRow(scope,"lock",appleSecondary(),DesignUi.TEXT,false,"不随备份","网络账号、订阅、固定出口、登录状态、Cookie、聊天、草稿、附件和设备密钥。");
    body.addView(scope,new LinearLayout.LayoutParams(-1,-2));
    scopeNote(body,"请妥善保管加密密码，忘记后无法解密备份。",8);
    setContentView(root);
  }
  void chooseBackupFile(){
    if(busy||picker!=0)return;
    clearPending();
    try{
      picker=IMPORT;
      startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT)
          .addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),IMPORT);
    }catch(Exception failure){
      picker=0;
      message("设备没有可用的文件选择器");
    }
  }
  private int dp(int size){return DesignUi.dp(this,size);}
  private void scopeRow(LinearLayout group,String glyph,int iconTone,int titleTone,boolean included,String label,String value){
    if(group.getChildCount()>0){
      View rule=new View(this);
      rule.setBackgroundColor(ReferenceUi.dividerColor());
      rule.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      LinearLayout.LayoutParams divider=new LinearLayout.LayoutParams(-1,Math.max(1,Math.round(ReferenceUi.dpF(this,0.5f))));
      divider.setMarginStart(dp(16));
      group.addView(rule,divider);
    }
    LinearLayout block=DesignUi.column(this);
    block.setPadding(dp(16),dp(14),dp(16),dp(14));
    LinearLayout heading=DesignUi.row(this);
    ImageView badge=new ImageView(this);
    badge.setImageDrawable(new Ui.Icon(glyph,iconTone));
    int bp=dp(5);
    badge.setPadding(bp,bp,bp,bp);
    badge.setBackground(included
        ?new AppleSurface(this,7,0x1a15804e,0x2934d38b)
        :new AppleSurface(this,7,0x14111827,0x1fffffff));
    badge.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    LinearLayout.LayoutParams iconLayout=new LinearLayout.LayoutParams(dp(24),dp(24));
    iconLayout.setMarginEnd(dp(8));
    heading.addView(badge,iconLayout);
    TextView name=ReferenceUi.crisp(ReferenceUi.workspaceText(this,label,ReferenceUi.ACTION_SIZE,titleTone,true));
    name.setTypeface(ReferenceUi.TYPE_SEMIBOLD);
    heading.addView(name,new LinearLayout.LayoutParams(0,-2,1));
    block.addView(heading,new LinearLayout.LayoutParams(-1,-2));
    TextView content=ReferenceUi.prose(ReferenceUi.workspaceText(this,value,ReferenceUi.BODY_SIZE,DesignUi.TEXT,false));
    content.setPadding(0,dp(7),0,0);
    block.addView(content,new LinearLayout.LayoutParams(-1,-2));
    group.addView(block,new LinearLayout.LayoutParams(-1,-2));
  }
  private TextView detailRow(LinearLayout rows,String label,String value){
    if(rows.getChildCount()>0){
      View rule=new View(this);
      rule.setBackgroundColor(ReferenceUi.dividerColor());
      rule.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      rows.addView(rule,new LinearLayout.LayoutParams(-1,Math.max(1,Math.round(ReferenceUi.dpF(this,0.5f)))));
    }
    LinearLayout row=DesignUi.row(this);
    row.setGravity(Gravity.TOP);
    row.setBaselineAligned(true);
    row.setPadding(0,dp(10),0,dp(10));
    TextView name=ReferenceUi.crisp(ReferenceUi.workspaceText(this,label,ReferenceUi.ACTION_SIZE,ReferenceUi.specKeyInk(),false));
    name.setTypeface(ReferenceUi.TYPE_REGULAR);
    name.setPaddingRelative(0,0,dp(10),0);
    row.addView(name,new LinearLayout.LayoutParams(dp(78),-2));
    TextView content=ReferenceUi.prose(ReferenceUi.workspaceText(this,value,ReferenceUi.BODY_SIZE,DesignUi.TEXT,false));
    content.setTypeface(ReferenceUi.TYPE_MEDIUM);
    row.addView(content,new LinearLayout.LayoutParams(0,-2,1));
    rows.addView(row,new LinearLayout.LayoutParams(-1,-2));
    return content;
  }
  private void scopeNote(LinearLayout parent,String text,int gap){
    TextView note=ReferenceUi.workspaceText(this,text,ReferenceUi.SECONDARY_SIZE,appleSecondary(),false);
    ReferenceUi.balancedBreaks(note);
    note.setPadding(dp(16),dp(gap),dp(16),0);
    parent.addView(note,new LinearLayout.LayoutParams(-1,-2));
  }
  boolean active(long serial){return serial==owner&&!isFinishing()&&!isDestroyed();}
  void message(String text){
    if(isFinishing()||isDestroyed())return;
    result.setVisibility(text.isEmpty()?View.GONE:View.VISIBLE);
    result.setText(text);
  }
  void chooseSource(){
    if(busy||picker!=0)return;clearPending();busy=true;long serial=owner;message("正在读取环境列表…");
    worker.execute(()->{
      List<String> names=new ArrayList<>();List<EnvironmentSpec.Identity> identities=new ArrayList<>();boolean read=false;
      try{if(!active(serial))return;ProfileCatalog catalog=ProfileCatalog.get(this);JSONArray rows=catalog.list();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(!AppSettings.selectable(row))continue;identities.add(catalog.identity(row.optInt("slot")));names.add(row.optString("name"));}read=true;}catch(Exception ignored){}
      boolean complete=read;runOnUiThread(()->{if(!active(serial))return;busy=false;if(!complete){message("环境列表暂时无法读取，请重试");return;}message("");ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"选择备份环境");
        styleAppleSheet(dialog);
        dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        if(!names.isEmpty()){
          LinearLayout list=DesignUi.column(this);
          list.setBackground(sheetGroupCard());
          list.setClipToOutline(true);
          for(int i=0;i<names.size();i++){
            EnvironmentSpec.Identity expected=identities.get(i);
            SettingsWorkspaceStyle.row(this,list,names.get(i),"","window",()->{
              dialog.dismiss();
              password(true,secret->export(expected,secret));
            });
            applyEnvMonogram(list,names.get(i));
          }
          dialog.body.addView(list,new LinearLayout.LayoutParams(-1,-2));
        }
        if(names.isEmpty())dialog.body.addView(ReferenceUi.modalEmpty(this,"window","暂时没有可用环境","请先在环境列表创建至少一个环境，再导出加密配置备份。"),new LinearLayout.LayoutParams(-1,-2));
        dialog.buttons("取消",dialog::dismiss,"",()->{});
        styleGrayButton((Button)dialog.footer.getChildAt(0));
        dialog.show();
      });
    });
  }
  interface PasswordAction {void run(char[] secret);}
  void password(boolean creating,PasswordAction action){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,creating?"加密备份":"打开加密备份");
    dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    LinearLayout card=ReferenceUi.modalGroup(this);
    EditText password=ReferenceUi.modalInput(card,"备份密码","","10–256 个字符",true);
    password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
    password.setSaveEnabled(false);
    password.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(256)});
    DesignUi.visiblePassword(password);
    EditText repeat=creating?ReferenceUi.modalInput(card,"再次输入密码","","再次输入相同密码",true):null;
    if(repeat!=null){
      repeat.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
      repeat.setSaveEnabled(false);
      repeat.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(256)});
      repeat.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
      DesignUi.visiblePassword(repeat);
    }else password.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
    dialog.body.addView(card,new LinearLayout.LayoutParams(-1,-2));
    ReferenceUi.modalFooterNote(dialog.body,creating?"请妥善保管加密密码，遗忘后无法找回或解密备份。":"输入创建备份时使用的密码，解密后可先查看恢复预览。");
    TextView error=ReferenceUi.workspaceText(this,"",ReferenceUi.ACTION_SIZE,appleRedText(),false);
    error.setPadding(dp(16),dp(8),dp(16),0);
    error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    error.setVisibility(View.GONE);
    dialog.body.addView(error,new LinearLayout.LayoutParams(-1,-2));
    dialog.setOnDismissListener(d->{password.setText("");if(repeat!=null)repeat.setText("");});
    dialog.buttons("取消",dialog::dismiss,creating?"选择保存位置":"解密并预览",()->{
      int length=password.length();
      if(length<10||length>256){
        error.setText(R.string.backup_password_length_error);error.setVisibility(View.VISIBLE);
        password.setError("请输入 10–256 个字符");ReferenceUi.hapticReject(password);password.requestFocus();dialog.resize();return;
      }
      boolean matching=true;
      if(repeat!=null){
        matching=repeat.length()==length;
        for(int i=0;matching&&i<length;i++)matching=password.getText().charAt(i)==repeat.getText().charAt(i);
      }
      if(!matching){
        error.setText(R.string.backup_password_mismatch);error.setVisibility(View.VISIBLE);
        repeat.setError("两次密码不一致");ReferenceUi.hapticReject(repeat);repeat.requestFocus();dialog.resize();return;
      }
      char[] secret=new char[length];password.getText().getChars(0,length,secret,0);dialog.dismiss();action.run(secret);
    });
    dialog.show();
    dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
    password.requestFocus();
  }
  void export(EnvironmentSpec.Identity expected,char[] password){
    if(busy){Arrays.fill(password,'\0');return;}busy=true;long serial=owner;message("正在加密配置…");
    worker.execute(()->{
      byte[] encrypted=null;String error="";try{if(!active(serial))return;Context source=Profiles.context(this,expected.slot);encrypted=EnvironmentConfigBackup.encrypt(EnvironmentConfigTransfer.capture(source,expected),password);}catch(Exception failure){error="配置读取或加密失败，未生成备份，请重试";}finally{Arrays.fill(password,'\0');}
      byte[] ready=encrypted;String issue=error;runOnUiThread(()->{if(!active(serial)){if(ready!=null)Arrays.fill(ready,(byte)0);return;}busy=false;if(!issue.isEmpty()){message(issue);return;}pending=ready;
        try{picker=EXPORT;startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,"PocketChat-环境配置.pocketcfg"),EXPORT);message("请选择备份保存位置");}catch(Exception failure){picker=0;clearPending();message("设备没有可用的文件保存器");}
      });
    });
  }
  @Override protected void onSaveInstanceState(Bundle state){
    super.onSaveInstanceState(state);
    state.putBoolean(IMPORT_PICKER_PENDING,picker==IMPORT);
  }
  @Override protected void onActivityResult(int request,int code,Intent data){
    super.onActivityResult(request,code,data);if((request!=EXPORT&&request!=IMPORT)||picker!=request)return;picker=0;
    if(code!=RESULT_OK||data==null||data.getData()==null){if(request==EXPORT)clearPending();return;}Uri uri=data.getData();
    if(!"content".equals(uri.getScheme())||uri.getAuthority()==null||uri.getAuthority().startsWith(getPackageName()+".")){if(request==EXPORT)clearPending();message("请选择系统文件提供者中的文件");return;}
    if(busy)return;busy=true;long serial=owner;
    if(request==EXPORT){byte[] bytes=pending;pending=null;if(bytes==null){busy=false;message("备份任务已失效，请重新选择环境");return;}message("正在保存备份…");worker.execute(()->{
      boolean written=false,verified=false;try{if(!active(serial))return;try(OutputStream stream=getContentResolver().openOutputStream(uri,"w")){if(stream==null)throw new IOException();stream.write(bytes);stream.flush();}written=true;
        try(InputStream stream=getContentResolver().openInputStream(uri)){byte[] reread=EnvironmentConfigBackup.read(stream);try{verified=java.security.MessageDigest.isEqual(bytes,reread);}finally{Arrays.fill(reread,(byte)0);}}
      }catch(Exception ignored){}finally{Arrays.fill(bytes,(byte)0);}
      boolean accepted=written,complete=verified;runOnUiThread(()->{if(!active(serial))return;busy=false;message(complete?"备份已保存并读回核对，请保管密码。网络配置与登录未包含在内。":accepted?"文件已交给保存器，但读回未确认，请检查备份文件并重试。":"备份写入未完成，请删除不完整文件后重试");});
    });}else{message("正在读取备份…");worker.execute(()->{
      byte[] bytes=null;try{if(!active(serial))return;try(InputStream stream=getContentResolver().openInputStream(uri)){bytes=EnvironmentConfigBackup.read(stream);}}catch(Exception ignored){}
      byte[] ready=bytes;runOnUiThread(()->{if(!active(serial)){if(ready!=null)Arrays.fill(ready,(byte)0);return;}busy=false;if(ready==null){message("备份不可读取或超过 64 KB，原环境未改变");return;}pending=ready;password(false,this::decrypt);});
    });}
  }
  void decrypt(char[] password){
    byte[] bytes=pending;pending=null;if(busy||bytes==null){Arrays.fill(password,'\0');message("请重新选择备份文件");return;}busy=true;long serial=owner;message("正在解密并验证…");
    worker.execute(()->{EnvironmentConfigBackup.Config config=null;try{if(!active(serial))return;config=EnvironmentConfigBackup.decrypt(bytes,password);}catch(Exception ignored){}finally{Arrays.fill(password,'\0');Arrays.fill(bytes,(byte)0);}
      EnvironmentConfigBackup.Config safe=config;runOnUiThread(()->{if(!active(serial))return;busy=false;if(safe==null){message("密码不正确、文件已损坏或版本不支持，原环境未改变");return;}preview(safe);});
    });
  }
  void preview(EnvironmentConfigBackup.Config config){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"恢复预览");
    styleAppleSheet(dialog);
    dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    LinearLayout summary=DesignUi.column(this);
    summary.setBackground(sheetGroupCard());
    summary.setPadding(dp(16),dp(4),dp(16),dp(4));
    detailRow(summary,"环境名称",config.name).setTextIsSelectable(true);
    detailRow(summary,"浏览器模板",config.browser.label()).setTextIsSelectable(true);
    detailRow(summary,"网页语言",config.browser.locales.isEmpty()?"跟随系统":String.join(", ",config.browser.locales))
        .setTextIsSelectable(true);
    LinearLayout.LayoutParams summaryParams=new LinearLayout.LayoutParams(-1,-2);
    summaryParams.topMargin=dp(4);
    dialog.body.addView(summary,summaryParams);
    java.util.concurrent.atomic.AtomicBoolean visible=new java.util.concurrent.atomic.AtomicBoolean(true);dialog.setOnDismissListener(d->visible.set(false));
    LinearLayout guarantee=ReferenceUi.modalBanner(this,"shield","将创建新环境，现有环境不会被覆盖。","创建后，请配置网络、核验固定出口并登录。如中途离开，请先在环境列表确认结果，再决定是否重试。",true);
    LinearLayout.LayoutParams gParams=new LinearLayout.LayoutParams(-1,-2);
    gParams.topMargin=dp(12);
    dialog.body.addView(guarantee,gParams);
    Spinner engine=BrowserSettingsUi.creationPicker(this,dialog.body,EnvironmentEngine.GECKO);
    TextView error=ReferenceUi.workspaceText(this,"",ReferenceUi.ACTION_SIZE,appleRedText(),false);
    error.setPadding(dp(4),dp(8),dp(4),0);
    error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    error.setVisibility(View.GONE);
    dialog.body.addView(error,new LinearLayout.LayoutParams(-1,-2));
    dialog.buttons("取消",dialog::dismiss,"创建新环境",()->{
      if(busy)return;busy=true;long serial=owner;dialog.primary().setEnabled(false);error.setTextColor(appleSecondary());error.setText("正在创建新环境…");error.setVisibility(View.VISIBLE);dialog.resize();
      EnvironmentEngine chosen=BrowserSettingsUi.creationSelection(engine);
      worker.execute(()->{EnvironmentSpec.Identity restored=null;String issue="";try{if(!active(serial))return;JSONArray rows=ProfileCatalog.get(this).list();int slot=-1;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&!row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting")){slot=row.optInt("slot",-1);break;}}if(slot<0)throw new IOException("没有可用的环境槽位；现有环境未改变");if(!active(serial))return;restored=EnvironmentConfigTransfer.restore(this,slot,config,chosen,()->active(serial)&&visible.get());}catch(Exception failure){issue="恢复结果尚未确认，现有环境未被覆盖。请先查看环境列表，再决定是否重试。";}
        EnvironmentSpec.Identity completed=restored;String problem=issue;runOnUiThread(()->{if(!active(serial))return;busy=false;if(completed==null){if(dialog.isShowing()){dialog.primary().setEnabled(true);error.setTextColor(appleRedText());error.setText(problem);error.setVisibility(View.VISIBLE);dialog.resize();}else message(problem);return;}dialog.dismiss();message("新环境已创建，尚未联网。请前往环境列表重新配置网络并登录。");});
      });
    });
    styleGrayButton((Button)dialog.footer.getChildAt(0));
    stylePrimary(dialog.primary());
    dialog.show();
  }
  void clearPending(){if(pending!=null){Arrays.fill(pending,(byte)0);pending=null;}}
  @Override protected void onDestroy(){owner++;clearPending();worker.shutdown();super.onDestroy();}
}
