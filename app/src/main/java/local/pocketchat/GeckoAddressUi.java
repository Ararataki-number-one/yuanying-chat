package local.pocketchat;

import android.app.AlertDialog;
import android.text.InputType;
import android.text.TextUtils;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.*;

/** Native address controls; never inspect or modify the website's inputs. */
final class GeckoAddressUi {
  final MainActivity a;final LinearLayout row;final Button address,home;
  private AlertDialog dialog;private String shown="";
  GeckoAddressUi(MainActivity activity){
    a=activity;row=DesignUi.row(a);row.setVisibility(View.GONE);row.setPadding(a.dp(10),a.dp(2),a.dp(10),a.dp(4));
    address=DesignUi.button(a,"网址或搜索",false,()->show(a));address.setAllCaps(false);address.setTextSize(13);address.setSingleLine(true);address.setEllipsize(TextUtils.TruncateAt.MIDDLE);address.setGravity(android.view.Gravity.CENTER_VERTICAL);address.setPadding(a.dp(12),a.dp(8),a.dp(12),a.dp(8));
    home=DesignUi.button(a,"主页",false,()->home(a));home.setTextSize(12);home.setSingleLine(true);home.setMinWidth(a.dp(56));home.setMinimumWidth(a.dp(56));home.setPadding(a.dp(6),a.dp(8),a.dp(6),a.dp(8));home.setContentDescription("打开 Gecko 指纹浏览器主页");
    row.addView(address,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(-2,-2);hp.leftMargin=a.dp(6);row.addView(home,hp);refresh();
  }
  String target(){if(a.session==null)return "";String url=a.session.navigating?a.session.navigationTarget:a.session.web.getUrl();return url==null?"":url;}
  String current(){String url=target();return url.isEmpty()?(a.session==null?BrowserPreferences.home(a):a.session.resumeUrl()):url;}
  static boolean visibleFor(String url){return GeckoNavigationPolicy.publicWeb(url)&&!MainActivity.chatUrl(url);}
  void refresh(){String url=target();int visibility=visibleFor(url)?View.VISIBLE:View.GONE;if(row.getVisibility()!=visibility)row.setVisibility(visibility);if(visibility==View.GONE)return;String text=(url.startsWith("http:")?"HTTP 未加密 · ":"")+url;if(!shown.equals(text)){shown=text;address.setText(text);address.setContentDescription("Gecko 指纹浏览器，当前网址 "+text+"，点击输入网址或搜索");}}
  static boolean available(MainActivity a){return a!=null&&!a.destroyed&&!a.isFinishing()&&a.session!=null&&a.remote!=null;}
  static void show(MainActivity a){
    if(!available(a))return;GeckoAddressUi owner=a.geckoAddress;if(owner==null)return;if(owner.dialog!=null&&owner.dialog.isShowing()){owner.dialog.getWindow().getDecorView().requestFocus();return;}
    LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(12));
    DesignUi.note(box,"Gecko 指纹浏览器 · 当前环境的原生指纹、登录数据和线路继续生效。其他网站不使用 ChatGPT 辅助脚本。");
    EditText input=DesignUi.input(box,"网址或搜索",owner.current(),"输入公共网址或搜索内容");input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);input.setSingleLine(true);input.setImeOptions(EditorInfo.IME_ACTION_GO);input.selectAll();
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("Gecko 指纹浏览器").setView(box).setPositiveButton("打开",null).setNeutralButton("主页",null).setNegativeButton("取消",null).create();owner.dialog=dialog;
    Runnable submit=()->{if(!available(a))return;try{String raw=input.getText().toString();String url=raw.trim().isEmpty()?BrowserPreferences.home(a):GeckoNavigationPolicy.normalizeInput(raw);long before=a.session.navigationEpoch;a.session.browse(url,"正在打开网页…");if(a.session.navigationEpoch!=before&&a.session.navigating&&url.equals(a.session.navigationTarget)){dialog.dismiss();a.showPage(true);owner.refresh();}else notice.setText(a.session.status);}catch(IllegalArgumentException invalid){notice.setText(invalid.getMessage());input.setError(invalid.getMessage());}};
    dialog.setOnDismissListener(ignored->{if(owner.dialog==dialog)owner.dialog=null;});dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->submit.run());dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{input.setText(BrowserPreferences.home(a));submit.run();});
    input.setOnEditorActionListener((v,action,event)->{if(action==EditorInfo.IME_ACTION_GO||event!=null&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER&&event.getAction()==KeyEvent.ACTION_DOWN){submit.run();return true;}return false;});
  }
  static void home(MainActivity a){if(!available(a))return;a.session.browse(BrowserPreferences.home(a),"正在打开主页…");a.showPage(true);if(a.geckoAddress!=null)a.geckoAddress.refresh();}
  static boolean closeBlocked(MainActivity a){return a.session.pending!=null||a.session.submitting||a.session.operation||a.session.resourceChoosers>0||a.session.resourceFilePreparations>0||a.session.transferActive;}
  static void closeSites(MainActivity a){
    if(!available(a))return;
    if(closeBlocked(a)){a.status("请先完成回复或暂停文件操作，再关闭网站");return;}
    AppAppearance.dialog(a).setTitle("关闭网站并返回 ChatGPT？").setMessage("将关闭此环境 Gecko 中的全部网页和弹出页，未保存的网页输入或上传可能丢失。登录数据和指纹设置会保留，等待中的线路配置可以继续应用。").setNegativeButton("保留网页",null).setPositiveButton("关闭网站",(d,w)->{
      long epoch=a.session.navigationEpoch;Object surface=a.remote.current;
      a.session.pageMemory.capture(()->{if(!available(a)||a.session.navigationEpoch!=epoch||a.remote.current!=surface)return;if(closeBlocked(a)){a.status("网页任务已变化，请完成或暂停后再关闭网站");return;}a.remote.closeWebsitePages();a.session.browse(MainActivity.ORIGIN,"正在返回 ChatGPT…");a.showPage(true);if(a.geckoAddress!=null)a.geckoAddress.refresh();});
    }).show();
  }
  void close(){if(dialog!=null)dialog.dismiss();dialog=null;}
}
