package local.pocketchat;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.LayerDrawable;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.ViewTreeObserver;
import android.widget.FrameLayout;
import java.util.Collections;
import java.util.Set;
import java.util.WeakHashMap;

/** Native page content only. Glass controls are siblings, never part of this source. */
final class GlassBackdrop extends FrameLayout {
  private final Set<View> controls=Collections.newSetFromMap(new WeakHashMap<>());
  private final int[] sourceLocation=new int[2],controlLocation=new int[2];
  private final ViewTreeObserver.OnScrollChangedListener scrollListener=this::sourceChanged;
  private ViewTreeObserver observedTree;
  private boolean glassActive,recording,notifying;
  private long sourceRevision;

  GlassBackdrop(Context context){super(context);}

  void setGlassActive(boolean active){
    if(glassActive==active)return;
    glassActive=active;sourceRevision++;invalidateControls();
  }

  boolean isGlassActive(){
    return glassActive&&isAttachedToWindow()&&isShown()&&getWindowVisibility()==VISIBLE
      &&getWidth()>0&&getHeight()>0;
  }

  long revision(){return sourceRevision;}

  /** Keeps the public navigation views and their click/press dispatch unchanged. */
  void bindControls(View root){
    if(root==null||root==this)return;
    if(bindDrawable(root.getBackground(),root))controls.add(root);
    if(root instanceof ViewGroup){
      ViewGroup group=(ViewGroup)root;
      for(int i=0;i<group.getChildCount();i++)bindControls(group.getChildAt(i));
    }
  }

  private boolean bindDrawable(Drawable drawable,View host){
    if(drawable instanceof LiquidGlassDrawable){
      ((LiquidGlassDrawable)drawable).setBackdrop(this,host);return true;
    }
    boolean found=false;
    if(drawable instanceof LayerDrawable){
      LayerDrawable layers=(LayerDrawable)drawable;
      for(int i=0;i<layers.getNumberOfLayers();i++)found|=bindDrawable(layers.getDrawable(i),host);
    }else if(drawable instanceof InsetDrawable)found=bindDrawable(((InsetDrawable)drawable).getDrawable(),host);
    return found;
  }

  /**
   * Records only this native page into the caller's already bounded render target.
   * The caller owns clearing, clipping, RenderNode allocation and cache lifetime.
   */
  boolean drawBehind(Canvas canvas,View host,float margin){
    if(canvas==null||host==null||recording||!isGlassActive()||!Float.isFinite(margin)
        ||margin<0f||!host.isAttachedToWindow()||!host.isShown()
        ||host.getWidth()<=0||host.getHeight()<=0||host.getWindowToken()!=getWindowToken()
        ||isInsideSource(host))return false;
    getLocationInWindow(sourceLocation);host.getLocationInWindow(controlLocation);
    int saved=canvas.save();recording=true;
    try{
      canvas.translate(margin+sourceLocation[0]-controlLocation[0],margin+sourceLocation[1]-controlLocation[1]);
      super.draw(canvas);return true;
    }finally{recording=false;canvas.restoreToCount(saved);}
  }

  private boolean isInsideSource(View view){
    for(View current=view;current!=null;){
      if(current==this)return true;
      ViewParent parent=current.getParent();current=parent instanceof View?(View)parent:null;
    }
    return false;
  }

  private void sourceChanged(){
    // Recording a source must not itself produce the next glass frame.
    if(recording)return;
    sourceRevision++;
    if(glassActive)invalidateControls();
  }

  private void invalidateControls(){
    if(recording||notifying)return;
    notifying=true;
    try{
      // View invalidations are coalesced by Android; no idle/pre-draw frame pump.
      for(View host:controls)if(host!=null&&host.isAttachedToWindow()&&!isInsideSource(host))host.invalidate();
    }finally{notifying=false;}
  }

  @Override public void onDescendantInvalidated(View child,View target){
    super.onDescendantInvalidated(child,target);sourceChanged();
  }

  @Override public ViewParent invalidateChildInParent(int[] location,Rect dirty){
    ViewParent parent=super.invalidateChildInParent(location,dirty);sourceChanged();return parent;
  }

  @Override public void onViewAdded(View child){super.onViewAdded(child);sourceChanged();}
  @Override public void onViewRemoved(View child){super.onViewRemoved(child);sourceChanged();}

  @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
    super.onLayout(changed,left,top,right,bottom);sourceChanged();
  }

  @Override protected void onAttachedToWindow(){
    super.onAttachedToWindow();observedTree=getViewTreeObserver();
    observedTree.addOnScrollChangedListener(scrollListener);sourceChanged();
  }

  @Override protected void onDetachedFromWindow(){
    if(observedTree!=null&&observedTree.isAlive())observedTree.removeOnScrollChangedListener(scrollListener);
    observedTree=null;super.onDetachedFromWindow();sourceChanged();
  }

  @Override public void onVisibilityAggregated(boolean visible){super.onVisibilityAggregated(visible);sourceChanged();}
  @Override protected void onWindowVisibilityChanged(int visibility){super.onWindowVisibilityChanged(visibility);sourceChanged();}
}
