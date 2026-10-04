package local.pocketchat;

import android.content.Context;
import android.widget.*;

/** One compact control shared by all environment creation and editing entries. */
final class BrowserDisplayUi {
  static Spinner add(LinearLayout parent,boolean desktop){
    Context c=parent.getContext();DesignUi.section(parent,"网页显示方式","");
    Spinner choice=new Spinner(c);choice.setMinimumHeight(DesignUi.dp(c,48));
    choice.setAdapter(DesignUi.spinnerAdapter(c,new String[]{BrowserDisplay.label(false),BrowserDisplay.label(true)}));
    choice.setSelection(desktop?1:0);choice.setContentDescription("网页显示方式");parent.addView(choice);return choice;
  }
}
