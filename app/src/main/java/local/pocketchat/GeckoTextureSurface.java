package local.pocketchat;

import android.graphics.SurfaceTexture;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;

/** Keeps Gecko's surface lifecycle separate from already displayed content frames. */
final class GeckoTextureSurface implements TextureView.SurfaceTextureListener,AutoCloseable {
  private final TextureView view;
  private final TextureView.SurfaceTextureListener delegate;
  private SurfaceTexture texture;
  private int width,height;
  private boolean closed,replacementRequested;

  private GeckoTextureSurface(TextureView view,TextureView.SurfaceTextureListener delegate){
    this.view=view;this.delegate=delegate;
    if(view.isAvailable())remember(view.getSurfaceTexture(),view.getWidth(),view.getHeight());
  }

  static GeckoTextureSurface install(ViewGroup surface,GeckoTextureSurface previous){
    TextureView target=null;
    if(surface!=null)for(int index=0;index<surface.getChildCount();index++){
      View child=surface.getChildAt(index);if(child instanceof TextureView){target=(TextureView)child;break;}
    }
    if(previous!=null&&previous.current(target))return previous;
    if(previous!=null)previous.close();
    if(target==null)return null;
    TextureView.SurfaceTextureListener listener=target.getSurfaceTextureListener();
    if(listener instanceof GeckoTextureSurface&&((GeckoTextureSurface)listener).current(target))return (GeckoTextureSurface)listener;
    if(listener==null)return null;
    GeckoTextureSurface binding=new GeckoTextureSurface(target,listener);
    target.setSurfaceTextureListener(binding);return binding;
  }

  private boolean current(TextureView target){return !closed&&view==target&&view.getSurfaceTextureListener()==this;}
  private void remember(SurfaceTexture value,int w,int h){texture=value;width=w;height=h;}

  static void requestNewSurface(ViewGroup surface){
    if(surface==null)return;
    for(int index=0;index<surface.getChildCount();index++){
      View child=surface.getChildAt(index);if(!(child instanceof TextureView))continue;
      TextureView target=(TextureView)child;
      TextureView.SurfaceTextureListener listener=target.getSurfaceTextureListener();
      if(listener instanceof GeckoTextureSurface){
        GeckoTextureSurface binding=(GeckoTextureSurface)listener;
        if(binding.current(target))binding.replacementRequested=true;
      }
      return;
    }
  }

  @Override public void onSurfaceTextureAvailable(SurfaceTexture value,int w,int h){
    if(!current(view)||view.getSurfaceTexture()!=value)return;
    replacementRequested=false;remember(value,w,h);delegate.onSurfaceTextureAvailable(value,w,h);
  }

  @Override public void onSurfaceTextureSizeChanged(SurfaceTexture value,int w,int h){
    if(!current(view)||view.getSurfaceTexture()!=value)return;
    remember(value,w,h);delegate.onSurfaceTextureSizeChanged(value,w,h);
  }

  @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture value){
    if(!current(view)||texture!=value)return false;
    // Clear ownership before the original callback can synchronously bind a new surface.
    replacementRequested=false;remember(null,0,0);return delegate.onSurfaceTextureDestroyed(value);
  }

  @Override public void onSurfaceTextureUpdated(SurfaceTexture value){
    if(!current(view)||!view.isAvailable()||view.getSurfaceTexture()!=value)return;
    int w=view.getWidth(),h=view.getHeight();
    // Android has already consumed this content buffer. Gecko 157's listener
    // recreates Surface and resumes/resizes its compositor for every update;
    // that resume requests another draw even when the document is unchanged.
    // Available/size/destroy callbacks above still carry the real lifecycle.
    // The SDK's explicit invalid-surface recovery still posts its visibility
    // toggle. Its next update must create a new Surface even at the same size.
    if(!replacementRequested&&texture==value&&width==w&&height==h)return;
    replacementRequested=false;remember(value,w,h);delegate.onSurfaceTextureUpdated(value);
  }

  @Override public void close(){
    if(closed)return;closed=true;replacementRequested=false;remember(null,0,0);
    // A later backend/owner may have installed its own listener already.
    if(view.getSurfaceTextureListener()==this)view.setSurfaceTextureListener(delegate);
  }
}
