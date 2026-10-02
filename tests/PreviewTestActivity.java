package local.pocketchat;
import android.os.*;
import android.graphics.*;
import org.json.*;
import java.io.*;
public class PreviewTestActivity extends AttachmentPreviewActivity {
 JSONArray checks=new JSONArray();boolean png;
 @Override public void onCreate(Bundle b){png=getIntent().getBooleanExtra("image",false);getIntent().putExtra("uri","content://local.pocketchat.fixturefiles/"+(png?"image.png":"document.pdf")).putExtra("name",png?"fixture-image.png":"fixture-document.pdf").putExtra("mime",png?"image/png":"application/pdf");super.onCreate(b);setRequestedOrientation(1);main.postDelayed(()->verify(),3000);}
 void check(String n,boolean ok){checks.put(J.obj("name",n,"pass",ok));}
 void verify(){check("Local attachment decoded",image.getDrawable()!=null);check("Preview has fitted scale",image.base>0);if(png){check("Image preview dimensions",image.getDrawable()!=null&&image.getDrawable().getIntrinsicWidth()==256);write();}else{check("PDF exposes all pages",total==2&&page==0&&next.isEnabled()&&!previous.isEnabled());showPage(1);main.postDelayed(()->{check("PDF next page renders",page==1&&previous.isEnabled()&&!next.isEnabled());showPage(0);main.postDelayed(()->{check("PDF previous page renders",page==0);write();},800);},1200);}}
 void write(){try{J.write(new File(getFilesDir(),png?"preview-image-results.json":"preview-pdf-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}}
}
