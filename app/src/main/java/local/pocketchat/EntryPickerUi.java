package local.pocketchat;

import android.app.Activity;import android.content.res.ColorStateList;import android.graphics.Rect;import android.view.*;import android.widget.*;
import org.json.*;import java.util.*;

/** Recycled choices keep large real subscription pools responsive on a phone. */
final class EntryPickerUi {
  final Activity a;final ReferenceUi.Modal dialog;final NetworkDraft draft;final List<String> nodes;final Runnable changed;
  final LinkedHashSet<String> pool;String mode,entry;TextView result,error;Button shuffle;GridView grid;NodeAdapter adapter;
  EntryPickerUi(Activity a,NetworkDraft draft,List<String> nodes,Runnable changed){this.a=a;this.draft=draft;this.nodes=nodes;this.changed=changed;pool=new LinkedHashSet<>(draft.pool);pool.retainAll(nodes);mode=draft.mode;entry=draft.entry;if(!nodes.contains(entry)||mode.equals("random")&&!pool.contains(entry))entry="";dialog=new ReferenceUi.Modal(a,"选择入口");}
  int dp(int n){return ReferenceUi.dp(a,n);}
  ReferenceUi.Modal show(){dialog.buttons("取消",dialog::dismiss,"确定",this::confirm);render();dialog.show();return dialog;}
  void render(){
    dialog.body.removeAllViews();boolean random=mode.equals("random");dialog.body.addView(ReferenceUi.tabs(a,new String[]{"自动随机","手动指定"},random?0:1,n->{mode=n==0?"random":"manual";if(mode.equals("random")&&!pool.contains(entry))entry="";render();}));dialog.note(random?"勾选参与随机的入口":"选择当前订阅中的一个入口");
    int columns=a.getResources().getConfiguration().screenWidthDp>360&&a.getResources().getConfiguration().fontScale<=1.2f?2:1;
    grid=new GridView(a);grid.setNumColumns(columns);grid.setHorizontalSpacing(dp(8));grid.setVerticalSpacing(dp(8));grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);grid.setNestedScrollingEnabled(true);
    grid.setOnTouchListener((v,event)->{if(event.getActionMasked()==MotionEvent.ACTION_DOWN)v.getParent().requestDisallowInterceptTouchEvent(v.canScrollVertically(1)||v.canScrollVertically(-1));return false;});
    adapter=new NodeAdapter();grid.setAdapter(adapter);Rect visible=new Rect();a.getWindow().getDecorView().getWindowVisibleDisplayFrame(visible);int height=visible.height()>0?visible.height():a.getResources().getDisplayMetrics().heightPixels;
    int cap=Math.max(dp(112),(int)(height*.82)-dp(random?330:230)),rows=(nodes.size()+columns-1)/columns;dialog.body.addView(grid,new LinearLayout.LayoutParams(-1,Math.min(rows*dp(56),cap)));
    if(random){LinearLayout box=ReferenceUi.card(a);box.setBackground(ReferenceUi.surface(a,0xfff5f9ff,14,0xffd4e3ff));result=ReferenceUi.text(a,"",15,ReferenceUi.TEXT,true);ReferenceUi.single(result);box.addView(result);shuffle=ReferenceUi.link(a,"重新随机",()->{entry=EntrySelection.random(pool,new Random());updateResult();adapter.notifyDataSetChanged();});box.addView(shuffle,new LinearLayout.LayoutParams(-1,dp(48)));dialog.body.addView(box);updateResult();}
    error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);dialog.body.addView(error);dialog.resize();
  }
  void updateResult(){if(result!=null&&mode.equals("random")){result.setText("当前入口："+(entry.isEmpty()?"尚未随机":NativeNetwork.display(entry)));result.setContentDescription(result.getText());shuffle.setEnabled(!pool.isEmpty());}}
  void confirm(){
    if(!nodes.contains(entry)||mode.equals("random")&&!pool.contains(entry)){error.setText(mode.equals("random")?"勾选入口后，点击重新随机":"请选择一个入口");dialog.resize();return;}
    draft.mode=mode;draft.entry=entry;draft.pool.clear();draft.pool.addAll(pool);dialog.dismiss();changed.run();
  }
  final class NodeAdapter extends BaseAdapter {
    public int getCount(){return nodes.size();}public String getItem(int position){return nodes.get(position);}public long getItemId(int position){return position;}
    public View getView(int position,View recycled,ViewGroup parent){
      boolean random=mode.equals("random");CompoundButton button=recycled instanceof CompoundButton?(CompoundButton)recycled:random?new CheckBox(a):new RadioButton(a);String node=getItem(position);boolean selected=random?pool.contains(node):node.equals(entry);
      button.setText(NativeNetwork.display(node));button.setTextSize(14);button.setTextColor(ReferenceUi.TEXT);button.setButtonTintList(ColorStateList.valueOf(ReferenceUi.BLUE));button.setChecked(selected);button.setMinHeight(dp(48));button.setSingleLine(true);button.setEllipsize(android.text.TextUtils.TruncateAt.END);button.setContentDescription(NativeNetwork.display(node));button.setBackground(ReferenceUi.surface(a,selected?0xfff7faff:ReferenceUi.WHITE,12,selected?0xff8fb4ff:ReferenceUi.LINE));button.setPadding(dp(7),0,dp(7),0);
      button.setOnClickListener(v->{if(random){if(button.isChecked())pool.add(node);else pool.remove(node);if(!pool.contains(entry))entry="";updateResult();}else entry=node;notifyDataSetChanged();});return button;
    }
  }
}
