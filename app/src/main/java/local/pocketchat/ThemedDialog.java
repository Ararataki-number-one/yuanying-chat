package local.pocketchat;
import android.app.Dialog;
import android.content.Context;
class ThemedDialog extends Dialog {
  ThemedDialog(Context c){super(c);}
  @Override public void show(){super.show();AppAppearance.shown(this);}
}
