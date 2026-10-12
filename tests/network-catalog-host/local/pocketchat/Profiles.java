package local.pocketchat;
import android.content.Context;
final class Profiles {
  static Context context(Context c,int slot){return new Context(c.root,slot);}
  static int slot(Context c){return c.slot;}
}
