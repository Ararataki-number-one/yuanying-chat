package local.pocketchat;

import android.annotation.TargetApi;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.RecordingCanvas;
import android.graphics.RenderEffect;
import android.graphics.RenderNode;
import android.graphics.RuntimeShader;
import android.graphics.Shader;
import android.util.Log;
import android.view.View;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/** API 33 isolation: only the material receives the effect; glyphs stay native. */
@TargetApi(33)
final class GlassLensRenderer {
  private static final String TAG="GlassLens";
  private static String program;
  private final RuntimeShader shader;
  private final RenderNode content=new RenderNode("native-glass-content");
  private final float density;
  private RenderEffect blur;
  private final int[] hostAt=new int[2],sourceAt=new int[2];
  private int width=-1,height=-1,lastX=Integer.MIN_VALUE,lastY=Integer.MIN_VALUE,lastColor;
  private long lastRevision=-1;
  private GlassBackdrop lastSource;
  private boolean hadBackdrop,reportedBackdrop;

  GlassLensRenderer(Context context,float density) throws Exception {
    this.density=density;
    if(program==null){
      ByteArrayOutputStream bytes=new ByteArrayOutputStream();
      try(InputStream stream=context.getAssets().open("ui/liquid-glass.agsl")){
        byte[] block=new byte[4096];int count;
        while((count=stream.read(block))!=-1)bytes.write(block,0,count);
      }
      program=bytes.toString("UTF-8");
    }
    shader=new RuntimeShader(program);
    content.setClipToBounds(false);
    blur=RenderEffect.createBlurEffect(3.5f*density,3.5f*density,Shader.TileMode.CLAMP);
    Log.i(TAG,"AGSL material ready");
  }

  boolean draw(Canvas canvas,Rect bounds,float radius,float pressure,float bend,
      float lightX,float lightY,float bumpX,float bumpY,int alpha,boolean dark,
      GlassBackdrop source,View host){
    if(!canvas.isHardwareAccelerated()||bounds.isEmpty())return false;
    int margin=(int)Math.ceil(18*density),w=bounds.width(),h=bounds.height();
    int recordedWidth=w+2*margin,recordedHeight=h+2*margin;
    boolean backdrop=source!=null&&host!=null&&source.isGlassActive();
    int relativeX=0,relativeY=0;
    long revision=-1;
    if(backdrop){
      host.getLocationInWindow(hostAt);source.getLocationInWindow(sourceAt);
      relativeX=hostAt[0]-sourceAt[0]+bounds.left;
      relativeY=hostAt[1]-sourceAt[1]+bounds.top;
      revision=source.revision();
    }
    // Keep a nonempty display list even for the transparent, unsampled coating.
    // The shader ignores these input pixels when hasBackdrop is zero.
    int clear=backdrop?DesignUi.BG:Color.WHITE;
    content.setPosition(bounds.left-margin,bounds.top-margin,bounds.right+margin,bounds.bottom+margin);
    if(width!=w||height!=h||backdrop!=hadBackdrop||source!=lastSource
        ||revision!=lastRevision||relativeX!=lastX||relativeY!=lastY||clear!=lastColor
        ||!content.hasDisplayList()){
      RecordingCanvas recording=content.beginRecording(recordedWidth,recordedHeight);
      boolean recorded=false;
      try{
        recording.clipRect(0,0,recordedWidth,recordedHeight);
        recording.drawColor(clear);
        if(backdrop){
          recording.translate(-bounds.left,-bounds.top);
          recorded=source.drawBehind(recording,host,margin);
        }
      }finally{content.endRecording();}
      backdrop&=recorded;
      width=w;height=h;hadBackdrop=backdrop;lastSource=source;lastRevision=revision;
      lastX=relativeX;lastY=relativeY;lastColor=clear;
      if(backdrop&&!reportedBackdrop){reportedBackdrop=true;Log.i(TAG,"native backdrop recorded");}
    }
    shader.setFloatUniform("size",w,h);
    shader.setFloatUniform("margin",margin);
    shader.setFloatUniform("density",density);
    shader.setFloatUniform("radius",radius);
    shader.setFloatUniform("press",pressure);
    shader.setFloatUniform("bend",bend);
    shader.setFloatUniform("light",lightX,lightY);
    shader.setFloatUniform("bump",bumpX-bounds.left,bumpY-bounds.top);
    shader.setFloatUniform("darkTheme",dark?1f:0f);
    shader.setFloatUniform("hasBackdrop",backdrop?1f:0f);
    shader.setFloatUniform("opacity",alpha/255f);
    // RenderEffect snapshots shader uniforms; rebuilding this lightweight chain
    // is required for a new optical state. The recorded pixels and blur are reused.
    RenderEffect lens=RenderEffect.createRuntimeShaderEffect(shader,"content");
    content.setRenderEffect(backdrop?RenderEffect.createChainEffect(lens,blur):lens);
    canvas.drawRenderNode(content);
    return true;
  }

  void discard(){content.discardDisplayList();lastRevision=-1;lastSource=null;hadBackdrop=false;}
}
