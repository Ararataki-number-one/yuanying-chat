package local.pocketchat;

import android.widget.Button;
import java.util.List;

/** Lists only this environment's retained Gecko pages, never fabricated tabs. */
final class GeckoWindowsUi {
  private GeckoWindowsUi() {}
  static void show(MainActivity activity){
    if(!GeckoAddressUi.available(activity))return;
    GeckoWebView owner=activity.remote;
    List<GeckoWebView.BrowserWindow> windows=owner.browserWindows();
    ReferenceUi.Modal panel=new ReferenceUi.Modal(activity,"网页窗口").asSheet();
    panel.note(Profiles.display(activity,Profiles.slot(activity))+" · 当前环境已打开的网页");
    if(windows.isEmpty())panel.note("网页尚未就绪，打开后会显示在这里。");
    for(GeckoWebView.BrowserWindow window:windows){
      String title=window.primary?"主页面":"弹出网页";
      String address=window.url.isEmpty()?"空白网页":window.url;
      String label=title+(window.selected?" · 当前":"")+"\n"+address;
      Button button=ReferenceUi.menuAction(panel,label,()->{
        panel.dismiss();
        if(!GeckoAddressUi.available(activity)||activity.remote!=owner||!owner.selectBrowserWindow(window,activity)){
          if(!activity.destroyed&&!activity.isFinishing())activity.status("网页窗口已变化，请重新选择");
        }else if(activity.geckoAddress!=null)activity.geckoAddress.refresh();
      });
      button.setSelected(window.selected);button.setContentDescription("网页窗口："+label);
    }
    if(owner.hasWebsitePages())ReferenceUi.menuAction(panel,"关闭网站并返回 ChatGPT",()->{panel.dismiss();GeckoAddressUi.closeSites(activity);});
    panel.buttons("返回",panel::dismiss,"",()->{});panel.show();
  }
}
