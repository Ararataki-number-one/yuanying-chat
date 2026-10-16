package local.pocketchat;

import android.app.Activity;
import android.graphics.Rect;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Recycled source nodes. Selection remains detached until the explicit confirmation. */
final class ExitNodePickerUi {
  interface PickCallback {void selected(NetworkCatalog catalog,String nodeKey,String nodeName);}
  final Activity a;
  final JSONObject source;
  final String role,id,url;
  final long addressRevision;
  final PickCallback callback;
  final List<String> names;
  final ReferenceUi.Modal dialog;
  final Map<String,JSONObject> byName=new HashMap<>();
  String selectedKey,selectedName;
  TextView error;
  boolean checking;
  NodeAdapter adapter;

  ExitNodePickerUi(Activity a,JSONObject source,String selectedKey,PickCallback callback){
    this(a,source,selectedKey,"",callback);
  }
  ExitNodePickerUi(Activity a,JSONObject source,String selectedKey,String selectedName,PickCallback callback){
    this.a=a;this.source=NetworkCatalog.copy(source);this.callback=callback;this.selectedName=selectedName;
    this.selectedKey=selectedKey==null?"":selectedKey;
    role=source.optString("role",NetworkCatalog.EXIT);id=source.optString("id");
    url=source.optString("url");addressRevision=source.optLong("addressRevision");
    names=NetworkSourceSelection.names(source);JSONArray details=this.source.optJSONArray("nodeDetails");if(details!=null)for(int i=0;i<details.length();i++){JSONObject node=details.optJSONObject(i);if(node!=null)byName.put(node.optString("name"),node);}
    dialog=new ReferenceUi.Modal(a,callback==null?NetworkWorkspaceUi.roleName(role)+"节点":"选择固定出口节点");
  }
  int dp(int n){return ReferenceUi.dp(a,n);}
  int rowHeight(){return dp(Math.max(58,18+Math.round(32*a.getResources().getConfiguration().fontScale)));}
  ReferenceUi.Modal show(){
    dialog.note(source.optString("name")+" · "+names.size()+" 个节点");
    if(callback!=null)dialog.note("选择一个 SOCKS5 节点作为固定出口。其他协议暂不支持作为出口，入口仍可使用它们。");
    else if(source.optBoolean("stale"))dialog.note("这是上次成功读取的节点，当前订阅地址尚未更新成功。");
    ListView list=new ListView(a);list.setDivider(null);list.setNestedScrollingEnabled(true);
    list.setOnTouchListener((v,event)->{if(event.getActionMasked()==MotionEvent.ACTION_DOWN)v.getParent().requestDisallowInterceptTouchEvent(v.canScrollVertically(1)||v.canScrollVertically(-1));return false;});
    adapter=new NodeAdapter();list.setAdapter(adapter);
    Rect frame=new Rect();a.getWindow().getDecorView().getWindowVisibleDisplayFrame(frame);
    int height=frame.height()>0?frame.height():a.getResources().getDisplayMetrics().heightPixels;
    int max=Math.max(dp(112),(int)(height*.82)-dp(callback==null?210:300));
    dialog.body.addView(list,new LinearLayout.LayoutParams(-1,Math.min(max,Math.max(dp(56),names.size()*rowHeight()))));
    if(names.isEmpty())dialog.note("尚未读取到节点，请更新订阅。");
    error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);dialog.body.addView(error);
    dialog.buttons(callback==null?"关闭":"取消",dialog::dismiss,callback==null?"":"确定",this::confirm);dialog.show();return dialog;
  }
  void confirm(){
    if(callback==null||checking)return;String key=selectedKey,name=selectedName;checking=true;dialog.primary().setEnabled(false);dialog.primary().setText("正在检查…");
    NetworkWorkspaceUi.libraryWork(()->{
      NetworkCatalog catalog=new NetworkCatalog(a);JSONObject current=catalog.subscription(role,id);String failure="";
      if(current==null||!url.equals(current.optString("url"))||addressRevision!=current.optLong("addressRevision")||!NetworkWorkspaceUi.hasCurrentCacheMetadata(current))failure="订阅已修改或暂不可用，请关闭后重新选择当前订阅。";
      JSONObject node=NetworkSourceSelection.node(current,key,name);
      if(failure.isEmpty()&&!NetworkSourceSelection.socks5(node))failure="请选择一个有效的 SOCKS5 出口节点。";
      String message=failure,chosen=node==null?"":node.optString("name");
      a.runOnUiThread(()->{
        if(a.isDestroyed()||!dialog.isShowing())return;checking=false;
        if(!message.isEmpty()){error.setText(message);dialog.primary().setEnabled(true);dialog.primary().setText("确定");dialog.resize();return;}
        dialog.dismiss();callback.selected(catalog,key,chosen);
      });
    });
  }
  final class NodeAdapter extends BaseAdapter {
    public int getCount(){return names.size();}
    public String getItem(int position){return names.get(position);}
    public long getItemId(int position){return position;}
    public View getView(int position,View recycled,ViewGroup parent){
      LinearLayout row;
      if(recycled instanceof LinearLayout)row=(LinearLayout)recycled;
      else{
        row=DesignUi.row(a);row.setPadding(dp(10),dp(5),dp(10),dp(5));row.setMinimumHeight(rowHeight());
        TextView mark=ReferenceUi.text(a,"",20,ReferenceUi.BLUE,false);row.addView(mark,new LinearLayout.LayoutParams(dp(30),-2));
        LinearLayout labels=DesignUi.column(a);TextView name=ReferenceUi.text(a,"",14,ReferenceUi.TEXT,true);ReferenceUi.single(name);labels.addView(name);labels.addView(ReferenceUi.secondary(a,""));row.addView(labels,new LinearLayout.LayoutParams(0,-2,1));row.addView(ReferenceUi.more(a,()->{}),new LinearLayout.LayoutParams(dp(44),dp(44)));
      }
      String name=getItem(position);View more=row.getChildAt(2);more.setVisibility(callback==null?View.VISIBLE:View.GONE);more.setOnClickListener(v->NetworkShareUi.nodeMenu(a,source,name));JSONObject node=byName.get(name);String key=node==null?"":node.optString("configFingerprint");
      boolean supported=NetworkSourceSelection.socks5(node)&&!key.isEmpty();
      boolean chosen=callback!=null&&!key.isEmpty()&&key.equals(selectedKey)&&name.equals(selectedName);
      TextView mark=(TextView)row.getChildAt(0);mark.setVisibility(callback==null?View.GONE:View.VISIBLE);mark.setText(chosen?"◉":"○");mark.setTextColor(supported?ReferenceUi.BLUE:ReferenceUi.MUTED);
      LinearLayout labels=(LinearLayout)row.getChildAt(1);((TextView)labels.getChildAt(0)).setText(NetworkWorkspaceUi.nodeName(name));
      String type=node==null?"协议未识别":node.optString("type");((TextView)labels.getChildAt(1)).setText(type+(callback!=null&&!supported?" · 暂不能作为固定出口":""));
      row.setBackground(ReferenceUi.surface(a,chosen?0xfff7faff:ReferenceUi.WHITE,10,chosen?0xff94b8ff:ReferenceUi.LINE));
      row.setSelected(chosen);row.setAlpha(callback!=null&&!supported?.6f:1f);row.setFocusable(callback!=null);
      row.setContentDescription(NetworkWorkspaceUi.nodeName(name)+"，"+type+(callback!=null&&!supported?"，暂不能作为固定出口":chosen?"，已选择":""));
      row.setOnClickListener(callback==null?null:v->{
        if(checking)return;
        if(!supported){error.setText("当前出口链支持 SOCKS5，请选择列表中的 SOCKS5 节点。");dialog.resize();return;}
        selectedKey=key;selectedName=name;error.setText("");notifyDataSetChanged();
      });return row;
    }
  }
}
