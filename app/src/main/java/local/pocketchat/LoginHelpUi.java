package local.pocketchat;

import android.content.*;
import android.net.Uri;
import android.widget.*;

/** A contextual explanation, never an imitation login form or a cookie-transfer promise. */
final class LoginHelpUi {
  static void maybeShow(MainActivity a){
    if(!a.active||!a.pageMode||!a.hasWindowFocus()||a.hub==null||a.hub.page!=AppHub.CHAT||!a.session.googleLoginBlocked||!LoginPagePolicy.google(a.remote.getUrl())||a.shownGoogleLoginNotice==a.session.navigationEpoch)return;
    a.shownGoogleLoginNotice=a.session.navigationEpoch;show(a);
  }
  static void show(MainActivity a){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"Google 登录遇到限制");
    d.note(GeckoWebView.active(a.remote)?"当前使用 Firefox 新内核。Google 仍可能拒绝应用内浏览器登录，先查看官方网页给出的提示。":"Google 可能拒绝应用内浏览器登录。系统内核使用 Android WebView，切换页面布局无法保证解除这个限制。");
    d.note("可返回 ChatGPT，选择这个账号已有的其他登录方式。若账号只能用 Google 登录，可先在系统浏览器中使用 ChatGPT。");
    Button browser=ReferenceUi.link(a,"在系统浏览器中使用 ChatGPT",()->{
      try{a.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(MainActivity.ORIGIN)));d.dismiss();}catch(ActivityNotFoundException|SecurityException e){a.status("系统浏览器暂时无法打开，请检查默认浏览器或手机限制");}
    });d.body.addView(browser,new LinearLayout.LayoutParams(-1,a.dp(48)));
    d.note("系统浏览器的登录不会自动同步回本应用。"+(a.session.internalNetwork()||!a.prefs.getString("proxy","").isEmpty()?"它也不使用本环境的应用专用代理，请确认手机网络可用。":""));
    d.buttons("关闭",d::dismiss,"返回 ChatGPT",()->{
      String reason=EnvironmentEditorUi.browserTaskReason(a.session);if(!reason.isEmpty()){a.status(reason);return;}
      d.dismiss();a.session.navigate(MainActivity.ORIGIN,"正在返回 ChatGPT…");a.showPage(true);
    });d.show();
  }
}
