package local.pocketchat;

import android.app.Activity;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.Layout;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.Button;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

/** Test-only observation of the existing production button, without layout mutations. */
final class DownloadLocationLayoutEvidence implements ViewTreeObserver.OnPreDrawListener, Runnable {
  static final String TAG="PocketDownloadLabel", LABEL="保存位置";
  final Activity activity; final View root; final String nonce; final Handler handler=new Handler(Looper.getMainLooper());
  final long started=SystemClock.uptimeMillis(); boolean closed;
  DownloadLocationLayoutEvidence(Activity activity,View root,String nonce){
    this.activity=activity;this.root=root;this.nonce=nonce;
    root.getViewTreeObserver().addOnPreDrawListener(this);handler.postDelayed(this,5000);
  }
  @Override public boolean onPreDraw(){
    if(closed)return true;
    try{
      ArrayList<Button> buttons=new ArrayList<>();find(root,buttons);
      if(buttons.size()!=1||root.isLayoutRequested())return true;
      Button button=buttons.get(0);Layout layout=button.getLayout();
      if(layout==null||button.isLayoutRequested()||!button.isLaidOut()||!button.isAttachedToWindow()||!button.hasWindowFocus())return true;
      if(layout.getLineCount()<1||layout.getLineCount()>8)throw new IllegalStateException("Unexpected label line count");
      JSONObject value=base();JSONArray lines=new JSONArray();
      for(int i=0;i<layout.getLineCount();i++)lines.put(new JSONObject().put("start",layout.getLineStart(i)).put("end",layout.getLineEnd(i)).put("left",layout.getLineLeft(i)).put("right",layout.getLineRight(i)).put("bottom",layout.getLineBottom(i)).put("ellipsisCount",layout.getEllipsisCount(i)));
      Rect visible=new Rect();boolean shown=button.getGlobalVisibleRect(visible);int[] point=new int[2];button.getLocationOnScreen(point);
      value.put("status","observed").put("text",button.getText().toString()).put("layoutTextLength",layout.getText().length())
        .put("actualAndroidLayout",true).put("viewClass",button.getClass().getName()).put("layoutClass",layout.getClass().getName())
        .put("width",button.getWidth()).put("height",button.getHeight()).put("contentWidth",button.getWidth()-button.getCompoundPaddingLeft()-button.getCompoundPaddingRight())
        .put("contentHeight",button.getHeight()-button.getCompoundPaddingTop()-button.getCompoundPaddingBottom()).put("layoutWidth",layout.getWidth()).put("layoutHeight",layout.getHeight())
        .put("left",point[0]).put("top",point[1]).put("visibleWidth",visible.width()).put("visibleHeight",visible.height())
        .put("shown",shown&&button.isShown()).put("enabled",button.isEnabled()).put("clickable",button.isClickable()).put("windowFocused",button.hasWindowFocus())
        .put("layoutRequested",button.isLayoutRequested()).put("scrollX",button.getScrollX()).put("scrollY",button.getScrollY()).put("lines",lines);
      emit(value);
    }catch(Exception failure){failed(failure);}
    return true;
  }
  static void find(View view,ArrayList<Button> result){
    if(view instanceof Button&&LABEL.contentEquals(((Button)view).getText()))result.add((Button)view);
    if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)find(group.getChildAt(i),result);}
  }
  JSONObject base()throws Exception{
    if(!"local.pocketchat.test".equals(activity.getPackageName())||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalStateException("Owned synthetic capture required");
    JSONObject stamp;
    try(InputStream in=activity.getAssets().open("pocketchat-integration-build.json");ByteArrayOutputStream out=new ByteArrayOutputStream()){
      byte[] bytes=new byte[1024];int count;while((count=in.read(bytes))!=-1){out.write(bytes,0,count);if(out.size()>8192)throw new IllegalStateException("Source stamp too large");}
      stamp=new JSONObject(out.toString("UTF-8"));
    }
    String source=stamp.getString("sourceCommit");
    if(!source.matches("[0-9a-f]{40}")||stamp.getBoolean("dirtySource"))throw new IllegalStateException("Clean source stamp required");
    return new JSONObject().put("schema",1).put("sourceCommit",source).put("nonce",nonce).put("scene","downloads")
      .put("fontScale",activity.getResources().getConfiguration().fontScale).put("density",activity.getResources().getDisplayMetrics().density)
      .put("startedUptimeMs",started).put("observedUptimeMs",SystemClock.uptimeMillis());
  }
  void emit(JSONObject value)throws Exception{
    String raw=value.toString();if(raw.getBytes(StandardCharsets.UTF_8).length>3500)throw new IllegalStateException("Label evidence exceeds one log record");
    close();Log.i(TAG,raw);
  }
  void failed(Exception failure){
    try{emit(new JSONObject().put("schema",1).put("nonce",nonce).put("scene","downloads").put("status","failed").put("error",failure.getClass().getSimpleName()));}
    catch(Exception ignored){close();Log.e(TAG,"Could not retain download label observation");}
  }
  @Override public void run(){if(!closed)failed(new IllegalStateException("Production button layout was not ready"));}
  void close(){if(closed)return;closed=true;handler.removeCallbacks(this);if(root.getViewTreeObserver().isAlive())root.getViewTreeObserver().removeOnPreDrawListener(this);}
}
