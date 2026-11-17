package local.pocketchat;

import android.content.Context;
import android.text.TextUtils;
import android.view.View;
import android.view.ViewGroup;
import android.view.Gravity;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.TextView;

/** Native browser actions share the existing glass material and press feedback. */
final class BrowserToolbarUi {
  private BrowserToolbarUi() {}

  static Button action(Context context,String glyph,String label,Runnable run){
    Button button=ReferenceUi.iconButton(context,glyph,label,run);
    button.setBackground(DesignUi.glass(context,24));
    GlassMotion.press(button,false);
    return button;
  }

  static void action(Button button,String glyph,String label){
    if(button instanceof Ui.IconButton){
      Ui.Icon icon=((Ui.IconButton)button).icon;
      if(!glyph.equals(icon.name)){icon.name=glyph;button.invalidate();}
    }
    if(!TextUtils.equals(button.getContentDescription(),label)){
      button.setContentDescription(label);button.setTooltipText(label);
    }
  }

  static void enabled(Button button,boolean enabled){
    if(button.isEnabled()!=enabled)button.setEnabled(enabled);
  }

  /** The small glass face and its larger native hit region have separate geometry. */
  static final class EnvironmentButton extends FrameLayout {
    final TextView label;
    EnvironmentButton(Context context,TextView label,Runnable choose){
      super(context);this.label=label;setMinimumHeight(ReferenceUi.dp(context,48));
      setPadding(0,ReferenceUi.dp(context,2),0,ReferenceUi.dp(context,2));
      setClipChildren(false);setClipToPadding(false);setFocusable(true);setLongClickable(false);
      label.setDuplicateParentStateEnabled(true);label.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      addView(label,new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL));
      setOnClickListener(view->choose.run());
    }
    @Override public void drawableHotspotChanged(float x,float y){super.drawableHotspotChanged(x,y);if(label!=null&&label.getBackground()!=null)label.getBackground().setHotspot(x-label.getLeft(),y-label.getTop());}
    @Override public CharSequence getAccessibilityClassName(){return Button.class.getName();}
    @Override public void onInitializeAccessibilityNodeInfo(AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(info);info.setText(label.getText());info.addAction(new AccessibilityNodeInfo.AccessibilityAction(AccessibilityNodeInfo.ACTION_CLICK,"切换环境"));}
  }

  /** Both engines share the same address material and system font scaling. */
  static void address(TextView view){
    Context context=view.getContext();
    view.setTextSize(14);view.setSingleLine(true);view.setIncludeFontPadding(true);
    if(android.os.Build.VERSION.SDK_INT>=28)view.setFallbackLineSpacing(true);
    view.setTextColor(DesignUi.GLASS_INK);view.setHintTextColor(DesignUi.GLASS_MUTED);
    view.setMinWidth(0);view.setMinimumWidth(0);view.setMinHeight(ReferenceUi.dp(context,48));view.setMinimumHeight(ReferenceUi.dp(context,48));
    view.setPadding(ReferenceUi.dp(context,12),ReferenceUi.dp(context,8),ReferenceUi.dp(context,12),ReferenceUi.dp(context,8));
    view.setBackground(DesignUi.glass(context,24));
  }

  /**
   * Five genuine browser controls, with the address receiving all spare width.
   * Long URLs and larger text use the address editor instead of forcing a second
   * toolbar row. Only an exceptionally narrow window stacks the address, so no
   * action loses its 48 dp target. Measuring never replaces or reparents views.
   */
  static final class NavigationBar extends ViewGroup {
    final TextView address;final Button[] actions;boolean stacked;
    NavigationBar(Context context,TextView address,Button home,Button windows,Button tools,Button menu){
      super(context);this.address=address;actions=new Button[]{home,windows,tools,menu};
      addView(home);addView(windows);addView(address);addView(tools);addView(menu);
      setPadding(dp(4),dp(6),dp(4),dp(8));setClipChildren(false);setClipToPadding(false);
      setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    }
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    @Override protected void onMeasure(int widthSpec,int heightSpec){
      int action=dp(48),gap=dp(4),minimum=dp(72);
      int width=resolveSize(getPaddingLeft()+getPaddingRight()+4*action+2*gap+minimum,widthSpec);
      int available=Math.max(0,width-getPaddingLeft()-getPaddingRight());
      stacked=available<4*action+2*gap+minimum;
      int addressWidth=stacked?available:available-4*action-2*gap;
      address.measure(MeasureSpec.makeMeasureSpec(addressWidth,MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));
      int actionSpec=MeasureSpec.makeMeasureSpec(action,MeasureSpec.EXACTLY);
      for(Button button:actions)button.measure(actionSpec,actionSpec);
      int content=stacked?address.getMeasuredHeight()+gap+action:Math.max(address.getMeasuredHeight(),action);
      setMeasuredDimension(width,resolveSize(getPaddingTop()+content+getPaddingBottom(),heightSpec));
    }
    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
      int start=getPaddingLeft(),end=right-left-getPaddingRight(),y=getPaddingTop();
      int action=actions[0].getMeasuredWidth(),gap=dp(4),addressHeight=address.getMeasuredHeight();
      int content=stacked?addressHeight:Math.max(addressHeight,action);
      int addressTop=y+(content-addressHeight)/2;
      int addressLeft=stacked?start:start+2*action+gap;
      place(address,addressLeft,addressTop,stacked?end:end-2*action-gap,addressTop+addressHeight,right-left);
      int actionTop=stacked?y+addressHeight+gap:y+(content-action)/2;
      for(int i=0;i<actions.length;i++){
        int x=stacked?start+(end-start-action)*i/3:i<2?start+i*action:end-(4-i)*action;
        place(actions[i],x,actionTop,x+action,actionTop+action,right-left);
      }
    }
    private void place(View view,int left,int top,int right,int bottom,int width){
      if(getLayoutDirection()==View.LAYOUT_DIRECTION_RTL)view.layout(width-right,top,width-left,bottom);
      else view.layout(left,top,right,bottom);
    }
  }
}
