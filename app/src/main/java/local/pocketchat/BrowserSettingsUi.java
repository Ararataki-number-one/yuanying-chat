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
    start.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"Gecko 指纹浏览器 · ChatGPT 增强","Chromium 指纹浏览器"}));start.setSelection(BrowserPreferences.startBrowser(activity)?1:0);form.addView(start,new LinearLayout.LayoutParams(-1,-2));
    EditText home=DesignUi.input(form,"两个内核的默认网站",BrowserPreferences.home(activity),BrowserPreferences.DEFAULT_URL);
    home.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);home.setSingleLine(true);home.setImeOptions(EditorInfo.IME_ACTION_DONE);home.setFilters(new InputFilter[]{new InputFilter.LengthFilter(8192)});
    DesignUi.action(form,"恢复默认网站为 ChatGPT",false,()->home.setText(BrowserPreferences.DEFAULT_URL));
    dialog.note("默认仍为 Gecko，网站仍为 ChatGPT。两个内核都能在地址栏切换网站，也都使用这里设置的首页；已打开的网页保持原位置。");
    dialog.note("两个内核分别保存登录、Cookie 和指纹配置。Gecko 保留原生隐私模板；Chromium 的 UA、UA-CH 与文档指纹保护在其指纹设置中单独管理。ChatGPT 的草稿救援和回复检测仅在 ChatGPT 网页启用。");
    dialog.note("两核保护范围不同，请分别查看设置和自检。Chromium 的页面 WebRTC 限制不覆盖 Worker；HTTP 代理也不能代替设备 VPN。");
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
