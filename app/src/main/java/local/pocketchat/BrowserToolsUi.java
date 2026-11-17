package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;

/** Page actions share a native sheet; each engine supplies only its real actions. */
final class BrowserToolsUi {
  final Activity activity;
  final ReferenceUi.Modal panel;
  final ActionGrid navigation,tools;
  private Button backButton,forwardButton,reloadButton;

  BrowserToolsUi(Activity activity,String description){
    this.activity=activity;panel=new ReferenceUi.Modal(activity,"网页工具").asSheet();
    if(description!=null&&!description.isEmpty()){
      TextView caption=ReferenceUi.secondary(activity,description);caption.setMaxLines(2);panel.body.addView(caption);
    }
    navigation=new ActionGrid(activity,3,64);tools=new ActionGrid(activity,4,76);
    navigation.setPadding(0,ReferenceUi.dp(activity,8),0,ReferenceUi.dp(activity,8));
    panel.body.addView(navigation,new LinearLayout.LayoutParams(-1,-2));
    panel.body.addView(tools,new LinearLayout.LayoutParams(-1,-2));
  }

  void navigation(boolean canBack,Runnable back,boolean canForward,Runnable forward,boolean loading,Runnable reload){
    backButton=add(navigation,"back","后退",canBack,back);
    forwardButton=add(navigation,"chevron-right","前进",canForward,forward);
    reloadButton=add(navigation,loading?"close":"refresh",loading?"停止加载":"刷新网页",true,reload);
    navigationState(canBack,canForward,loading);
  }
  void navigationState(boolean canBack,boolean canForward,boolean loading){
    if(backButton==null)return;
    backButton.setEnabled(canBack);backButton.setAlpha(canBack?1f:.38f);
    forwardButton.setEnabled(canForward);forwardButton.setAlpha(canForward?1f:.38f);
    String label=loading?"停止加载":"刷新网页";
    if(!label.contentEquals(reloadButton.getText())){reloadButton.setText(label);reloadButton.setContentDescription(label);}
    android.graphics.drawable.Drawable drawable=reloadButton.getCompoundDrawables()[1];
    if(drawable instanceof Ui.Icon){Ui.Icon icon=(Ui.Icon)drawable;String glyph=loading?"close":"refresh";if(!glyph.equals(icon.name)){icon.name=glyph;reloadButton.invalidate();}}
  }

  Button action(String glyph,String label,Runnable run){return add(tools,glyph,label,true,run);}
  private Button add(ActionGrid parent,String glyph,String label,boolean enabled,Runnable run){
    Button button=ReferenceUi.link(activity,label,()->{panel.dismiss();if(!activity.isFinishing()&&!activity.isDestroyed())run.run();});
    button.setTextColor(ReferenceUi.TEXT);button.setTextSize(13);button.setGravity(Gravity.CENTER);
    button.setSingleLine(false);button.setMaxLines(Integer.MAX_VALUE);ReferenceUi.readable(button);
    button.setMinWidth(ReferenceUi.dp(activity,48));button.setMinimumWidth(ReferenceUi.dp(activity,48));
    button.setMinHeight(ReferenceUi.dp(activity,80));button.setMinimumHeight(ReferenceUi.dp(activity,80));
    button.setPadding(ReferenceUi.dp(activity,4),ReferenceUi.dp(activity,10),ReferenceUi.dp(activity,4),ReferenceUi.dp(activity,10));
    Ui.Icon icon=new Ui.Icon(glyph,ReferenceUi.TEXT);icon.setBounds(0,0,ReferenceUi.dp(activity,24),ReferenceUi.dp(activity,24));
    button.setCompoundDrawables(null,icon,null,null);button.setCompoundDrawablePadding(ReferenceUi.dp(activity,8));
    button.setContentDescription(label);button.setEnabled(enabled);parent.addView(button);return button;
  }
  void show(){panel.show();}

  /** Text can grow or wrap; cell height follows native measurement, not a fixed grid. */
  static final class ActionGrid extends ViewGroup {
    final int maximumColumns,minimumWidth;int columns=1;final List<Integer> rowHeights=new ArrayList<>();
    ActionGrid(Context context,int maximumColumns,int minimumWidth){super(context);this.maximumColumns=maximumColumns;this.minimumWidth=minimumWidth;setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);}
    private int dp(int value){return ReferenceUi.dp(getContext(),value);}
    @Override protected void onMeasure(int widthSpec,int heightSpec){
      int width=resolveSize(dp(maximumColumns*minimumWidth),widthSpec),available=Math.max(0,width-getPaddingLeft()-getPaddingRight());
      float font=getResources().getConfiguration().fontScale;
      int minimum=dp(Math.round(minimumWidth*Math.max(1f,Math.min(1.6f,font))));
      columns=Math.min(maximumColumns,Math.max(1,available/Math.max(dp(48),minimum)));
      int cell=available/columns,total=getPaddingTop()+getPaddingBottom();rowHeights.clear();
      for(int start=0;start<getChildCount();start+=columns){
        int height=0;
        for(int i=start;i<Math.min(getChildCount(),start+columns);i++){
          View child=getChildAt(i);child.measure(MeasureSpec.makeMeasureSpec(cell,MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));height=Math.max(height,child.getMeasuredHeight());
        }
        rowHeights.add(height);total+=height;
      }
      setMeasuredDimension(width,resolveSize(total,heightSpec));
    }
    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
      int width=right-left,available=width-getPaddingLeft()-getPaddingRight(),y=getPaddingTop(),index=0;
      for(int height:rowHeights){
        for(int column=0;column<columns&&index<getChildCount();column++){
          int x=getPaddingLeft()+available*column/columns,end=getPaddingLeft()+available*(column+1)/columns;
          if(getLayoutDirection()==View.LAYOUT_DIRECTION_RTL)getChildAt(index++).layout(width-end,y,width-x,y+height);
          else getChildAt(index++).layout(x,y,end,y+height);
        }
        y+=height;
      }
    }
  }
}
