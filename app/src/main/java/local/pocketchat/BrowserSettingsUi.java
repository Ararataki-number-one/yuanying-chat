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
      show(activity,expected,refresh,fromStandalone);
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
    show(activity,expected,()->activity.hub.settings(),true);
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
    show(activity,expected,refresh,false);
  }

  private static void show(Activity activity,EnvironmentSpec.Identity expected,Runnable refresh,boolean fromStandalone){
    if(activity.isFinishing()||activity.isDestroyed())return;
    if(!current(activity,expected)||expected.slot!=Profiles.slot(activity)){unavailable(activity);return;}
    Context profile=Profiles.context(activity,expected.slot);
    boolean initialChromium=BrowserPreferences.startBrowser(profile);
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"此环境的浏览器与启动");
    dialog.note(Profiles.display(activity,expected.slot));
    LinearLayout form=DesignUi.column(activity);dialog.body.addView(form);
    DesignUi.note(form,"浏览器内核");
    Spinner start=new Spinner(activity);start.setContentDescription("此环境的浏览器内核");start.setMinimumHeight(DesignUi.dp(activity,48));
    start.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"Gecko 浏览器","Chromium 浏览器"}));start.setSelection(initialChromium?1:0);form.addView(start,new LinearLayout.LayoutParams(-1,-2));
    EditText home=DesignUi.input(form,"两个内核的默认网站",BrowserPreferences.home(profile),BrowserPreferences.DEFAULT_URL);
    home.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);home.setSingleLine(true);home.setImeOptions(EditorInfo.IME_ACTION_DONE);home.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8192)});
    DesignUi.action(form,"恢复默认网站为 ChatGPT",false,()->home.setText(BrowserPreferences.DEFAULT_URL));
    dialog.note("此环境打开网页时使用所选内核。初始选择为 Gecko，首页为 ChatGPT。切换内核前请保存未提交的网页内容，并在保存设置后重新打开此环境。");
    boolean managedChromium=ChromiumEntry.managed(activity);
    if(fromStandalone&&initialChromium&&managedChromium&&ChromiumModuleInstaller.installed(activity)){
      start.setEnabled(false);
      dialog.note("可保存默认网站。切换内核请从此环境的 Chromium 网页打开环境设置，以便先确认文件操作已结束。");
    }
    if(managedChromium){
      if(AppUpdates.parallelInstall(activity))
        dialog.note("独立 Chromium 仅支持同批构建的并行版组件，不能从正式版通道下载。");
      else
        dialog.note("Chromium 按需安装。安装后，各环境可选择使用此组件，登录和网站数据各自保存。");
    }else{
      dialog.note("两个内核分别保存登录、Cookie 和指纹配置。Gecko 保留原生隐私模板；Chromium 的 UA、UA-CH 与文档指纹保护在其指纹设置中单独管理。Gecko 在 ChatGPT 网页中支持草稿救援和离线会话检索。");
      dialog.note("两核保护范围不同，请分别查看设置和自检。Chromium 的页面 WebRTC 限制不覆盖 Worker；HTTP 代理也不能代替设备 VPN。");
    }
    TextView problem=DesignUi.text(activity,"",13,DesignUi.RED);problem.setVisibility(View.GONE);problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);form.addView(problem);
    dialog.buttons("取消",dialog::dismiss,"保存",()->{
      if(activity.isFinishing()||activity.isDestroyed())return;
      final String address;
      try{address=BrowserPreferences.normalizeHome(home.getText().toString());}
      catch(IllegalArgumentException invalid){home.setError(invalid.getMessage());home.requestFocus();return;}
      try{
        boolean chromium=start.getSelectedItemPosition()==1;
        boolean homepageOnly=fromStandalone&&chromium==initialChromium;
        boolean currentChromium=BrowserPreferences.startBrowser(profile);
        boolean changing=!homepageOnly&&chromium!=currentChromium;
        if(fromStandalone&&changing&&currentChromium&&managedChromium&&ChromiumModuleInstaller.installed(activity)){
          problem.setText("切换内核请从此环境的 Chromium 网页打开环境设置。");problem.setVisibility(View.VISIBLE);return;
        }
        boolean needsModule=!homepageOnly&&managedChromium&&chromium&&!ChromiumModuleInstaller.installed(activity);
        if((changing||needsModule)&&browserWorkPending(activity)){
          problem.setText("请完成当前网页或文件操作，再保存新的内核选择。");problem.setVisibility(View.VISIBLE);return;
        }
        if(!homepageOnly&&managedChromium&&chromium){
          String issue=ChromiumEntry.networkIssue(profile);
          if(!issue.isEmpty()){problem.setText(issue);problem.setVisibility(View.VISIBLE);return;}
        }
        if(needsModule){
          if(!current(activity,expected)){unavailable(activity);return;}
          if(AppUpdates.parallelInstall(activity)){
            problem.setText("并行版不能使用正式版组件下载。请安装同一并行版发布包内的 Chromium 组件。");
            problem.setVisibility(View.VISIBLE);return;
          }
          ChromiumModuleInstaller.show(activity,expected.slot);
          return;
        }
        boolean saved=ProfileCatalog.get(activity).withIdentity(expected,()->homepageOnly
          ?BrowserPreferences.saveHome(profile,address):BrowserPreferences.save(profile,chromium,address));
        if(!saved){problem.setText("偏好暂时无法保存，请重试。");problem.setVisibility(View.VISIBLE);return;}
        dialog.dismiss();refresh.run();
        if(changing)Toast.makeText(activity,"内核已保存，重新打开此环境后生效。",Toast.LENGTH_LONG).show();
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
