package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.text.InputFilter;
import android.text.InputType;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.*;

/** A small environment-scoped form, usable before either browser is initialized. */
final class BrowserSettingsUi {
  private static final String OWNER_SLOT="browserSettingsOwnerSlot";
  private static final String OWNER_GENERATION="browserSettingsOwnerGeneration";
  private static final String OWNER_ID="browserSettingsOwnerId";
  private static final String OPEN_DIALOG="openBrowserSettingsDialog";

  private BrowserSettingsUi() {}

  static EnvironmentSpec.Identity workspaceIdentity(Activity activity){
    try{
      int slot=activity instanceof MainActivity?Profiles.slot(activity):AppSettings.recentSlot(activity);
      return ProfileCatalog.get(activity).identity(slot);
    }catch(Exception unavailable){return null;}
  }

  static void openWorkspace(Activity activity,EnvironmentSpec.Identity expected,Runnable refresh){
    if(activity.isFinishing()||activity.isDestroyed())return;
    if(expected!=null&&expected.slot==Profiles.slot(activity)){
      Intent origin=activity.getIntent();
      boolean fromStandalone=ownerOpening(activity,origin);
      if(fromStandalone&&!expected.equals(ownerIdentity(activity,origin))){unavailable(activity);return;}
      show(activity,expected,refresh);
      return;
    }
    if(!current(activity,expected)){unavailable(activity);return;}
    activity.startActivity(ownerIntent(activity,expected));
  }

  private static Intent ownerIntent(Activity activity,EnvironmentSpec.Identity expected){
    return new Intent(activity,Profiles.activity(expected.slot)).putExtra("openWindowAction","settings")
      .putExtra(OWNER_SLOT,expected.slot).putExtra(OWNER_GENERATION,expected.generation).putExtra(OWNER_ID,expected.environmentId)
      .putExtra(OPEN_DIALOG,true)
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
  }

  static boolean ownerOpening(Activity activity,Intent intent){
    if(intent==null||Intent.ACTION_VIEW.equals(intent.getAction())||!"settings".equals(intent.getStringExtra("openWindowAction")))return false;
    int slot=intent.getIntExtra(OWNER_SLOT,-1);
    return slot>0&&slot==Profiles.slot(activity);
  }

  private static EnvironmentSpec.Identity ownerIdentity(Activity activity,Intent intent){
    int slot=intent.getIntExtra(OWNER_SLOT,-1),generation=intent.getIntExtra(OWNER_GENERATION,-1);
    String environmentId=intent.getStringExtra(OWNER_ID);
    if(slot!=Profiles.slot(activity))return null;
    try{return new EnvironmentSpec.Identity(slot,generation,environmentId);}
    catch(RuntimeException unavailable){return null;}
  }

  static void showRequestedOwner(MainActivity activity,Intent intent){
    if(!ownerOpening(activity,intent)||!intent.getBooleanExtra(OPEN_DIALOG,false))return;
    // Keep the native route in the Intent for Activity recreation. The modal
    // itself opens once per request, with the original slot and generation.
    intent.removeExtra(OPEN_DIALOG);
    EnvironmentSpec.Identity expected=ownerIdentity(activity,intent);
    show(activity,expected,()->activity.hub.settings());
  }

  private static boolean current(Activity activity,EnvironmentSpec.Identity expected){
    if(expected==null)return false;
    try{return expected.equals(ProfileCatalog.get(activity).identity(expected.slot));}
    catch(Exception unavailable){return false;}
  }

  private static void unavailable(Activity activity){
    DesignUi.message(activity,"浏览器与启动","此环境暂不可用，请返回环境管理后重试。");
  }

  static void show(Activity activity){show(activity,()->{});}
  static void show(Activity activity,Runnable refresh){
    if(activity.isFinishing()||activity.isDestroyed())return;
    final EnvironmentSpec.Identity expected;
    try{expected=ProfileCatalog.get(activity).identity(Profiles.slot(activity));}
    catch(Exception failure){unavailable(activity);return;}
    show(activity,expected,refresh);
  }

  static Spinner creationPicker(Activity activity,LinearLayout form,EnvironmentEngine initial){
    DesignUi.note(form,"浏览器内核 · 仅创建时可选");
    Spinner picker=new Spinner(activity);
    picker.setContentDescription("新环境的浏览器内核");
    picker.setMinimumHeight(DesignUi.dp(activity,48));
    boolean available=ChromiumModuleInstaller.selectableForNewEnvironment(activity);
    picker.setAdapter(DesignUi.spinnerAdapter(activity,available
      ?new String[]{EnvironmentEngine.GECKO.label,EnvironmentEngine.CHROMIUM.label}
      :new String[]{EnvironmentEngine.GECKO.label}));
    picker.setSelection(available&&initial==EnvironmentEngine.CHROMIUM?1:0);
    form.addView(picker,new LinearLayout.LayoutParams(-1,-2));
    if(!available)DesignUi.note(form,"此设备或当前安装不提供独立 Chromium，新环境可使用 Firefox（Gecko）。");
    return picker;
  }

  static EnvironmentEngine creationSelection(Spinner picker){
    return picker.getSelectedItemPosition()==1?EnvironmentEngine.CHROMIUM:EnvironmentEngine.GECKO;
  }

  private static void show(Activity activity,EnvironmentSpec.Identity expected,Runnable refresh){
    if(activity.isFinishing()||activity.isDestroyed())return;
    if(!current(activity,expected)||expected.slot!=Profiles.slot(activity)){unavailable(activity);return;}
    Context profile=Profiles.context(activity,expected.slot);
    EnvironmentEngine engine=BrowserPreferences.engine(profile);
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"此环境的浏览器与启动");
    dialog.note(Profiles.display(activity,expected.slot));
    LinearLayout form=DesignUi.column(activity);dialog.body.addView(form);
    DesignUi.field(form,"已绑定浏览器内核",engine.label);
    dialog.note("内核只在创建时选择。修改首页不会更换内核或影响登录。");
    EditText home=DesignUi.input(form,"默认网站",BrowserPreferences.home(profile),BrowserPreferences.DEFAULT_URL);
    home.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);home.setSingleLine(true);
    home.setImeOptions(EditorInfo.IME_ACTION_DONE);home.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8192)});
    DesignUi.action(form,"恢复默认网站为 ChatGPT",false,()->home.setText(BrowserPreferences.DEFAULT_URL));
    if(engine==EnvironmentEngine.CHROMIUM&&!ChromiumModuleInstaller.installed(activity)){
      if(ChromiumModuleInstaller.available(activity)){
        DesignUi.action(form,"安装 Chromium 组件",false,()->{
          if(!current(activity,expected)){unavailable(activity);return;}
          if(browserWorkPending(activity)){DesignUi.message(activity,"Chromium 组件","请完成当前网页或文件操作后再安装。");return;}
          String issue=ChromiumEntry.networkIssue(profile);
          if(!issue.isEmpty()){DesignUi.message(activity,"Chromium 组件",issue);return;}
          dialog.dismiss();ChromiumModuleInstaller.show(activity,expected);
        });
      }else DesignUi.note(form,"当前安装不提供此 Chromium 组件。原有内核绑定不会改变。");
    }
    TextView problem=DesignUi.text(activity,"",13,DesignUi.RED);problem.setVisibility(View.GONE);
    problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);form.addView(problem);
    dialog.buttons("取消",dialog::dismiss,"保存",()->{
      if(activity.isFinishing()||activity.isDestroyed())return;
      final String address;
      try{address=BrowserPreferences.normalizeHome(home.getText().toString());}
      catch(IllegalArgumentException invalid){home.setError(invalid.getMessage());home.requestFocus();return;}
      try{
        boolean saved=ProfileCatalog.get(activity).withIdentity(expected,()->BrowserPreferences.saveHome(profile,address));
        if(!saved){problem.setText("偏好暂时无法保存，请重试。");problem.setVisibility(View.VISIBLE);return;}
        dialog.dismiss();refresh.run();
      }catch(Exception changed){problem.setText("环境已变化或暂时无法保存，请重新打开浏览器设置。");problem.setVisibility(View.VISIBLE);}
    });
    dialog.show();
  }
  static boolean browserWorkPending(Activity activity){
    ChatSession session=ChatSession.peek();
    MainActivity main=activity instanceof MainActivity?(MainActivity)activity:null;
    ChromiumRuntime chromium=ChromiumRuntime.owner;
    return session!=null&&!session.deleted&&(ProfileUi.working(session)||session.currentReplyActive())
      ||main!=null&&(main.geckoWorkPending()||main.nativeFileWorkPending())
      ||chromium!=null&&!chromium.closed&&chromium.activity instanceof BrowserActivity
        &&((BrowserActivity)chromium.activity).fileOperationPending()
      ||ChromiumRouteLease.snapshot().downloads>0;
  }
}
