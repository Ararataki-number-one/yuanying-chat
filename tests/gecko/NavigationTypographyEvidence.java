package local.pocketchat;

import android.app.Activity;
import android.graphics.Rect;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.Layout;
import android.util.Log;
import android.view.View;
import android.view.ViewTreeObserver;
import android.widget.Button;
import android.widget.LinearLayout;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only observation of the actual shared navigation component.
 * This fixture is not a MainActivity screenshot or a website/network test.
 */
final class NavigationTypographyEvidence implements ViewTreeObserver.OnPreDrawListener, Runnable {
  static final String TAG="PocketNavType";
  final Activity activity;final LinearLayout root;final Button[] buttons=new Button[DesignUi.NAV.length];
  final Handler handler=new Handler(Looper.getMainLooper());final JSONObject identity;
  final String nonce;final long started=SystemClock.uptimeMillis();
  int selected=WorkspaceNavigation.NONE,observations;boolean closed,allFit=true;String previous;

  NavigationTypographyEvidence(Activity activity)throws Exception{
    this.activity=activity;nonce=activity.getIntent().getStringExtra("visualNonce");
    if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalArgumentException("Owned observation nonce required");
    identity=IntegrationBuildIdentity.read(activity);
    if(!identity.getString("sourceCommit").equals(activity.getIntent().getStringExtra("visualSourceCommit")))
      throw new IllegalArgumentException("Current clean source required");
    float expected=activity.getIntent().getFloatExtra("visualFontScale",-1f);
    if(Math.abs(activity.getResources().getConfiguration().fontScale-expected)>.001f)
      throw new IllegalStateException("Requested font configuration is not active");
    DesignUi.chrome(activity);if(Build.VERSION.SDK_INT>=30)activity.getWindow().setDecorFitsSystemWindows(false);
    root=DesignUi.column(activity);root.setBackgroundColor(ReferenceUi.CHAT_BG);
    root.addView(new View(activity),new LinearLayout.LayoutParams(-1,0,1));
    root.addView(ReferenceUi.nav(activity,selected,n->{},buttons));
    activity.setContentView(root);ReferenceUi.insets(activity,root);AppAppearance.apply(root);
    root.getViewTreeObserver().addOnPreDrawListener(this);handler.postDelayed(this,12000);
  }

  @Override public boolean onPreDraw(){
    if(closed)return true;
    try{
      if(root.isLayoutRequested()||!root.hasWindowFocus()){root.postInvalidateOnAnimation();return true;}
      JSONArray rows=new JSONArray();
      for(int i=0;i<buttons.length;i++){
        Button b=buttons[i];Layout layout=b.getLayout();
        if(layout==null||b.isLayoutRequested()||!b.isLaidOut()||!b.isAttachedToWindow()){
          root.postInvalidateOnAnimation();return true;
        }
        String label=b.getText().toString();Rect glyph=new Rect(),visible=new Rect();
        b.getPaint().getTextBounds(label,0,label.length(),glyph);
        int top=b.getCompoundPaddingTop(),bottom=b.getHeight()-b.getCompoundPaddingBottom();
        int glyphTop=b.getBaseline()+glyph.top-b.getScrollY(),glyphBottom=b.getBaseline()+glyph.bottom-b.getScrollY();
        boolean shown=b.getGlobalVisibleRect(visible)&&b.isShown();
        JSONObject checks=new JSONObject().put("layoutFits",layout.getHeight()<=bottom-top)
          .put("glyphFits",glyphTop>=top&&glyphBottom<=bottom)
          .put("wholeLabel",DesignUi.NAV[i].equals(label)&&layout.getText().toString().equals(label)
            &&layout.getLineCount()==1&&layout.getEllipsisCount(0)==0&&layout.getLineEnd(0)==label.length())
          .put("widthFits",layout.getLineWidth(0)<=b.getWidth()-b.getCompoundPaddingLeft()-b.getCompoundPaddingRight()+.5f)
          .put("viewVisible",shown&&visible.width()==b.getWidth()&&visible.height()==b.getHeight())
          .put("unscrolled",b.getScrollX()==0&&b.getScrollY()==0)
          .put("selectionMatches",b.isSelected()==(i==selected));
        boolean valid=true;java.util.Iterator<String> keys=checks.keys();while(keys.hasNext())valid&=checks.getBoolean(keys.next());
        rows.put(new JSONObject().put("buttonIndex",i).put("label",label).put("selected",b.isSelected())
          .put("width",b.getWidth()).put("height",b.getHeight()).put("layoutHeight",layout.getHeight())
          .put("standardLineHeight",b.getLineHeight()).put("layoutClass",layout.getClass().getName())
          .put("compoundPaddingTop",top).put("compoundPaddingBottom",b.getCompoundPaddingBottom())
          .put("contentHeight",bottom-top).put("baseline",b.getBaseline()).put("scrollY",b.getScrollY())
          .put("glyphBounds",new JSONArray(new int[]{glyph.left,glyph.top,glyph.right,glyph.bottom}))
          .put("glyphTop",glyphTop).put("glyphBottom",glyphBottom).put("textSizePx",b.getTextSize())
          .put("includeFontPadding",b.getIncludeFontPadding()).put("fallbackLineSpacing",Build.VERSION.SDK_INT>=28&&b.isFallbackLineSpacing())
          .put("checks",checks).put("valid",valid));
      }
      String snapshot=rows.toString();
      // Observe two identical laid-out frames. A padding correction may have
      // requested another native layout; never record its transient first pass.
      if(!snapshot.equals(previous)){previous=snapshot;root.postInvalidateOnAnimation();return true;}
      for(int i=0;i<rows.length();i++){
        JSONObject row=rows.getJSONObject(i);allFit&=row.getBoolean("valid");
        emit(base("label").put("selectedIndex",selected).put("measurement",row));observations++;
      }
      if(selected==buttons.length-1){
        emit(base("summary").put("status",allFit?"verified":"failed").put("observationCount",observations).put("allFit",allFit));
        close();return true;
      }
      selected++;previous=null;
      // Exercise production selection updates; do not patch any measured view.
      root.post(()->{if(!closed){ReferenceUi.markNav(buttons,selected);root.postInvalidateOnAnimation();}});
    }catch(Exception failure){failed(failure);}
    return true;
  }

  JSONObject base(String kind)throws Exception{
    return new JSONObject().put("schema",1).put("kind",kind).put("nonce",nonce)
      .put("sourceCommit",identity.getString("sourceCommit")).put("sourceTree",identity.getString("sourceTree"))
      .put("apkSha256",identity.getString("apkSha256")).put("fontScale",activity.getResources().getConfiguration().fontScale)
      .put("density",activity.getResources().getDisplayMetrics().density).put("actualAndroidLayout",true)
      .put("scope","Actual ReferenceUi.nav component fixture; not MainActivity or network acceptance")
      .put("startedUptimeMs",started).put("observedUptimeMs",SystemClock.uptimeMillis());
  }
  static void emit(JSONObject value)throws Exception{
    String raw=value.toString();if(raw.getBytes(StandardCharsets.UTF_8).length>3500)throw new IllegalStateException("Typography record too large");
    Log.i(TAG,raw);
  }
  void failed(Exception failure){
    try{emit(base("summary").put("status","failed").put("errorType",failure.getClass().getSimpleName()).put("observationCount",observations));}
    catch(Exception ignored){Log.e(TAG,"Could not retain navigation typography observation");}
    close();
  }
  static void rejected(Activity activity,Exception failure){
    try{emit(new JSONObject().put("schema",1).put("kind","summary").put("nonce",activity.getIntent().getStringExtra("visualNonce"))
      .put("status","failed").put("errorType",failure.getClass().getSimpleName()));}
    catch(Exception ignored){Log.e(TAG,"Navigation typography observation rejected");}
  }
  @Override public void run(){if(!closed)failed(new IllegalStateException("Native navigation layout did not stabilize"));}
  void close(){if(closed)return;closed=true;handler.removeCallbacks(this);if(root.getViewTreeObserver().isAlive())root.getViewTreeObserver().removeOnPreDrawListener(this);}
}
