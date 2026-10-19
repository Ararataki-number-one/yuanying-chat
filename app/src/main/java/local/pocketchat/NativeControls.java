package local.pocketchat;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.util.*;

/** Native form details shared by workspaces, secondary dialogs and system-style lists. */
final class NativeControls {
  private static final Set<View> prepared=Collections.newSetFromMap(new WeakHashMap<>());
  static int height(TextView text,int minimum,int verticalPadding){
    android.graphics.Paint.FontMetrics f=text.getPaint().getFontMetrics();
    return Math.max(Ui.dp(text.getContext(),minimum),(int)Math.ceil(f.bottom-f.top)+Ui.dp(text.getContext(),verticalPadding));
  }
  static void prepare(View view){
    if(!prepared.add(view))return;
    Context c=view.getContext();
    if(view instanceof EditText){
      EditText input=(EditText)view;
      input.setTextColor(DesignUi.TEXT);input.setHintTextColor(DesignUi.MUTED);
      input.setTextSize(16);input.setIncludeFontPadding(false);
      input.setPadding(Ui.dp(c,14),Ui.dp(c,12),Ui.dp(c,14),Ui.dp(c,12));
      input.setMinHeight(height(input,50,24));input.setBackground(new Field(c));
      if(input.getId()==View.NO_ID)input.setId(View.generateViewId());
    }else if(view instanceof CompoundButton){
      CompoundButton control=(CompoundButton)view;
      control.setTextSize(15);control.setTextColor(DesignUi.TEXT);
      control.setMinHeight(Math.max(control.getMinimumHeight(),height(control,50,20)));
      control.setGravity(Gravity.CENTER_VERTICAL|Gravity.START);
      control.setPadding(Math.max(control.getPaddingLeft(),Ui.dp(c,4)),Ui.dp(c,10),Math.max(control.getPaddingRight(),Ui.dp(c,8)),Ui.dp(c,10));
      if(control instanceof Switch)((Switch)control).setSwitchPadding(Ui.dp(c,16));
    }else if(view instanceof Button&&!(view instanceof DesignUi.ActionButton)&&!(view instanceof Ui.IconButton)){
      Button button=(Button)view;button.setAllCaps(false);button.setTextSize(15);button.setMinHeight(height(button,48,16));
    }else if(view instanceof Spinner){
      Spinner spinner=(Spinner)view;spinner.setMinimumHeight(Ui.dp(c,50));
      spinner.setPadding(Ui.dp(c,10),Ui.dp(c,4),Ui.dp(c,10),Ui.dp(c,4));
      android.graphics.drawable.LayerDrawable background=new android.graphics.drawable.LayerDrawable(new android.graphics.drawable.Drawable[]{DesignUi.surface(c,DesignUi.FIELD,12,DesignUi.LINE),new Ui.Icon("chevron",DesignUi.MUTED)});
      background.setLayerSize(1,Ui.dp(c,16),Ui.dp(c,16));background.setLayerGravity(1,Gravity.END|Gravity.CENTER_VERTICAL);background.setLayerInset(1,0,0,Ui.dp(c,12),0);spinner.setBackground(background);
      if(Build.VERSION.SDK_INT>=29)spinner.setPopupBackgroundDrawable(DesignUi.surface(c,DesignUi.CARD,14,DesignUi.LINE));
    }else if(view instanceof ScrollView||view instanceof HorizontalScrollView){
      view.setScrollBarStyle(View.SCROLLBARS_INSIDE_OVERLAY);
      view.setVerticalScrollBarEnabled(false);view.setHorizontalScrollBarEnabled(false);
      view.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);
      if(view instanceof ScrollView)((ScrollView)view).setClipToPadding(false);
    }
  }
  static void form(View root){
    List<EditText> fields=new ArrayList<>();collect(root,fields);
    for(int i=0;i<fields.size();i++){
      EditText input=fields.get(i);if(input.getMaxLines()!=1)continue;
      int action=i==fields.size()-1?EditorInfo.IME_ACTION_DONE:EditorInfo.IME_ACTION_NEXT;
      input.setImeOptions((input.getImeOptions()&~EditorInfo.IME_MASK_ACTION)|action);
      if(i+1<fields.size())input.setNextFocusForwardId(fields.get(i+1).getId());
    }
  }
  private static void collect(View view,List<EditText> out){
    if(view.getVisibility()!=View.VISIBLE)return;
    if(view instanceof GeckoWebView||view instanceof org.mozilla.geckoview.GeckoView||view instanceof android.webkit.WebView)return;
    if(view instanceof EditText){prepare(view);if(view.getVisibility()==View.VISIBLE)out.add((EditText)view);}
    if(view instanceof ViewGroup&&!(view instanceof android.webkit.WebView)&&!(view instanceof org.mozilla.geckoview.GeckoView)){
      ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)collect(group.getChildAt(i),out);
    }
  }
  static final class Field extends GradientDrawable {
    final int edge;boolean focused,enabled=true;
    Field(Context c){edge=Math.max(1,Ui.dp(c,1));setCornerRadius(Ui.dp(c,12));refresh();}
    void refresh(){setColor(DesignUi.FIELD);setStroke(focused?edge*2:edge,focused?DesignUi.BLUE:DesignUi.LINE);setAlpha(enabled?255:140);}
    @Override public boolean isStateful(){return true;}
    @Override protected boolean onStateChange(int[] states){
      focused=false;enabled=false;for(int state:states){if(state==android.R.attr.state_focused)focused=true;if(state==android.R.attr.state_enabled)enabled=true;}
      refresh();return true;
    }
  }
}
