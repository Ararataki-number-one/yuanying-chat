package local.pocketchat;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import java.io.*;
public class MediaFixtureProvider extends ContentProvider {
 public boolean onCreate(){return true;}
 String name(Uri uri){return uri.getPath().endsWith(".png")?"fixture-image.png":"fixture-document.pdf";}
 public String getType(Uri uri){return uri.getPath().endsWith(".png")?"image/png":"application/pdf";}
 public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){MatrixCursor c=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});c.addRow(new Object[]{name(uri),25});return c;}
 public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(!"r".equals(mode))throw new FileNotFoundException();try{File file=new File(getContext().getCacheDir(),name(uri));try(FileOutputStream out=new FileOutputStream(file)){if(uri.getPath().endsWith(".png")){android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(256,256,android.graphics.Bitmap.Config.ARGB_8888);bitmap.eraseColor(0xff7db5d9);bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);bitmap.recycle();}else{android.graphics.pdf.PdfDocument doc=new android.graphics.pdf.PdfDocument();for(int i=1;i<=2;i++){android.graphics.pdf.PdfDocument.Page p=doc.startPage(new android.graphics.pdf.PdfDocument.PageInfo.Builder(360,480,i).create());android.graphics.Paint paint=new android.graphics.Paint();paint.setTextSize(24);p.getCanvas().drawText("Preview fixture page "+i,30,80,paint);doc.finishPage(p);}doc.writeTo(out);doc.close();}}return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);}catch(Exception e){throw new FileNotFoundException();}}
 public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}public int update(Uri u,ContentValues v,String s,String[] a){return 0;}public int delete(Uri u,String s,String[] a){return 0;}
}
