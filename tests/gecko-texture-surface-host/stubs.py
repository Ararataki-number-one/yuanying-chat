"""Declared Android rendering boundary; no Android or GPU execution is claimed."""
SOURCES = {
 'android/content/Context.java': 'package android.content; public class Context {}',
 'android/graphics/Color.java': 'package android.graphics; public class Color {public static final int TRANSPARENT=0;}',
 'android/graphics/PixelFormat.java': 'package android.graphics; public class PixelFormat {public static final int TRANSPARENT=-3;}',
 'android/graphics/Rect.java': 'package android.graphics; public class Rect {public int right=400,bottom=800;}',
 'android/graphics/SurfaceTexture.java': 'package android.graphics; public class SurfaceTexture {public final int identity;public boolean released;public SurfaceTexture(int identity){this.identity=identity;}public void release(){released=true;}}',
 'android/os/Build.java': 'package android.os; public class Build {public static class VERSION {public static int SDK_INT=35;}public static class VERSION_CODES {public static final int Q=29;}}',
 'android/util/Log.java': 'package android.util; public class Log {public static int e(String tag,String text){return 0;}}',
 'android/view/SurfaceControl.java': 'package android.view; public class SurfaceControl {}',
 'android/view/Surface.java': '''package android.view;import android.graphics.SurfaceTexture;
public class Surface {public static int allocations;public final SurfaceTexture texture;public Surface(SurfaceTexture texture){allocations++;this.texture=texture;}}''',
 'android/view/View.java': '''package android.view;import android.content.Context;
public class View {public static final int INVISIBLE=4,VISIBLE=0;protected int width=400,height=800;final Context context;public int visibilityChanges;int visibility=VISIBLE;final java.util.ArrayDeque<Runnable> posted=new java.util.ArrayDeque<>();public View(Context context){this.context=context;}public Context getContext(){return context;}public int getWidth(){return width;}public int getHeight(){return height;}public void size(int w,int h){width=w;height=h;}public void setBackgroundColor(int color){}public void setVisibility(int value){if(visibility!=value){visibilityChanges++;visibility=value;}}public int getVisibility(){return visibility;}public boolean post(Runnable call){posted.add(call);return true;}public int postedCount(){return posted.size();}public void dispatchPosted(){int count=0;while(!posted.isEmpty()){if(++count>20)throw new IllegalStateException("unbounded callback loop");posted.remove().run();}}}''',
 'android/view/ViewGroup.java': '''package android.view;import android.content.Context;import java.util.*;
public class ViewGroup extends View {final List<View> children=new ArrayList<>();public ViewGroup(Context context){super(context);}public int getChildCount(){return children.size();}public View getChildAt(int index){return children.get(index);}public void addView(View view){children.add(view);}public void removeAllViews(){children.clear();}}''',
 'android/view/SurfaceHolder.java': '''package android.view;import android.graphics.Rect;
public interface SurfaceHolder {void setFormat(int format);void addCallback(Callback callback);Surface getSurface();Rect getSurfaceFrame();interface Callback {void surfaceCreated(SurfaceHolder holder);void surfaceChanged(SurfaceHolder holder,int format,int width,int height);void surfaceDestroyed(SurfaceHolder holder);}}''',
 'android/view/SurfaceView.java': '''package android.view;import android.content.Context;import android.graphics.Rect;
public class SurfaceView extends View {final SurfaceHolder holder=new SurfaceHolder(){public void setFormat(int format){}public void addCallback(Callback callback){}public Surface getSurface(){return null;}public Rect getSurfaceFrame(){return new Rect();}};public SurfaceView(Context c){super(c);}public SurfaceHolder getHolder(){return holder;}public SurfaceControl getSurfaceControl(){return null;}}''',
 'org/mozilla/gecko/MagnifiableSurfaceView.java': 'package org.mozilla.gecko;public class MagnifiableSurfaceView extends android.view.SurfaceView {public MagnifiableSurfaceView(android.content.Context c){super(c);}}',
 'android/view/TextureView.java': '''package android.view;import android.content.Context;import android.graphics.SurfaceTexture;
public class TextureView extends View {
 public interface SurfaceTextureListener {void onSurfaceTextureAvailable(SurfaceTexture texture,int width,int height);void onSurfaceTextureSizeChanged(SurfaceTexture texture,int width,int height);boolean onSurfaceTextureDestroyed(SurfaceTexture texture);void onSurfaceTextureUpdated(SurfaceTexture texture);}
 SurfaceTextureListener listener;SurfaceTexture texture;boolean available;public int displayedFrames;public String displayedContent="";
 public TextureView(Context context){super(context);}public void setSurfaceTextureListener(SurfaceTextureListener value){listener=value;}public SurfaceTextureListener getSurfaceTextureListener(){return listener;}public SurfaceTexture getSurfaceTexture(){return texture;}public boolean isAvailable(){return available;}
 public void available(SurfaceTexture next,int w,int h){texture=next;available=true;size(w,h);if(listener!=null)listener.onSurfaceTextureAvailable(next,w,h);}
 public void resize(int w,int h){size(w,h);if(listener!=null)listener.onSurfaceTextureSizeChanged(texture,w,h);}
 public void replaceWithoutAvailable(SurfaceTexture next){texture=next;available=true;}
 // AOSP calls the listener while the old texture is still available, then releases/clears it.
 public boolean destroy(){SurfaceTexture previous=texture;boolean release=listener==null||listener.onSurfaceTextureDestroyed(previous);if(release&&previous!=null)previous.release();texture=null;available=false;return release;}
 // Android consumes/displays the new buffer independently of this listener.
 public void present(String content){displayedFrames++;displayedContent=content;if(listener!=null)listener.onSurfaceTextureUpdated(texture);}
}
''',
}
