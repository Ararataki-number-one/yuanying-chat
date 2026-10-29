package local.pocketchat;

import android.app.Activity;
import android.view.*;
import android.widget.*;

/** A retryable native footer; showing it does not rebuild or scroll the file list. */
final class DownloadRefreshUi {
  final LinearLayout panel;final TextView message;
  DownloadRefreshUi(Activity activity,LinearLayout box,Runnable retry){
    panel=DesignUi.row(activity);panel.setPadding(DesignUi.dp(activity,14),DesignUi.dp(activity,4),DesignUi.dp(activity,14),DesignUi.dp(activity,4));
    message=DesignUi.text(activity,"下载信息暂时无法刷新，当前列表可能不是最新。",13,DesignUi.RED);message.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    panel.addView(message,new LinearLayout.LayoutParams(0,-2,1));Button button=DesignUi.button(activity,"重试",false,retry);panel.addView(button,new LinearLayout.LayoutParams(-2,-2));panel.setVisibility(View.GONE);
    ViewParent parent=box.getParent();
    if(parent instanceof ScrollView&&parent.getParent() instanceof LinearLayout){LinearLayout screen=(LinearLayout)parent.getParent();screen.addView(panel,screen.indexOfChild((View)parent)+1,new LinearLayout.LayoutParams(-1,-2));}
    else box.addView(panel,new LinearLayout.LayoutParams(-1,-2));
  }
  void failed(){if(panel.getVisibility()!=View.VISIBLE)panel.setVisibility(View.VISIBLE);}
  void clear(){if(panel.getVisibility()!=View.GONE)panel.setVisibility(View.GONE);}
}
