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
    DesignUi.note(form,"启动界面");
    Spinner start=new Spinner(activity);start.setContentDescription("此环境的默认启动界面");start.setMinimumHeight(DesignUi.dp(activity,48));
    start.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"ChatGPT 增强 · Gecko","通用浏览器 · Chromium"}));start.setSelection(BrowserPreferences.startBrowser(activity)?1:0);form.addView(start,new LinearLayout.LayoutParams(-1,-2));
    EditText home=DesignUi.input(form,"通用浏览器的默认网站",BrowserPreferences.home(activity),BrowserPreferences.DEFAULT_URL);
    home.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);home.setSingleLine(true);home.setImeOptions(EditorInfo.IME_ACTION_DONE);home.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8192)});
    DesignUi.action(form,"恢复默认网站为 ChatGPT",false,()->home.setText(BrowserPreferences.DEFAULT_URL));
    dialog.note("默认仍为 ChatGPT 增强界面。选择通用浏览器后，下次打开此环境进入 Chromium；当前网页继续保留。默认网站仅用于通用浏览器。");
    dialog.note("Chromium 使用 Android System WebView，可访问其他网站。Chromium 与 Gecko 的登录和 Cookie 分开保存；ChatGPT 增强界面的草稿救援、回复检测和环境模板不会随之迁移。");
    dialog.note("Chromium 不继承 Gecko 的 WebRTC 限制，HTTP 代理不能覆盖 WebRTC 连接。如需保护这类连接，请自行启用设备 VPN；应用不会自动开启 VPN。");
    TextView problem=DesignUi.text(activity,"",13,DesignUi.RED);problem.setVisibility(View.GONE);problem.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);form.addView(problem);
    dialog.buttons("取消",dialog::dismiss,"保存",()->{
      if(activity.isFinishing()||activity.isDestroyed())return;
      final String address;
      try{address=BrowserPreferences.normalizeHome(home.getText().toString());}
      catch(IllegalArgumentException invalid){home.setError(invalid.getMessage());home.requestFocus();return;}
      try{
        boolean saved=ProfileCatalog.get(activity).withIdentity(expected,()->BrowserPreferences.save(activity,start.getSelectedItemPosition()==1,address));
        if(!saved){problem.setText("偏好暂时无法保存，请重试。");problem.setVisibility(View.VISIBLE);return;}
        dialog.dismiss();refresh.run();
      }catch(Exception changed){problem.setText("环境已变化或暂时无法保存，请重新打开浏览器设置。");problem.setVisibility(View.VISIBLE);}
    });
    dialog.show();
  }
}
