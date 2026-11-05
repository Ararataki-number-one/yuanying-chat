package local.pocketchat;

import android.app.Activity;
import android.widget.*;
import org.json.*;

/** Edits one captured Chromium policy. The surface owner performs all I/O and
 * rejects stale revisions; this dialog never touches Gecko's applied state. */
final class ChromiumFingerprintUi {
  interface Callback {
    void save(JSONObject specification,boolean rotateSeed);
    void observe();
  }
  private ChromiumFingerprintUi() {}

  static void show(Activity activity,ChromiumFingerprintStore.State current,JSONObject receipt,boolean observing,Callback callback){
    if(activity.isFinishing()||activity.isDestroyed())return;
    final ChromiumFingerprintSpec selected;
    try{selected=ChromiumFingerprintSpec.from(current.spec());}
    catch(Exception unavailable){DesignUi.message(activity,"Chromium 指纹设置","配置暂时无法读取，原配置已保留。");return;}
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(activity,"Chromium 指纹设置");
    LinearLayout form=dialog.body;
    dialog.note(Profiles.display(activity,current.identity.slot)+" · 配置版本 "+current.revision);
    dialog.note(summary(receipt));
    DesignUi.note(form,"网页显示");
    Spinner display=new Spinner(activity);display.setContentDescription("Chromium 网页显示模式");
    display.setMinimumHeight(DesignUi.dp(activity,48));
    display.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"手机版","电脑版"}));
    display.setSelection(selected.desktop()?1:0);form.addView(display);
    DesignUi.note(form,"兼容模式");
    Spinner protection=new Spinner(activity);protection.setContentDescription("Chromium 指纹保护模式");
    protection.setMinimumHeight(DesignUi.dp(activity,48));
    protection.setAdapter(DesignUi.spinnerAdapter(activity,new String[]{"保护模式 · 需要内核支持","兼容模式 · 允许较旧内核"}));
    protection.setSelection(selected.protectedMode()?0:1);form.addView(protection);
    CheckBox canvas=option(activity,form,"Canvas 图像读出保护",selected.canvas);
    CheckBox webgl=option(activity,form,"限制 WebGL 调试显卡标识",selected.webgl);
    CheckBox audio=option(activity,form,"音频复制读出保护",selected.audio);
    CheckBox webrtc=option(activity,form,"限制页面创建 WebRTC 连接",selected.webrtc);
    dialog.note("同一环境、同一网站使用稳定的保护种子；不同环境分别保存。网页显示会同时调整原生 UA 与 UA-CH，不修改设备实际系统。");
    dialog.note("保护在新文档开始时注入，覆盖支持的页面与框架。Worker、Service Worker、OffscreenCanvas、独立时区、字体与硬件伪装未覆盖；音频实时缓冲和 WebGL 像素读出保持原样。兼容模式的未覆盖项请查看确认结果。");
    android.view.View observe=DesignUi.button(activity,observing?"当前页面正在自检…":"自检当前页面",false,()->{
      if(observing)return;
      dialog.dismiss();callback.observe();
    });observe.setEnabled(!observing);form.addView(observe);
    DesignUi.action(form,"保护范围与确认状态",false,()->DesignUi.message(activity,"Chromium 保护范围",details(receipt)));
    DesignUi.action(form,"更换此环境的保护种子…",false,()->confirm(activity,dialog,
        "更换保护种子？","此环境所有 Chromium 标签页将重新加载，未提交的网页内容可能丢失。新的种子会改变后续网页的保护输出；登录数据会保留。",()->callback.save(current.spec(),true)));
    dialog.buttons("关闭",dialog::dismiss,"保存并重新加载",()->{
      JSONObject specification=J.obj("schema",1,"engine","chromium","display",display.getSelectedItemPosition()==1?"desktop":"mobile",
          "protection",protection.getSelectedItemPosition()==0?"protected":"compatibility",
          "canvas",canvas.isChecked(),"webgl",webgl.isChecked(),"audio",audio.isChecked(),"webrtc",webrtc.isChecked());
      try{ChromiumFingerprintSpec.from(specification);}
      catch(Exception invalid){DesignUi.message(activity,"配置无法保存","请选择有效的 Chromium 指纹配置。");return;}
      confirm(activity,dialog,"应用指纹设置？","此环境所有 Chromium 标签页将重新加载，未提交的网页内容可能丢失。",()->callback.save(specification,false));
    });
    dialog.show();
  }

  private static CheckBox option(Activity activity,LinearLayout form,String title,boolean checked){
    CheckBox value=new CheckBox(activity);value.setText(title);value.setChecked(checked);
    value.setMinimumHeight(DesignUi.dp(activity,48));form.addView(value);return value;
  }
  private static void confirm(Activity activity,ReferenceUi.Modal owner,String title,String message,Runnable accepted){
    if(activity.isFinishing()||activity.isDestroyed()||!owner.isShowing())return;
    AppAppearance.dialog(activity).setTitle(title).setMessage(message).setNegativeButton("取消",null)
        .setPositiveButton("重新加载",(dialog,which)->{if(activity.isFinishing()||activity.isDestroyed()||!owner.isShowing())return;owner.dismiss();accepted.run();}).show();
  }
  static String summary(JSONObject receipt){
    JSONObject fields=fields(receipt);int nativeCount=0,pageCount=0,requested=0,failed=0;
    java.util.Iterator<String> names=fields.keys();while(names.hasNext()){
      JSONObject row=fields.optJSONObject(names.next());if(row==null)continue;
      String state=row.optString("state");if("native-readback".equals(state))nativeCount++;
      else if("page-observed".equals(state))pageCount++;else if("requested".equals(state))requested++;else if("failed".equals(state))failed++;
    }
    if(fields.length()==0)return "配置已保存；尚无当前页面的确认记录。";
    return "原生设置回读 "+nativeCount+" 项 · 页面观测 "+pageCount+" 项"+(requested>0?" · 待观测 "+requested+" 项":"")+(failed>0?" · 失败 "+failed+" 项":"")+"。确认结果只对应当前页面及本次运行。";
  }
  private static JSONObject fields(JSONObject receipt){
    if(receipt==null)return new JSONObject();JSONObject fields=receipt.optJSONObject("fields");return fields==null?receipt:fields;
  }
  private static String details(JSONObject receipt){
    return summary(receipt)+"\n\n原生 UA 与 UA-CH：由当前 WebView 提供者设置并回读，是否支持以运行时结果为准。"+
        "\nCanvas：页面中的二维图像读出和导出保护。WebGL：限制调试显卡标识，不保护 readPixels。音频：保护 copyFromChannel 复制读出，不改变实时缓冲和播放。WebRTC：限制页面连接构造器，不覆盖 Worker。"+
        "\n\nWorker、Service Worker、OffscreenCanvas、AudioWorklet、字体、硬件、独立时区、系统语言、TLS 与 HTTP/2 指纹未覆盖。电脑版不会把 Android 内核变成桌面操作系统。"+
        "\n\n页面自检只观察当前页面能读到的结果，不能证明服务端请求、所有框架或完整指纹均受到保护。其他网站的脚本也可能修改页面环境。Gecko 原生模板及其自检独立管理。";
  }
}
