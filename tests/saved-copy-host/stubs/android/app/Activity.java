package android.app;
import android.content.*;import java.io.File;import java.util.*;
/** Only the document-picker launch and feedback are modeled here. */
public class Activity extends Context {
  public static final int RESULT_OK=-1,RESULT_CANCELED=0;
  public final List<String> problems=new ArrayList<>();public int pickers;public boolean rejectPicker;
  public Activity(File root,ContentResolver resolver){super(root,resolver);}
  public void startActivityForResult(Intent intent,int request){if(rejectPicker)throw new IllegalStateException("No controlled picker");if(!Intent.ACTION_CREATE_DOCUMENT.equals(intent.action)||request!=85)throw new AssertionError("Unexpected Activity boundary");pickers++;}
}
