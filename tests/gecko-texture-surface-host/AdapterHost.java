package local.pocketchat;

import android.content.Context;
import android.graphics.SurfaceTexture;
import android.view.*;
import org.json.*;
import org.mozilla.gecko.SurfaceViewWrapper;

/** The complete application adapter plus the unmodified SDK surface wrapper. */
public final class AdapterHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(new JSONObject().put("name",name).put("pass",pass));}
  static final class Sink implements SurfaceViewWrapper.Listener {
    int resets,destroyed,width,height;Surface surface;Runnable change,destroy;
    public void onSurfaceChanged(Surface next,SurfaceControl control,int w,int h){
      resets++;surface=next;width=w;height=h;Runnable call=change;change=null;if(call!=null)call.run();
    }
    public void onSurfaceDestroyed(){destroyed++;Runnable call=destroy;destroy=null;if(call!=null)call.run();}
  }
  static final class Scene {
    final Context context=new Context();final ViewGroup view=new ViewGroup(context);
    final SurfaceViewWrapper sdk=new SurfaceViewWrapper(context);final Sink sink=new Sink();
    final TextureView texture;final TextureView.SurfaceTextureListener original;
    GeckoTextureSurface binding;SurfaceTexture image=new SurfaceTexture(1);
    Scene(){this(true);}
    Scene(boolean early){
      sdk.setListener(sink);sdk.useTextureView(context);sink.destroyed=0;
      texture=(TextureView)sdk.getView();original=texture.getSurfaceTextureListener();view.addView(texture);
      if(early)install();texture.available(image,400,800);if(!early)install();
    }
    void install(){binding=GeckoTextureSurface.install(view,binding);}
    void present(int count){for(int i=0;i<count;i++)texture.present("document update "+i);}
  }
  static final class Listener implements TextureView.SurfaceTextureListener {
    int available,resized,destroyed,updated;boolean release;Runnable destroy,receive;
    public void onSurfaceTextureAvailable(SurfaceTexture t,int w,int h){available++;Runnable call=receive;receive=null;if(call!=null)call.run();}
    public void onSurfaceTextureSizeChanged(SurfaceTexture t,int w,int h){resized++;}
    public boolean onSurfaceTextureDestroyed(SurfaceTexture t){destroyed++;Runnable call=destroy;destroy=null;if(call!=null)call.run();return release;}
    public void onSurfaceTextureUpdated(SurfaceTexture t){updated++;}
  }
  static void stableContent(){
    Scene s=new Scene();Surface initial=s.sink.surface;int allocations=Surface.allocations;
    s.present(120);
    check("Repeated content frames do not resubmit the same SDK surface",s.sink.resets==1);
    check("Repeated content frames do not allocate replacement Surface objects",Surface.allocations==allocations);
    check("The native listener retains the original available surface",s.sink.surface==initial&&s.sdk.getSurface()==initial);
    check("Every actual content notification still reaches the TextureView presentation boundary",s.texture.displayedFrames==120&&s.texture.displayedContent.equals("document update 119"));
    check("The original texture and dimensions remain usable",s.texture.getSurfaceTexture()==s.image&&s.sink.width==400&&s.sink.height==800);
    GeckoTextureSurface binding=s.binding;s.install();s.install();
    check("Repeated installation preserves the same listener binding",s.binding==binding&&s.texture.getSurfaceTextureListener()==binding);
    GeckoTextureSurface rediscovered=GeckoTextureSurface.install(s.view,null);
    check("An existing live listener is rediscovered without nesting wrappers",rediscovered==binding);
    s.texture.resize(700,400);
    check("A real size change reaches the original SDK with exact dimensions",s.sink.resets==2&&s.sink.width==700&&s.sink.height==400);
    check("Size changes preserve the real underlying surface identity",s.sink.surface==initial&&s.sdk.getWidth()==700&&s.sdk.getHeight()==400);
    s.present(8);check("Content after resize remains independent of surface notifications",s.sink.resets==2&&s.texture.displayedFrames==128);
    s.texture.resize(700,400);
    check("Explicit SDK size callbacks remain transparent even when dimensions repeat",s.sink.resets==3);
  }
  static void replacement(){
    Scene s=new Scene();Surface first=s.sink.surface;SurfaceTexture next=new SurfaceTexture(2);
    s.texture.replaceWithoutAvailable(next);s.texture.present("new texture content");
    check("A texture replaced without an available event reaches the original SDK",s.sink.resets==2&&s.sink.surface.texture==next&&s.sink.surface!=first);
    s.present(6);check("Further frames of the replacement do not reset its compositor",s.sink.resets==2);
    s.binding.onSurfaceTextureUpdated(s.image);
    check("A late old texture update cannot replace the newly selected SDK surface",s.sink.resets==2&&s.sink.surface.texture==next);
    s.binding.onSurfaceTextureSizeChanged(s.image,1,1);
    check("A late old texture size callback cannot resize the replacement",s.sink.resets==2&&s.sink.width==400&&s.sink.height==800);
    boolean stale=s.binding.onSurfaceTextureDestroyed(s.image);
    check("A late old texture destroy cannot retire the replacement",!stale&&s.sink.destroyed==0&&s.sdk.getSurface().texture==next);
    s.texture.resize(900,600);
    check("Replacement dimensions still use the real SDK size callback",s.sink.resets==3&&s.sink.width==900&&s.sink.height==600);
  }
  static void retirement(){
    Scene s=new Scene();int resets=s.sink.resets;
    boolean release=s.texture.destroy();
    check("The original SDK destroy callback and texture-release result are retained",!release&&s.sink.destroyed==1&&s.sdk.getSurface()==null);
    s.binding.onSurfaceTextureUpdated(s.image);
    check("A queued update after destruction cannot revive the retired surface",s.sink.resets==resets);
    SurfaceTexture next=new SurfaceTexture(3);s.texture.available(next,320,640);s.present(4);
    check("Destroy then recreate reuses the listener with a new real surface",s.sink.resets==resets+1&&s.sink.surface.texture==next&&s.sink.width==320&&s.sink.height==640);
    GeckoTextureSurface old=s.binding;old.close();old.close();
    check("Closing restores the precise original SDK listener once",s.texture.getSurfaceTextureListener()==s.original);
    int after=s.sink.resets;old.onSurfaceTextureUpdated(next);old.onSurfaceTextureAvailable(next,320,640);
    check("Callbacks held by a closed adapter cannot revive an SDK surface",s.sink.resets==after);
    s.install();s.present(4);
    check("A later binding after close remains usable without a new surface reset",s.binding!=old&&s.sink.resets==after);
    old.close();check("Closing the prior binding again cannot remove its successor",s.texture.getSurfaceTextureListener()==s.binding);
    Scene attached=new Scene(false);attached.present(4);
    check("Installation after availability retains the already established SDK surface",attached.sink.resets==1&&attached.texture.displayedFrames==4);
  }
  static void listenerOwnership(){
    Scene s=new Scene();GeckoTextureSurface old=s.binding;Listener replacement=new Listener();
    s.texture.setSurfaceTextureListener(replacement);old.close();
    check("Closing an old binding preserves an externally installed successor listener",s.texture.getSurfaceTextureListener()==replacement);
    old.onSurfaceTextureUpdated(s.image);old.onSurfaceTextureDestroyed(s.image);
    check("A retired binding cannot forward old callbacks into the SDK",s.sink.resets==1&&s.sink.destroyed==0);
    s.install();s.texture.resize(500,900);
    check("A replacement owner can be bound and still receives its actual lifecycle",replacement.resized==1);
    s.binding.close();check("A later close restores that replacement listener exactly",s.texture.getSurfaceTextureListener()==replacement);
    Scene first=new Scene();TextureView originalTexture=first.texture;GeckoTextureSurface previous=first.binding;
    Scene second=new Scene(false);second.binding.close();
    first.view.removeAllViews();first.view.addView(second.texture);first.install();
    check("Changing the texture backend restores the old child's original listener",originalTexture.getSurfaceTextureListener()==first.original);
    check("Changing the texture backend installs one binding on the new child",first.binding!=previous&&second.texture.getSurfaceTextureListener()==first.binding);
    int oldResets=first.sink.resets,newResets=second.sink.resets;second.present(4);
    check("New backend frames retain their own SDK surface without touching the old one",first.sink.resets==oldResets&&second.sink.resets==newResets);
    first.view.removeAllViews();first.view.addView(new SurfaceView(first.context));first.install();
    check("A non-texture backend receives no adapter and restores the former listener",first.binding==null&&second.texture.getSurfaceTextureListener()==second.original);
    ViewGroup empty=new ViewGroup(new Context());TextureView unowned=new TextureView(empty.getContext());empty.addView(unowned);
    check("A texture without an SDK listener is left unchanged",GeckoTextureSurface.install(empty,null)==null&&unowned.getSurfaceTextureListener()==null);
  }
  static void reentry(){
    Context context=new Context();ViewGroup view=new ViewGroup(context);TextureView texture=new TextureView(context);view.addView(texture);
    Listener original=new Listener();original.release=true;texture.setSurfaceTextureListener(original);
    final GeckoTextureSurface[] binding={GeckoTextureSurface.install(view,null)};
    SurfaceTexture first=new SurfaceTexture(10),next=new SurfaceTexture(11);
    texture.available(first,400,800);
    original.destroy=()->check("The framework destroy callback still sees the old available texture",texture.isAvailable()&&texture.getSurfaceTexture()==first);
    boolean release=texture.destroy();
    check("Destroy preserves a delegate that releases its surface texture",release&&original.destroyed==1&&first.released&&!texture.isAvailable());
    // Synthetic adapter reentry only: Android clears its texture after a normal
    // destroy callback; this direct call does not claim recreation inside it.
    SurfaceTexture synthetic=new SurfaceTexture(13);texture.available(synthetic,400,800);
    original.destroy=()->texture.available(next,600,300);
    binding[0].onSurfaceTextureDestroyed(synthetic);texture.present("new page after adapter callback");
    check("Adapter-only reentry retains a newer availability after an old callback",texture.getSurfaceTexture()==next&&original.available==3&&original.updated==0);
    Listener successor=new Listener();GeckoTextureSurface old=binding[0];
    original.receive=()->{old.close();texture.setSurfaceTextureListener(successor);binding[0]=GeckoTextureSurface.install(view,null);};
    texture.available(new SurfaceTexture(12),400,800);texture.present("successor content");
    check("A synchronous listener replacement during available keeps the new binding",texture.getSurfaceTextureListener()==binding[0]&&binding[0]!=old);
    check("The old availability callback does not overwrite the successor's content ownership",successor.updated==0);
    old.onSurfaceTextureUpdated(next);check("An older captured callback cannot reach the successor",successor.updated==0);
    binding[0].close();check("The successor's exact listener survives adapter cleanup",texture.getSurfaceTextureListener()==successor);
  }
  public static void main(String[] args){
    stableContent();replacement();retirement();listenerOwnership();reentry();
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.getJSONObject(i).getBoolean("pass"))passed++;
    JSONObject result=new JSONObject().put("status",passed==checks.length()?"passed":"failed")
      .put("passed",passed).put("total",checks.length()).put("checks",checks);
    System.out.println(result);if(passed!=checks.length())System.exit(1);
  }
}
