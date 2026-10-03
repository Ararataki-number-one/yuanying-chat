package local.pocketchat;

import android.view.Gravity;
import android.widget.*;

final class BrowserReadingUi {
  static void show(MainActivity a){BrowserReading reading=a.session.reading;ReferenceUi.Modal d=new ReferenceUi.Modal(a,"网页缩放");
    d.note(Profiles.display(a,Profiles.slot(a))+" · 电脑版");LinearLayout row=DesignUi.row(a);TextView amount=ReferenceUi.text(a,"",22,ReferenceUi.TEXT,true);amount.setGravity(Gravity.CENTER);
    Runnable refresh=()->amount.setText(Math.round(reading.choice()*100)+"%");
    Button minus=ReferenceUi.button(a,"−",false,()->{reading.choose(reading.choice()-.1f);refresh.run();});minus.setContentDescription("缩小网页");row.addView(minus,new LinearLayout.LayoutParams(a.dp(56),a.dp(48)));
    row.addView(amount,new LinearLayout.LayoutParams(0,a.dp(48),1));Button plus=ReferenceUi.button(a,"+",false,()->{reading.choose(reading.choice()+.1f);refresh.run();});plus.setContentDescription("放大网页");row.addView(plus,new LinearLayout.LayoutParams(a.dp(56),a.dp(48)));d.body.addView(row);refresh.run();
    d.note("100% 按手机宽度正常显示。双指缩放会记住，放大后可左右移动。\n只影响当前环境，不会重新加载网页。");
    d.buttons("适应屏幕",()->{reading.choose(1);refresh.run();},"完成",d::dismiss);d.show();
  }
}
