package android.app;
import android.content.Context;import android.content.DialogInterface;
/** Explicit Android choice adapter: records options, never chooses one automatically. */
public class AlertDialog implements DialogInterface {
 public static class Builder {
  public static String[] names;static DialogInterface.OnClickListener listener;
  public Builder(Context context){}public Builder setTitle(String value){return this;}
  public Builder setItems(String[] value,DialogInterface.OnClickListener callback){names=value.clone();listener=callback;return this;}
  public Builder setNegativeButton(String value,DialogInterface.OnClickListener callback){return this;}
  public AlertDialog show(){return new AlertDialog();}
  public static void reset(){names=null;listener=null;}public static void pick(int which){if(listener==null)throw new AssertionError("No entry choice");listener.onClick(new AlertDialog(),which);}
 }
}
