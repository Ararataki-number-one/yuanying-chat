package local.pocketchat;

import android.content.Context;
import android.text.TextUtils;
import android.widget.Button;

/** Native browser actions share the existing glass material and press feedback. */
final class BrowserToolbarUi {
  private BrowserToolbarUi() {}

  static Button action(Context context,String glyph,String label,Runnable run){
    Button button=ReferenceUi.iconButton(context,glyph,label,run);
    button.setBackground(DesignUi.glass(context,24));
    GlassMotion.press(button,false);
    return button;
  }

  static void action(Button button,String glyph,String label){
    if(button instanceof Ui.IconButton){
      Ui.Icon icon=((Ui.IconButton)button).icon;
      if(!glyph.equals(icon.name)){icon.name=glyph;button.invalidate();}
    }
    if(!TextUtils.equals(button.getContentDescription(),label)){
      button.setContentDescription(label);button.setTooltipText(label);
    }
  }

  static void enabled(Button button,boolean enabled){
    if(button.isEnabled()!=enabled)button.setEnabled(enabled);
  }
}
