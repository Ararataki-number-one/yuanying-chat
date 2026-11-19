package local.pocketchat;

import android.app.Activity;
import android.text.InputFilter;
import android.text.InputType;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.*;

/** A small environment-scoped form, usable before either browser is initialized. */
final class BrowserSettingsUi {
  private BrowserSettingsUi() {}
  static void show(Activity activity){show(activity,()->{});}
  static void show(Activity activity,Runnable refresh){
    if(activity.isFinishing()||activity.isDestroyed())return;
    final EnvironmentSpec.Identity expected;
    try{expected=ProfileCatalog.get(activity).identity(Profiles.slot(activity));}
    catch(Exception unavailable){DesignUi.message(activity,"浏览器与启动","此环境暂不可用，请返回环境管理后重试。");return;}
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"此环境的浏览器与启动");
    dialog.note(Profiles.display(activity,expected.slot));
    LinearLayout form=DesignUi.column(activity);dialog.body.addView(form);
    DesignUi.note(form,"浏览器内核");
    Spinner start=new Spinner(activity);start.setContentDescription("此环境的浏览器内核");start.setMinimumHeight(DesignUi.dp(activity,48));
    start.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"Gecko 浏览器","Chromium 浏览器"}));start.setSelection(BrowserPreferences.startBrowser(activity)?1:0);form.addView(start,new LinearLayout.LayoutParams(-1,-2));
    EditText home=DesignUi.input(form,"两个内核的默认网站",BrowserPreferences.home(activity),BrowserPreferences.DEFAULT_URL);
    home.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);home.setSingleLine(true);home.setImeOptions(EditorInfo.IME_ACTION_DONE);home.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8192)});
    DesignUi.action(form,"恢复默认网站为 ChatGPT",false,()->home.setText(BrowserPreferences.DEFAULT_URL));
    dialog.note("此环境打开网页时使用所选内核。初始选择为 Gecko，首页为 ChatGPT。切换内核前请保存未提交的网页内容，并在保存设置后重新打开此环境。");
    boolean managedChromium=ChromiumEntry.managed(activity);
    if(managedChromium){
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
        boolean changing=chromium!=BrowserPreferences.startBrowser(activity);
        boolean needsModule=managedChromium&&chromium&&!ChromiumModuleInstaller.installed(activity);
        if((changing||needsModule)&&browserWorkPending(activity)){
          problem.setText("请完成当前网页或文件操作，再保存新的内核选择。");problem.setVisibility(View.VISIBLE);return;
        }
        if(managedChromium&&chromium){
          String issue=ChromiumEntry.networkIssue(activity);
          if(!issue.isEmpty()){problem.setText(issue);problem.setVisibility(View.VISIBLE);return;}
        }
        if(needsModule){
          ChromiumModuleInstaller.show(activity,expected.slot);
          return;
        }
        boolean saved=ProfileCatalog.get(activity).withIdentity(expected,()->BrowserPreferences.save(activity,chromium,address));
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
