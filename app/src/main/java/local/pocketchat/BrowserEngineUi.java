package local.pocketchat;

import android.app.AlertDialog;

/** Explicit fallback preserves the original WebView's on-device login data. */
final class BrowserEngineUi {
  static void show(MainActivity activity){
    if(!(activity.remote instanceof GeckoWebView))return;
    GeckoWebView web=(GeckoWebView)activity.remote;
    new AlertDialog.Builder(activity).setTitle("浏览器内核")
      .setSingleChoiceItems(new String[]{"Firefox 新内核","系统内核 · 保留原登录"},web.enabled?0:1,(dialog,index)->{
        boolean next=index==0;if(next==web.enabled){dialog.dismiss();return;}
        if(EnvironmentEditorUi.browserBusy(activity.session)){activity.status("先完成当前提问或附件操作，再切换内核");return;}
        dialog.dismiss();
        new AlertDialog.Builder(activity).setTitle("切换浏览器内核？")
          .setMessage("将重新加载当前网页。两种内核分别保存登录，原登录数据会保留；首次使用新内核需要重新登录。环境和网络配置保持。").setNegativeButton("取消",null)
          .setPositiveButton("切换并加载",(d,w)->{
            if(EnvironmentEditorUi.browserBusy(activity.session)){activity.status("当前操作未完成，暂未切换");return;}
            activity.session.guard.setBlocked(true);web.useEngine(next);activity.session.webObserver.install();activity.session.applyBrowserSettings(true);
          }).show();
      }).setNegativeButton("关闭",null).show();
  }
}
