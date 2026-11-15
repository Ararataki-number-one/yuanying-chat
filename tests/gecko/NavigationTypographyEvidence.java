package local.pocketchat;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
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
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only observation of the actual shared navigation component.
 * This fixture is not a MainActivity screenshot or a website/network test.
 */
final class NavigationTypographyEvidence implements ViewTreeObserver.OnPreDrawListener, Runnable {
  static final String TAG="PocketNavType";
  final Activity activity;final LinearLayout root;final Button[] buttons;
  final Button[] initialButtons;final Rect[] initialButtonBounds,initialIconBounds;
  final Map<String,JSONObject> iconRenderings=new HashMap<>();
  final String navigationMode;final String[] labels;
  final int[] workspacePages={AppHub.CHAT,AppHub.ENVIRONMENTS,AppHub.DOWNLOADS,AppHub.NETWORK,AppHub.SETTINGS};
  final Handler handler=new Handler(Looper.getMainLooper());final JSONObject identity;
  final String nonce;final long started=SystemClock.uptimeMillis();
  int selected=WorkspaceNavigation.NONE,observations;boolean closed,allFit=true;String previous;

  NavigationTypographyEvidence(Activity activity)throws Exception{
    this.activity=activity;nonce=activity.getIntent().getStringExtra("visualNonce");
    String requestedMode=activity.getIntent().getStringExtra("visualNavigationMode");
    if(requestedMode!=null&&!"conversation".equals(requestedMode)&&!"workspace".equals(requestedMode))
      throw new IllegalArgumentException("Known navigation mode required");
    navigationMode="workspace".equals(requestedMode)?"workspace":"conversation";
    labels="workspace".equals(navigationMode)?new String[]{"浏览器","环境","下载","网络","设置"}:DesignUi.NAV;
    buttons=new Button[labels.length];
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
    root.addView("workspace".equals(navigationMode)?ReferenceUi.workspaceNav(activity,selected,n->{},buttons)
      :ReferenceUi.nav(activity,selected,n->{},buttons));
    initialButtons=buttons.clone();initialButtonBounds=new Rect[buttons.length];initialIconBounds=new Rect[buttons.length];
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
        String label=b.getText().toString();Rect visible=new Rect();
        int top=b.getCompoundPaddingTop(),bottom=b.getHeight()-b.getCompoundPaddingBottom();
        int left=b.getCompoundPaddingLeft(),right=b.getWidth()-b.getCompoundPaddingRight();
        int lineCount=layout.getLineCount(),maximumLines="workspace".equals(navigationMode)?2:1,covered=0;
        boolean wholeLabel=labels[i].equals(label)&&layout.getText().toString().equals(label)
          &&lineCount>=1&&lineCount<=maximumLines;
        boolean glyphFits=true,widthFits=true,horizontalLineFits=true,horizontalGlyphFits=true;
        JSONArray lines=new JSONArray();
        for(int line=0;line<lineCount;line++){
          int start=layout.getLineStart(line),end=layout.getLineEnd(line);
          boolean range=start==covered&&start>=0&&end>start&&end<=label.length();
          Rect glyph=new Rect();if(range)b.getPaint().getTextBounds(label,start,end,glyph);
          wholeLabel&=range&&layout.getEllipsisCount(line)==0&&layout.getEllipsisStart(line)==0;covered=end;
          int baseline=b.getBaseline()+layout.getLineBaseline(line)-layout.getLineBaseline(0);
          int glyphTop=baseline+glyph.top-b.getScrollY(),glyphBottom=baseline+glyph.bottom-b.getScrollY();
          // Use each native line's draw origin and baseline. The complete label
          // may wrap, but no character, glyph or fallback-font height may clip.
          float primary=layout.getPrimaryHorizontal(start),drawX=left+primary-b.getScrollX();
          float lineLeft=left+layout.getLineLeft(line)-b.getScrollX(),lineRight=left+layout.getLineRight(line)-b.getScrollX();
          float glyphLeft=drawX+glyph.left,glyphRight=drawX+glyph.right;
          glyphFits&=glyphTop>=top&&glyphBottom<=bottom;
          widthFits&=layout.getLineWidth(line)<=right-left+.5f;
          horizontalLineFits&=lineLeft>=left-.5f&&lineRight<=right+.5f;
          horizontalGlyphFits&=layout.getParagraphDirection(line)==1&&glyphLeft>=left-.5f&&glyphRight<=right+.5f;
          lines.put(new JSONObject().put("start",start).put("end",end).put("text",range?label.substring(start,end):"")
            .put("ellipsisCount",layout.getEllipsisCount(line)).put("ellipsisStart",layout.getEllipsisStart(line))
            .put("layoutBaseline",layout.getLineBaseline(line)).put("lineWidth",layout.getLineWidth(line))
            .put("lineLeft",layout.getLineLeft(line)).put("lineRight",layout.getLineRight(line))
            .put("paragraphDirection",layout.getParagraphDirection(line)).put("primaryHorizontal",primary)
            .put("glyphBounds",new JSONArray(new int[]{glyph.left,glyph.top,glyph.right,glyph.bottom})));
        }
        wholeLabel&=covered==label.length();
        boolean shown=b.getGlobalVisibleRect(visible)&&b.isShown();
        Drawable drawable=b.getCompoundDrawables()[1];Ui.Icon icon=drawable instanceof Ui.Icon?(Ui.Icon)drawable:null;
        Rect iconBounds=drawable==null?new Rect():new Rect(drawable.getBounds());
        Rect buttonBounds=new Rect(b.getLeft(),b.getTop(),b.getRight(),b.getBottom());
        if(initialButtonBounds[i]==null){initialButtonBounds[i]=new Rect(buttonBounds);initialIconBounds[i]=new Rect(iconBounds);}
        boolean expectedSelected=i==selected;int expectedInk=expectedSelected?DesignUi.GLASS_INK:DesignUi.GLASS_MUTED;
        int expectedIconInk=expectedSelected?DesignUi.BLUE:DesignUi.GLASS_MUTED;
        JSONObject rendered=iconRendering(icon);
        JSONObject checks=new JSONObject().put("layoutFits",layout.getHeight()<=bottom-top)
          .put("glyphFits",glyphFits)
          .put("wholeLabel",wholeLabel)
          .put("widthFits",widthFits)
          .put("viewVisible",shown&&visible.width()==b.getWidth()&&visible.height()==b.getHeight())
          .put("horizontalLineFits",horizontalLineFits)
          .put("horizontalGlyphFits",horizontalGlyphFits)
          .put("verticalUnscrolled",b.getScrollY()==0)
          .put("selectionMatches",b.isSelected()==expectedSelected)
          .put("iconSolidMatchesSelection",icon!=null&&icon.solid==expectedSelected)
          .put("iconInkMatchesSelection",icon!=null&&icon.color==expectedIconInk)
          .put("labelInkMatchesSelection",b.getCurrentTextColor()==expectedInk)
          .put("buttonIdentityStable",b==initialButtons[i])
          .put("buttonBoundsStable",buttonBounds.equals(initialButtonBounds[i]))
          .put("iconBoundsStable",iconBounds.width()>0&&iconBounds.height()>0&&iconBounds.equals(initialIconBounds[i]))
          .put("iconStatesRenderNonempty",rendered.optBoolean("bothNonempty"))
          .put("iconStatesRenderDifferently",rendered.optBoolean("imagesDiffer"))
          .put("iconRenderStateRestored",rendered.optBoolean("stateRestored"))
          .put("minimumTouchTarget",b.getWidth()>=ReferenceUi.dp(activity,48)&&b.getHeight()>=ReferenceUi.dp(activity,48));
        boolean valid=true;java.util.Iterator<String> keys=checks.keys();while(keys.hasNext())valid&=checks.getBoolean(keys.next());
        rows.put(new JSONObject().put("buttonIndex",i).put("label",label).put("selected",b.isSelected())
          .put("width",b.getWidth()).put("height",b.getHeight()).put("layoutHeight",layout.getHeight())
          .put("layoutWidth",layout.getWidth()).put("compoundPaddingLeft",left).put("compoundPaddingRight",b.getCompoundPaddingRight())
          .put("contentWidth",right-left).put("scrollX",b.getScrollX())
          .put("typographyVersion",2).put("lineCount",lineCount).put("maximumLines",maximumLines).put("lines",lines)
          .put("standardLineHeight",b.getLineHeight()).put("layoutClass",layout.getClass().getName())
          .put("compoundPaddingTop",top).put("compoundPaddingBottom",b.getCompoundPaddingBottom())
          .put("contentHeight",bottom-top).put("baseline",b.getBaseline()).put("scrollY",b.getScrollY())
          .put("textSizePx",b.getTextSize())
          .put("includeFontPadding",b.getIncludeFontPadding()).put("fallbackLineSpacing",Build.VERSION.SDK_INT>=28&&b.isFallbackLineSpacing())
          .put("icon",new JSONObject().put("name",icon==null?JSONObject.NULL:icon.name)
            .put("solid",icon==null?JSONObject.NULL:icon.solid).put("color",icon==null?JSONObject.NULL:icon.color)
            .put("expectedColor",expectedIconInk).put("bounds",new JSONArray(new int[]{iconBounds.left,iconBounds.top,iconBounds.right,iconBounds.bottom})))
          .put("buttonBounds",new JSONArray(new int[]{buttonBounds.left,buttonBounds.top,buttonBounds.right,buttonBounds.bottom}))
          .put("iconRendering",rendered)
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
      root.post(()->{if(!closed){
        if("workspace".equals(navigationMode))ReferenceUi.markWorkspaceNav(buttons,workspacePages[selected]);
        else ReferenceUi.markNav(buttons,selected);
        root.postInvalidateOnAnimation();
      }});
    }catch(Exception failure){failed(failure);}
    return true;
  }

  /** Render the real drawable off-screen once per glyph/size; restore its live state. */
  JSONObject iconRendering(Ui.Icon icon)throws Exception{
    if(icon==null)return new JSONObject();
    Rect savedBounds=new Rect(icon.getBounds());int width=savedBounds.width(),height=savedBounds.height();
    if(width<=0||height<=0)return new JSONObject();
    String key=icon.name+":"+width+"x"+height;JSONObject cached=iconRenderings.get(key);if(cached!=null)return cached;
    boolean savedSolid=icon.solid;int savedColor=icon.color;
    Bitmap bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);
    int[] outline=new int[width*height],solid=new int[width*height];
    try{
      icon.setBounds(0,0,width,height);icon.solid=false;icon.draw(new Canvas(bitmap));
      bitmap.getPixels(outline,0,width,0,0,width,height);
      bitmap.eraseColor(0);icon.solid=true;icon.draw(new Canvas(bitmap));
      bitmap.getPixels(solid,0,width,0,0,width,height);
    }finally{icon.solid=savedSolid;icon.color=savedColor;icon.setBounds(savedBounds);bitmap.recycle();}
    JSONObject outlined=pixels(outline),filled=pixels(solid);
    JSONObject result=new JSONObject().put("actualAndroidBitmapRendering",true)
      .put("width",width).put("height",height).put("sampleColor",savedColor)
      .put("outline",outlined).put("solid",filled)
      .put("bothNonempty",outlined.getInt("nonTransparentPixels")>0&&filled.getInt("nonTransparentPixels")>0)
      .put("imagesDiffer",!java.util.Arrays.equals(outline,solid))
      .put("stateRestored",icon.solid==savedSolid&&icon.color==savedColor&&icon.getBounds().equals(savedBounds));
    iconRenderings.put(key,result);return result;
  }
  static JSONObject pixels(int[] pixels)throws Exception{
    int nonTransparent=0;long alphaSum=0;ByteBuffer bytes=ByteBuffer.allocate(pixels.length*4);
    for(int pixel:pixels){int alpha= pixel>>>24;if(alpha>0)nonTransparent++;alphaSum+=alpha;bytes.putInt(pixel);}
    byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes.array());StringBuilder hex=new StringBuilder();
    for(byte value:digest){hex.append(Character.forDigit((value>>>4)&15,16));hex.append(Character.forDigit(value&15,16));}
    return new JSONObject().put("nonTransparentPixels",nonTransparent).put("alphaSum",alphaSum).put("argbSha256",hex.toString());
  }

  JSONObject base(String kind)throws Exception{
    return new JSONObject().put("schema",1).put("kind",kind).put("nonce",nonce)
      .put("sourceCommit",identity.getString("sourceCommit")).put("sourceTree",identity.getString("sourceTree"))
      .put("apkSha256",identity.getString("apkSha256")).put("fontScale",activity.getResources().getConfiguration().fontScale)
      .put("navigationMode",navigationMode)
      .put("density",activity.getResources().getDisplayMetrics().density).put("actualAndroidLayout",true)
      .put("scope","Actual "+("workspace".equals(navigationMode)?"ReferenceUi.workspaceNav":"ReferenceUi.nav")
        +" component fixture; not MainActivity or network acceptance")
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
