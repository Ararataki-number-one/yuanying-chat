package android.content;
import android.net.Uri;import android.os.ParcelFileDescriptor;import java.io.*;
public class ContentResolver{public int opens;public Thread openedOn;public Runnable duringOpen;public ParcelFileDescriptor openFileDescriptor(Uri uri,String mode)throws IOException{opens++;openedOn=Thread.currentThread();if(duringOpen!=null)duringOpen.run();if(uri.toString().contains("missing"))throw new FileNotFoundException("missing");return new ParcelFileDescriptor();}}
