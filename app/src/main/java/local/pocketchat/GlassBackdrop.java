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
import java.lang.ref.WeakReference;
import java.util.Collections;
import java.util.Set;
import java.util.WeakHashMap;

/** Native page and its scroll-edge fade. Glass controls never enter this source. */
final class GlassBackdrop extends FrameLayout {
  private final Set<View> controls=Collections.newSetFromMap(new WeakHashMap<>());
  private final int[] sourceLocation=new int[2],controlLocation=new int[2],edgeLocation=new int[2];
  private final ViewTreeObserver.OnScrollChangedListener scrollListener=this::sourceChanged;
  private final OnLayoutChangeListener edgeLayoutListener=(v,l,t,r,b,ol,ot,or,ob)->{
    if(l!=ol||t!=ot||r!=or||b!=ob)sourceChanged();
  };
  private ViewTreeObserver observedTree;
  private WeakReference<View> scrollEdge;
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

  /** Share the visible native scroll-edge background without recording its controls. */
  void setScrollEdge(View edge){
    View previous=scrollEdge==null?null:scrollEdge.get();
    if(previous!=edge){
      if(previous!=null)previous.removeOnLayoutChangeListener(edgeLayoutListener);
      scrollEdge=edge==null?null:new WeakReference<>(edge);
      if(edge!=null&&isAttachedToWindow())edge.addOnLayoutChangeListener(edgeLayoutListener);
    }
    // Palette changes may replace the background while retaining the same View.
    sourceChanged();
  }

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
   * Records this native page and its scroll-edge fade into the bounded target.
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
      super.draw(canvas);drawScrollEdge(canvas);return true;
    }finally{recording=false;canvas.restoreToCount(saved);}
  }

  private void drawScrollEdge(Canvas canvas){
    View edge=scrollEdge==null?null:scrollEdge.get();
    if(edge==null||!edge.isAttachedToWindow()||!edge.isShown()
        ||edge.getWindowToken()!=getWindowToken()||isInsideSource(edge))return;
    Drawable background=edge.getBackground();
    if(background==null||edge.getWidth()<=0||edge.getHeight()<=0)return;
    edge.getLocationInWindow(edgeLocation);
    int saved=canvas.save();
    try{
      canvas.translate(edgeLocation[0]-sourceLocation[0],edgeLocation[1]-sourceLocation[1]);
      canvas.clipRect(0,0,edge.getWidth(),edge.getHeight());
      // Only the existing background is drawn: no footer, glyphs or feedback.
      // Text faded outside the lens must not reappear dark inside the lens.
      background.draw(canvas);
    }finally{canvas.restoreToCount(saved);}
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
    View edge=scrollEdge==null?null:scrollEdge.get();
    if(edge!=null)edge.addOnLayoutChangeListener(edgeLayoutListener);
    observedTree.addOnScrollChangedListener(scrollListener);sourceChanged();
  }

  @Override protected void onDetachedFromWindow(){
    if(observedTree!=null&&observedTree.isAlive())observedTree.removeOnScrollChangedListener(scrollListener);
    View edge=scrollEdge==null?null:scrollEdge.get();
    if(edge!=null)edge.removeOnLayoutChangeListener(edgeLayoutListener);
    observedTree=null;super.onDetachedFromWindow();sourceChanged();
  }

  @Override public void onVisibilityAggregated(boolean visible){super.onVisibilityAggregated(visible);sourceChanged();}
  @Override protected void onWindowVisibilityChanged(int visibility){super.onWindowVisibilityChanged(visibility);sourceChanged();}
}
