package local.pocketchat;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.*;

/** Presentation only: network state and configuration stay in NetworkWorkspaceUi. */
final class NetworkWorkspaceStyle {
  private NetworkWorkspaceStyle(){}

  static TextView text(Context context,String value,int size,int color,boolean strong){
    return ReferenceUi.workspaceText(context,value,size,color,strong);
  }

  static void readable(TextView view){
    ReferenceUi.readable(view);
  }

  static Drawable card(Context context,boolean focused){
    // Keep network content on a quiet, theme-aware surface. Optical effects
    // belong to the floating controls, so these cards add no wash or shadow.
    return EnvironmentWorkspaceStyle.card(context,false,focused);
  }

  static Button glassAction(Context context,String glyph,String label,Runnable action){
    Button button=ReferenceUi.iconButton(context,glyph,label,action);
    button.setBackground(DesignUi.glass(context,25));GlassMotion.press(button,true);return button;
  }

  static LinearLayout tabs(Context context,int selected,java.util.function.IntConsumer choose){
    return ReferenceUi.workspaceTabs(context,new String[]{"环境网络","入口","出口"},selected,choose);
  }

  static TextView status(Context context,String label,int color){
    TextView view=text(context,label,ReferenceUi.STATUS_SIZE,color,false);view.setGravity(Gravity.CENTER_VERTICAL);
    view.setCompoundDrawablesRelative(EnvironmentWorkspaceStyle.statusDot(context,color),null,null,null);
    view.setCompoundDrawablePadding(DesignUi.dp(context,6));
    view.setPadding(0,DesignUi.dp(context,3),0,DesignUi.dp(context,3));
    // The visible label carries the state; the small dot is only an accent.
    view.setBackground(null);return view;
  }

  static Button smallAction(Context context,String label,Runnable action){
    Button button=ReferenceUi.link(context,label,action);button.setTextSize(ReferenceUi.ACTION_SIZE);readable(button);
    button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x140067d8),
        new InsetDrawable(DesignUi.surface(context,ReferenceUi.BLUE_SOFT,16,Color.TRANSPARENT),0,DesignUi.dp(context,6),0,DesignUi.dp(context,6)),null));
    button.setPadding(DesignUi.dp(context,12),DesignUi.dp(context,8),DesignUi.dp(context,12),DesignUi.dp(context,8));return button;
  }

  static Button rowAction(Context context,String label,Runnable action){
    Button button=ReferenceUi.link(context,label,action);button.setTextSize(ReferenceUi.ACTION_SIZE);readable(button);
    button.setTextColor(DesignUi.BLUE);button.setContentDescription(label);
    button.setMinWidth(DesignUi.dp(context,48));button.setMinimumWidth(DesignUi.dp(context,48));
    button.setMinHeight(DesignUi.dp(context,48));button.setMinimumHeight(DesignUi.dp(context,48));
    Ui.Icon arrow=new Ui.Icon("chevron-right",DesignUi.BLUE);
    arrow.setBounds(0,0,DesignUi.dp(context,12),DesignUi.dp(context,12));
    button.setCompoundDrawablesRelative(null,null,arrow,null);button.setCompoundDrawablePadding(DesignUi.dp(context,3));
    button.setPadding(DesignUi.dp(context,8),DesignUi.dp(context,8),DesignUi.dp(context,3),DesignUi.dp(context,8));
    return button;
  }

  /** Decorative path only; the adjacent text supplies every route label. */
  static View routeMark(Context context,int index,boolean last){return new RouteMark(context,index,last);}

  private static final class RouteMark extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;
    private final int index;
    private final boolean last;

    RouteMark(Context context,int index,boolean last){
      super(context);this.index=index;this.last=last;
      density=context.getResources().getDisplayMetrics().density;
      setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);setFocusable(false);setClickable(false);
    }

    @Override protected void onMeasure(int widthSpec,int heightSpec){
      setMeasuredDimension(resolveSize(Math.round(20f*density),widthSpec),resolveSize(Math.round(22f*density),heightSpec));
    }

    @Override protected void onDraw(Canvas canvas){
      super.onDraw(canvas);
      float x=getWidth()*.5f,y=Math.min(getHeight()*.5f,11f*density),gap=4f*density;
      paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(density);paint.setColor(DesignUi.LINE);
      if(index>0&&y>gap)canvas.drawLine(x,0,x,y-gap,paint);
      if(!last&&getHeight()>y+gap)canvas.drawLine(x,y+gap,x,getHeight(),paint);
      paint.setColor(index==0?DesignUi.BLUE:DesignUi.MUTED);
      if(index==0)canvas.drawCircle(x,y,2.3f*density,paint);
      else{paint.setStyle(Paint.Style.FILL);canvas.drawCircle(x,y,1.65f*density,paint);}
    }
  }

  static LinearLayout sourceCard(Context context){
    LinearLayout card=DesignUi.column(context);
    card.setPadding(DesignUi.dp(context,16),DesignUi.dp(context,8),DesignUi.dp(context,12),DesignUi.dp(context,14));
    card.setBackground(card(context,false));return card;
  }

  static TextView secondary(Context context,String value){
    TextView view=text(context,value,ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);
    view.setPadding(0,DesignUi.dp(context,3),DesignUi.dp(context,4),0);return view;
  }

  static void empty(LinearLayout box,String title,String detail){
    Context context=box.getContext();LinearLayout state=DesignUi.row(context);state.setGravity(Gravity.TOP);
    state.setPadding(DesignUi.dp(context,18),DesignUi.dp(context,20),DesignUi.dp(context,18),DesignUi.dp(context,20));
    state.setBackground(card(context,false));
    ImageView symbol=DesignUi.icon(context,"globe",DesignUi.BLUE,36);
    symbol.setPadding(DesignUi.dp(context,8),DesignUi.dp(context,8),DesignUi.dp(context,8),DesignUi.dp(context,8));
    Drawable iconFace=DesignUi.surface(context,ReferenceUi.BLUE_SOFT,11,Color.TRANSPARENT);iconFace.setAlpha(150);
    symbol.setBackground(iconFace);
    symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);state.addView(symbol);
    LinearLayout copy=DesignUi.column(context);
    copy.addView(text(context,title,ReferenceUi.EMPTY_TITLE_SIZE,DesignUi.TEXT,true));
    TextView explanation=secondary(context,detail);explanation.setPadding(0,DesignUi.dp(context,5),0,0);copy.addView(explanation);
    LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(0,-2,1);params.leftMargin=DesignUi.dp(context,12);state.addView(copy,params);
    ReferenceUi.add(box,state);
  }
}
