package local.pocketchat;

import android.app.AlertDialog;
import android.content.Intent;

/** Restart only the selected environment to keep Chromium and Gecko apart. */
final class BrowserEngineUi {
  static void show(MainActivity activity){
    new AlertDialog.Builder(activity).setTitle("浏览器内核")
      .setSingleChoiceItems(new String[]{"Firefox 新内核","系统内核 · 保留原登录"},activity.remote.enabled?0:1,(dialog,index)->{
        boolean next=index==0;if(next==activity.remote.enabled){dialog.dismiss();return;}
        dialog.dismiss();switchTo(activity,next,true);
      }).setNegativeButton("关闭",null).show();
  }
  static void switchTo(MainActivity activity,boolean gecko,boolean raw){
    if(EnvironmentEditorUi.browserBusy(activity.session)){activity.status("先完成当前提问或附件操作，再切换内核");return;}
    new AlertDialog.Builder(activity).setTitle(raw?"切换浏览器内核？":"打开简洁模式？")
      .setMessage((raw?"将重新打开当前环境。":"简洁模式目前使用系统内核，将重新打开当前环境。")+"两种内核分别保存登录，原登录数据会保留；首次使用新内核需要重新登录。")
      .setNegativeButton("取消",null).setPositiveButton("继续",(d,w)->{
        if(EnvironmentEditorUi.browserBusy(activity.session)){activity.status("当前操作未完成，暂未切换");return;}
        activity.session.guard.setBlocked(true);
        activity.prefs.edit().putString("browserEngine",gecko?"gecko":"system").putBoolean("pageMode",raw).commit();
        activity.startActivity(new Intent(activity,EngineRestartActivity.class).putExtra("slot",Profiles.slot(activity)).putExtra("pid",android.os.Process.myPid()));
      }).show();
  }
}
