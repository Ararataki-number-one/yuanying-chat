package local.pocketchat;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;

/** Centers the three destinations independently of the trailing reading action. */
final class GlassNavigationRow extends ViewGroup {
  private final GlassDock dock;
  private final View reading;
  private final int controlHeight,preferredDockWidth,gap,minTarget;
  private boolean stacked;

  GlassNavigationRow(Context context,GlassDock dock,View reading,int controlHeight){
    super(context);this.dock=dock;this.reading=reading;this.controlHeight=controlHeight;
    float scale=Math.max(1f,context.getResources().getConfiguration().fontScale);
    preferredDockWidth=Ui.dp(context,Math.round(228+36*(scale-1f)));
    gap=Ui.dp(context,8);minTarget=Ui.dp(context,48);
    setClipChildren(false);setClipToPadding(false);
    addView(dock,new LayoutParams(LayoutParams.WRAP_CONTENT,controlHeight));
    addView(reading,new LayoutParams(controlHeight,controlHeight));
  }

  @Override protected void onMeasure(int widthSpec,int heightSpec){
    int minimumAction=minTarget;
    int childHeight=Math.max(0,controlHeight-dock.getPaddingTop()-dock.getPaddingBottom());
    // Measure the native labels before choosing a row width. Large text keeps
    // its natural width and every action keeps at least a 48 dp touch target.
    for(int i=0;i<dock.getChildCount();i++){
      View child=dock.getChildAt(i);
      child.measure(MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED),
        MeasureSpec.makeMeasureSpec(childHeight,MeasureSpec.EXACTLY));
      minimumAction=Math.max(minimumAction,child.getMeasuredWidth());
    }
    int minimum=dock.getPaddingLeft()+dock.getPaddingRight()+minimumAction*dock.getChildCount();
    int desired=Math.max(preferredDockWidth,minimum)+2*(controlHeight+gap);
    int width=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED
      ?desired:MeasureSpec.getSize(widthSpec);
    // Equal space on both sides keeps the destination pill on the screen axis.
    // The left space is empty; it is not a hidden or inaccessible fake control.
    int centeredRoom=width-2*(controlHeight+gap);
    stacked=centeredRoom<minimum;
    int dockWidth=Math.max(0,Math.min(Math.max(preferredDockWidth,minimum),stacked?width:centeredRoom));
    dock.measure(MeasureSpec.makeMeasureSpec(dockWidth,MeasureSpec.EXACTLY),
      MeasureSpec.makeMeasureSpec(controlHeight,MeasureSpec.EXACTLY));
    reading.measure(MeasureSpec.makeMeasureSpec(controlHeight,MeasureSpec.EXACTLY),
      MeasureSpec.makeMeasureSpec(controlHeight,MeasureSpec.EXACTLY));
    int height=stacked?controlHeight*2+gap:controlHeight;
    setMeasuredDimension(resolveSizeAndState(width,widthSpec,0),resolveSizeAndState(height,heightSpec,0));
  }

  @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
    int width=right-left,dockLeft=(width-dock.getMeasuredWidth())/2;
    dock.layout(dockLeft,0,dockLeft+dock.getMeasuredWidth(),controlHeight);
    int readingLeft=getLayoutDirection()==LAYOUT_DIRECTION_RTL?0:width-controlHeight;
    int readingTop=stacked?controlHeight+gap:0;
    reading.layout(readingLeft,readingTop,readingLeft+controlHeight,readingTop+controlHeight);
  }
}
