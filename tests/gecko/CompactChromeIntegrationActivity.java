package local.pocketchat;

import android.content.*;
import android.graphics.*;
import android.os.*;
import android.util.Log;
import android.view.*;
import android.widget.*;
import java.lang.reflect.*;
import org.json.*;

/** Test-only: actual production chrome, native hit regions and trusted Android taps. */
public final class CompactChromeIntegrationActivity extends MainActivity {
  boolean reporting;
  String command="";
  int actionCount;

  @Override public void onCreate(Bundle state){
    if(!getPackageName().endsWith(".test"))throw new SecurityException();
    ProfileCatalog.get(this).created(0);
    Profiles.rename(this,0,getIntent().getBooleanExtra("longName",true)?"长文阅读与文件整理和日常会话测试环境":"默认环境");
    getSharedPreferences("chat",0).edit().putString("browserEngine","system").putString("networkMode","external").putBoolean("networkConfigured",false).putBoolean("environmentInitialized",true).putBoolean("pageMode",false).remove("pending").commit();
    AppSettings.put(this,"brandSeen","true");
    AppSettings.put(this,"updateAutoCheck","false");
    getIntent().putExtra("openWindowAction","native-smoke");
    // This layout fixture does not open a website or make synthetic state a real connection.
    ChatSession.get(this).manualAttention=true;
    super.onCreate(state);
    command=getIntent().getStringExtra("compactCommand");
    handler.postDelayed(()->{
      handler.removeCallbacks(ticker);
      session.remove(sessionObserver);
      reporting=true;
      snapshot("ready");
    },600);
  }

  @Override void startNetwork(){}

  @Override protected void onNewIntent(Intent intent){
    super.onNewIntent(intent);
    command=intent.getStringExtra("compactCommand");
    if("snapshot".equals(intent.getStringExtra("compactAction")))handler.post(()->snapshot("snapshot"));
  }

  @Override void showDrawer(){
    super.showDrawer();
    if(reporting)event("drawer");
  }

  @Override void moreSheet(){
    super.moreSheet();
    if(reporting)event("more");
  }

  @Override void showPage(boolean show){
    super.showPage(show);
    if(reporting)event(show?"web":"native");
  }

  @Override public void startActivity(Intent intent){
    super.startActivity(intent);
    if(reporting)event("activity:"+(intent.getComponent()==null?"":intent.getComponent().getClassName()));
  }

  void event(String action){
    actionCount++;
    Log.i("PocketCompactChrome",J.obj("command",command,"event","action","action",action,"actions",actionCount,"page",hub.page).toString());
  }

  void snapshot(String event){
    try{
      handler.removeCallbacks(ticker);
      session.remove(sessionObserver);
      long now=System.currentTimeMillis();
      JSONObject config=J.obj("subscriptionUrl","https://example.test/compact-layout","exitHost","example.test","exitPort",1080,"exitRegion","日本 · Tokyo");
      JSONObject runtime=J.obj("at",now,"mode","internal","configured",true,"connected",true,"exitId",NetworkCatalog.exitId(config),"subscriptionId",NativeNetwork.hash(config.optString("subscriptionUrl")),"ip","203.0.113.25","entry","Entry|大阪 03","delayEntry","Entry|大阪 03","delay",42,"delayAt",now);
      WindowNetworkState network=new WindowNetworkState(this,ProfileCatalog.get(this).item(0),config,runtime,true,now);
      // Reflection keeps this integration source compilable with the historical UI baseline.
      Method show=DesignChrome.class.getDeclaredMethod("showNetwork",WindowNetworkState.class);
      show.setAccessible(true);show.invoke(designChrome,network);
      toolbar.postDelayed(()->report(event,network),100);
    }catch(Exception error){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"error",error.toString()).toString());}
  }

  void report(String event,WindowNetworkState network){
    try{
      TextView latency=(TextView)field("latencyWord");
      View more=(View)field("more");
      View top=(View)field("top");
      Method touch=DesignChrome.class.getDeclaredMethod("touchBounds",View.class);
      touch.setAccessible(true);
      String[] names={"drawer","environment","native","web","more"};
      View[] views={navigation,designChrome.title,nativeTab,webTab,more};
      int[] origin=new int[2];toolbar.getLocationOnScreen(origin);
      JSONArray controls=new JSONArray();
      for(int i=0;i<views.length;i++){
        Rect hit=(Rect)touch.invoke(designChrome,views[i]);hit.offset(origin[0],origin[1]);
        controls.put(J.obj("name",names[i],"visible",bounds(views[i]),"touch",rect(hit),"widthDp",hit.width()/density(),"heightDp",hit.height()/density(),"tap",J.arr(hit.centerX(),hit.bottom-1)));
      }
      JSONArray texts=new JSONArray();
      for(TextView text:new TextView[]{designChrome.title,nativeTab,webTab,networkLine,latency,designChrome.stateWord}){
        Paint.FontMetrics font=text.getPaint().getFontMetrics();
        texts.put(J.obj("text",text.getText().toString(),"bounds",bounds(text),"fontHeight",font.bottom-font.top,"contentHeight",text.getHeight()-text.getPaddingTop()-text.getPaddingBottom(),"inkWidth",text.getPaint().measureText(text.getText().toString()),"contentWidth",text.getWidth()-text.getPaddingLeft()-text.getPaddingRight(),"ellipsized",text.getLayout()!=null&&text.getLayout().getLineCount()>0&&text.getLayout().getEllipsisCount(0)>0,"clickable",text.isClickable()));
      }
      Rect networkBounds=screenBounds(designChrome.networkRow);
      Rect toolbarBounds=screenBounds(toolbar);
      Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"actions",actionCount,"page",hub.page,"pageMode",pageMode,"viewportDp",getResources().getDisplayMetrics().widthPixels/density(),"fontScale",getResources().getConfiguration().fontScale,"toolbar",rect(toolbarBounds),"toolbarHeightDp",toolbar.getHeight()/density(),"topHeightDp",top.getHeight()/density(),"networkHeightDp",designChrome.networkRow.getHeight()/density(),"networkBounds",rect(networkBounds),"networkTap",J.arr(networkBounds.centerX(),networkBounds.centerY()),"stateTap",center(designChrome.stateWord),"networkClickable",designChrome.networkRow.isClickable(),"networkFocusable",designChrome.networkRow.isFocusable(),"networkBackground",designChrome.networkRow.getBackground()==null?"none":designChrome.networkRow.getBackground().getClass().getName(),"networkDescription",String.valueOf(designChrome.networkRow.getContentDescription()),"latency",latency.getText().toString(),"expectedLatency",network.latency,"controls",controls,"texts",texts).toString());
    }catch(Exception error){Log.i("PocketCompactChrome",J.obj("command",command,"event",event,"error",error.toString()).toString());}
  }

  Object field(String name)throws Exception{Field field=DesignChrome.class.getDeclaredField(name);field.setAccessible(true);return field.get(designChrome);}
  float density(){return getResources().getDisplayMetrics().density;}
  JSONArray bounds(View view){return rect(screenBounds(view));}
  Rect screenBounds(View view){int[] at=new int[2];view.getLocationOnScreen(at);return new Rect(at[0],at[1],at[0]+view.getWidth(),at[1]+view.getHeight());}
  JSONArray rect(Rect value){return J.arr(value.left,value.top,value.right,value.bottom);}
  JSONArray center(View view){Rect bounds=screenBounds(view);return J.arr(bounds.centerX(),bounds.centerY());}
}
