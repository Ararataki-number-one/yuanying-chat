package local.pocketchat;

import android.content.Context;
import android.graphics.SurfaceTexture;
import android.view.*;
import org.json.JSONObject;
import org.mozilla.gecko.SurfaceViewWrapper;

/** Executes the complete upstream wrapper, or the actual receipt-bound class. */
public final class CauseHost {
  public static void main(String[] args)throws Exception {
    SurfaceViewWrapper sdk=new SurfaceViewWrapper(new Context());
    final int[] resets={0};
    sdk.setListener(new SurfaceViewWrapper.Listener(){
      public void onSurfaceChanged(Surface surface,SurfaceControl control,int width,int height){resets[0]++;}
      public void onSurfaceDestroyed(){}
    });
    sdk.useTextureView(new Context());
    TextureView texture=(TextureView)sdk.getView();
    SurfaceTexture image=new SurfaceTexture(1);
    texture.available(image,400,800);
    int initialResets=resets[0],initialAllocations=Surface.allocations;
    for(int frame=0;frame<12;frame++)texture.present("unchanged document");
    JSONObject report=new JSONObject().put("status",resets[0]==initialResets?"passed":"failed")
      .put("contentFramesPresented",texture.displayedFrames).put("initialSurfaceNotifications",initialResets)
      .put("surfaceNotificationsAfterUpdates",resets[0]).put("extraSurfaceNotifications",resets[0]-initialResets)
      .put("extraSurfaceAllocations",Surface.allocations-initialAllocations)
      .put("textureIdentityUnchanged",texture.getSurfaceTexture()==image)
      .put("dimensionsUnchanged",texture.getWidth()==400&&texture.getHeight()==800);
    System.out.println(report);
    if(resets[0]!=initialResets)System.exit(1);
  }
}
