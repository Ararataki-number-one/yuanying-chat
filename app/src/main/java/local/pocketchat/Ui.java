package local.pocketchat;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.view.Gravity;
import android.widget.Button;

final class Ui {
  static int INK=0xff1e293b,MUTED=0xff64748b,PAPER=0xfff4f6fa,SOFT=0xffeaf1ff;
  static int dp(Context c,int n){return (int)(c.getResources().getDisplayMetrics().density*n+.5f);}
  static GradientDrawable shape(Context c,int color,int radius){GradientDrawable d=new AppAppearance.Surface(color);d.setCornerRadius(dp(c,radius));return d;}
  static RippleDrawable ripple(Context c,int color,int radius){return new RippleDrawable(ColorStateList.valueOf(AppAppearance.dark()?0x337faeff:0x180067d8),shape(c,color,radius),shape(c,Color.WHITE,radius));}
  static final class Icon extends Drawable {
    String name;final Paint p=new Paint(3);int color;boolean solid;
    private final Path outline=new Path(),ink=new Path(),solidShape=new Path(),solidOutline=new Path();
    private String builtName;private boolean redesigned;private int alpha=255;
    Icon(String name,int color){this.name=name;this.color=color;geometry();}
    /** Geometry is cached; selecting a destination only changes ink and fill. */
    private void geometry(){
      builtName=name;outline.reset();ink.reset();solidShape.reset();solidOutline.reset();
      solidShape.setFillType(Path.FillType.EVEN_ODD);
      redesigned=buildNavigation(name)||WorkspaceGlyphs.build(name,outline,ink);
    }
    private boolean buildNavigation(String glyph){
      if(glyph==null)return false;
      switch(glyph){
        case "browser":{
          outline.addRoundRect(new RectF(3,4,21,20),3,3,Path.Direction.CW);
          outline.moveTo(3,9);outline.lineTo(21,9);
          ink.addCircle(6.5f,6.5f,.65f,Path.Direction.CW);
          ink.addCircle(9.5f,6.5f,.65f,Path.Direction.CW);
          solidShape.addRoundRect(new RectF(3,4,21,20),3,3,Path.Direction.CW);
          solidShape.addRoundRect(new RectF(5.5f,6,18.5f,8),1,1,Path.Direction.CW);
          return true;
        }
        case "chat":{
          outline.moveTo(7,3.8f);outline.lineTo(17,3.8f);
          outline.cubicTo(19.6f,3.8f,21,5.3f,21,7.8f);outline.lineTo(21,14.8f);
          outline.cubicTo(21,17.4f,19.6f,18.8f,17,18.8f);outline.lineTo(10.4f,18.8f);
          outline.lineTo(5.1f,21.5f);outline.lineTo(5.8f,18.4f);
          outline.cubicTo(3.8f,17.9f,3,16.6f,3,14.8f);outline.lineTo(3,7.8f);
          outline.cubicTo(3,5.3f,4.4f,3.8f,7,3.8f);outline.close();
          solidShape.addPath(outline);
          for(float x:new float[]{7.7f,12f,16.3f}){
            ink.addCircle(x,11.3f,.9f,Path.Direction.CW);
            solidShape.addCircle(x,11.3f,1.05f,Path.Direction.CW);
          }
          return true;
        }
        case "window":{
          Path back=new Path();back.moveTo(7.3f,3.2f);back.lineTo(17.5f,3.2f);
          back.quadTo(20.8f,3.2f,20.8f,6.5f);back.lineTo(20.8f,16.5f);
          outline.addPath(back);solidOutline.addPath(back);
          Path front=new Path();front.addRoundRect(new RectF(3.2f,6.6f,17.6f,21),3.1f,3.1f,Path.Direction.CW);
          outline.addPath(front);outline.moveTo(3.5f,11.2f);outline.lineTo(17.3f,11.2f);
          ink.addCircle(6.3f,8.9f,.55f,Path.Direction.CW);
          solidShape.addPath(front);solidShape.addRoundRect(new RectF(5.4f,9.5f,15.4f,11),.7f,.7f,Path.Direction.CW);
          return true;
        }
        case "download":{
          outline.moveTo(12,3.2f);outline.lineTo(12,15.3f);
          outline.moveTo(7.5f,10.8f);outline.lineTo(12,15.3f);outline.lineTo(16.5f,10.8f);
          outline.moveTo(3.4f,15);outline.lineTo(3.4f,18.6f);outline.quadTo(3.4f,21,5.8f,21);
          outline.lineTo(18.2f,21);outline.quadTo(20.6f,21,20.6f,18.6f);outline.lineTo(20.6f,15);
          solidShape.moveTo(10.5f,3.9f);solidShape.quadTo(10.5f,3,11.4f,3);solidShape.lineTo(12.6f,3);
          solidShape.quadTo(13.5f,3,13.5f,3.9f);solidShape.lineTo(13.5f,10.9f);solidShape.lineTo(16,10.9f);
          solidShape.quadTo(17,10.9f,16.3f,11.7f);solidShape.lineTo(12.7f,15.5f);
          solidShape.quadTo(12,16.2f,11.3f,15.5f);solidShape.lineTo(7.7f,11.7f);
          solidShape.quadTo(7,10.9f,8,10.9f);solidShape.lineTo(10.5f,10.9f);solidShape.close();
          solidShape.moveTo(3.8f,14.4f);solidShape.quadTo(2.8f,14.4f,2.8f,15.4f);solidShape.lineTo(2.8f,18.7f);
          solidShape.quadTo(2.8f,21.4f,5.5f,21.4f);solidShape.lineTo(18.5f,21.4f);
          solidShape.quadTo(21.2f,21.4f,21.2f,18.7f);solidShape.lineTo(21.2f,15.4f);
          solidShape.quadTo(21.2f,14.4f,20.2f,14.4f);solidShape.lineTo(18.6f,14.4f);solidShape.lineTo(18.6f,17.5f);
          solidShape.quadTo(18.6f,18.5f,17.6f,18.5f);solidShape.lineTo(6.4f,18.5f);
          solidShape.quadTo(5.4f,18.5f,5.4f,17.5f);solidShape.lineTo(5.4f,14.4f);solidShape.close();
          return true;
        }
        case "globe":{
          outline.addCircle(12,12,9.2f,Path.Direction.CW);
          outline.addOval(new RectF(8,2.8f,16,21.2f),Path.Direction.CW);
          outline.moveTo(2.8f,12);outline.lineTo(21.2f,12);
          solidShape.addCircle(12,12,9.4f,Path.Direction.CW);
          Path meridian=new Path(),cut=new Path(),equator=new Path();
          meridian.addOval(new RectF(8,4,16,20),Path.Direction.CW);
          Paint stroke=new Paint(Paint.ANTI_ALIAS_FLAG);stroke.setStyle(Paint.Style.STROKE);stroke.setStrokeWidth(1.4f);
          stroke.getFillPath(meridian,cut);
          equator.addRoundRect(new RectF(3.5f,11.25f,20.5f,12.75f),.7f,.7f,Path.Direction.CW);
          cut.op(equator,Path.Op.UNION);solidShape.op(cut,Path.Op.DIFFERENCE);
          return true;
        }
        case "settings":{
          float[] points=new float[64];int n=0;int[] offsets={-18,-11,11,18};
          for(int tooth=0;tooth<8;tooth++)for(int corner=0;corner<4;corner++){
            double angle=Math.toRadians(tooth*45+offsets[corner]);
            float radius=corner==0||corner==3?8:10.2f;
            points[n++]=12+(float)Math.cos(angle)*radius;points[n++]=12+(float)Math.sin(angle)*radius;
          }
          roundedPolygon(outline,points);solidShape.addPath(outline);
          outline.addCircle(12,12,3.2f,Path.Direction.CW);solidShape.addCircle(12,12,3.2f,Path.Direction.CW);
          return true;
        }
        case "book":{
          outline.moveTo(12,5.6f);outline.cubicTo(9,3.8f,5.5f,3.5f,2.6f,4.2f);
          outline.lineTo(2.6f,20);outline.cubicTo(6,19.2f,9.2f,19.6f,12,21.2f);
          outline.cubicTo(14.8f,19.6f,18,19.2f,21.4f,20);outline.lineTo(21.4f,4.2f);
          outline.cubicTo(18.5f,3.5f,15,3.8f,12,5.6f);outline.lineTo(12,21.2f);
          solidShape.moveTo(11.2f,5.5f);solidShape.cubicTo(8.7f,4,5.8f,3.6f,2.7f,4.2f);
          solidShape.lineTo(2.7f,20);solidShape.cubicTo(5.8f,19.3f,8.6f,19.6f,11.2f,20.8f);solidShape.close();
          solidShape.moveTo(12.8f,5.5f);solidShape.cubicTo(15.3f,4,18.2f,3.6f,21.3f,4.2f);
          solidShape.lineTo(21.3f,20);solidShape.cubicTo(18.2f,19.3f,15.4f,19.6f,12.8f,20.8f);solidShape.close();
          return true;
        }
        case "tray":{
          outline.moveTo(6.7f,4.2f);outline.lineTo(17.3f,4.2f);outline.quadTo(18.6f,4.2f,19,5.5f);
          outline.lineTo(21,13.4f);outline.lineTo(21,18.4f);outline.quadTo(21,20.5f,18.9f,20.5f);
          outline.lineTo(5.1f,20.5f);outline.quadTo(3,20.5f,3,18.4f);outline.lineTo(3,13.4f);
          outline.lineTo(5,5.5f);outline.quadTo(5.4f,4.2f,6.7f,4.2f);outline.close();
          outline.moveTo(3.4f,13.3f);outline.lineTo(7.8f,13.3f);outline.lineTo(9.6f,16.1f);
          outline.lineTo(14.4f,16.1f);outline.lineTo(16.2f,13.3f);outline.lineTo(20.6f,13.3f);
          return true;
        }
        case "filter":{
          outline.moveTo(4.3f,4);outline.lineTo(19.7f,4);outline.quadTo(20.8f,4,20.1f,4.9f);
          outline.lineTo(14,12.2f);outline.lineTo(14,18.6f);outline.quadTo(14,19.2f,13.5f,19.5f);
          outline.lineTo(10,21.2f);outline.lineTo(10,12.2f);outline.lineTo(3.9f,4.9f);
          outline.quadTo(3.2f,4,4.3f,4);outline.close();return true;
        }
        default:return false;
      }
    }
    private static void roundedPolygon(Path path,float[] points){
      int count=points.length/2;path.moveTo((points[0]+points[points.length-2])/2,(points[1]+points[points.length-1])/2);
      for(int i=0;i<count;i++){int next=(i+1)%count;path.quadTo(points[2*i],points[2*i+1],(points[2*i]+points[2*next])/2,(points[2*i+1]+points[2*next+1])/2);}path.close();
    }
    public void draw(Canvas canvas){
      if(builtName==null?name!=null:!builtName.equals(name))geometry();
      Rect b=getBounds();canvas.save();canvas.translate(b.left,b.top);canvas.scale(b.width()/24f,b.height()/24f);
      p.setColor(color);p.setAlpha(Math.round(Color.alpha(color)*alpha/255f));p.setStrokeWidth(1.75f);p.setStyle(Paint.Style.STROKE);p.setStrokeCap(Paint.Cap.ROUND);p.setStrokeJoin(Paint.Join.ROUND);
      if(redesigned){
        if(solid&&!solidShape.isEmpty()){
          p.setStyle(Paint.Style.FILL);canvas.drawPath(solidShape,p);p.setStyle(Paint.Style.STROKE);canvas.drawPath(solidOutline,p);
        }else{
          canvas.drawPath(outline,p);p.setStyle(Paint.Style.FILL);canvas.drawPath(ink,p);
        }
        canvas.restore();return;
      }
      Path path=new Path();
      switch(name){
        case "refresh":canvas.drawArc(new RectF(4,4,20,20),40,290,false,p);path.moveTo(16,2);path.lineTo(20,7);path.lineTo(14,8);canvas.drawPath(path,p);break;
        case "share":canvas.drawLine(12,15,12,3,p);path.moveTo(8,7);path.lineTo(12,3);path.lineTo(16,7);canvas.drawPath(path,p);path.reset();path.moveTo(6,10);path.lineTo(4,10);path.lineTo(4,21);path.lineTo(20,21);path.lineTo(20,10);path.lineTo(18,10);canvas.drawPath(path,p);break;
        case "trash":canvas.drawLine(4,6,20,6,p);canvas.drawLine(9,3,15,3,p);path.moveTo(6,6);path.lineTo(7,21);path.lineTo(17,21);path.lineTo(18,6);canvas.drawPath(path,p);canvas.drawLine(10,10,10,17,p);canvas.drawLine(14,10,14,17,p);break;
        case "check":path.moveTo(5,12);path.lineTo(10,17);path.lineTo(20,6);canvas.drawPath(path,p);break;
        case "info":canvas.drawCircle(12,12,9,p);canvas.drawLine(12,11,12,17,p);canvas.drawPoint(12,7,p);break;
        case "shield":path.moveTo(12,2);path.lineTo(21,6);path.lineTo(20,15);path.quadTo(18,20,12,23);path.quadTo(6,20,4,15);path.lineTo(3,6);path.close();canvas.drawPath(path,p);path.reset();path.moveTo(8,12);path.lineTo(11,15);path.lineTo(17,8);canvas.drawPath(path,p);break;
        case "lock":canvas.drawRoundRect(new RectF(5,10,19,22),3,3,p);canvas.drawArc(new RectF(8,2,16,14),180,180,false,p);canvas.drawCircle(12,15,1,p);canvas.drawLine(12,16,12,18,p);break;
        case "star":for(int i=0;i<10;i++){double angle=-Math.PI/2+i*Math.PI/5;float radius=i%2==0?10:4.8f;float x=12+(float)Math.cos(angle)*radius,y=12+(float)Math.sin(angle)*radius;if(i==0)path.moveTo(x,y);else path.lineTo(x,y);}path.close();canvas.drawPath(path,p);break;
        case "pause":canvas.drawLine(8,5,8,19,p);canvas.drawLine(16,5,16,19,p);break;
        case "brand":canvas.drawCircle(12,12,10,p);p.setStyle(Paint.Style.FILL);canvas.drawCircle(12,7,2,p);path.moveTo(12,9);path.lineTo(8,14);path.lineTo(5,18);path.quadTo(12,15,19,18);path.lineTo(16,14);path.close();canvas.drawPath(path,p);break;
        case "hamburger":canvas.drawLine(3,6,21,6,p);canvas.drawLine(3,12,21,12,p);canvas.drawLine(3,18,21,18,p);break;
        case "menu":canvas.drawLine(4,8,20,8,p);canvas.drawLine(4,15,14,15,p);break;
        case "new":path.moveTo(13,5);path.lineTo(6,5);path.quadTo(4,5,4,7);path.lineTo(4,18);path.quadTo(4,20,6,20);path.lineTo(17,20);path.quadTo(19,20,19,18);path.lineTo(19,12);canvas.drawPath(path,p);path.reset();path.moveTo(10,14);path.lineTo(11,10);path.lineTo(18,3);path.lineTo(21,6);path.lineTo(14,13);path.close();canvas.drawPath(path,p);break;
        case "more":p.setStyle(Paint.Style.FILL);for(int x:new int[]{5,12,19})canvas.drawCircle(x,12,1.5f,p);break;
        case "plus":canvas.drawLine(5,12,19,12,p);canvas.drawLine(12,5,12,19,p);break;
        case "arrow":canvas.drawLine(12,18,12,5,p);path.moveTo(6,11);path.lineTo(12,5);path.lineTo(18,11);canvas.drawPath(path,p);break;
        case "home":path.moveTo(3,10.5f);path.lineTo(12,3);path.lineTo(21,10.5f);path.moveTo(5,9);path.lineTo(5,21);path.lineTo(10,21);path.lineTo(10,14);path.lineTo(14,14);path.lineTo(14,21);path.lineTo(19,21);path.lineTo(19,9);canvas.drawPath(path,p);break;
        case "back":path.moveTo(14,5);path.lineTo(7,12);path.lineTo(14,19);canvas.drawPath(path,p);break;
        case "chevron":path.moveTo(7,10);path.lineTo(12,15);path.lineTo(17,10);canvas.drawPath(path,p);break;
        case "chevron-right":path.moveTo(9,5);path.lineTo(16,12);path.lineTo(9,19);canvas.drawPath(path,p);break;
        case "close":canvas.drawLine(6,6,18,18,p);canvas.drawLine(18,6,6,18,p);break;
        case "file":path.moveTo(5,3);path.lineTo(14,3);path.lineTo(19,8);path.lineTo(19,21);path.lineTo(5,21);path.close();canvas.drawPath(path,p);path.reset();path.moveTo(14,3);path.lineTo(14,8);path.lineTo(19,8);canvas.drawPath(path,p);canvas.drawLine(8,13,16,13,p);canvas.drawLine(8,17,14,17,p);break;
        case "image":canvas.drawRoundRect(new RectF(3,3,21,21),4,4,p);canvas.drawCircle(8,8,1.4f,p);path.moveTo(4,18);path.lineTo(10,12);path.lineTo(14,16);path.lineTo(17,13);path.lineTo(21,17);canvas.drawPath(path,p);break;
        case "undo":path.moveTo(4,9);path.lineTo(14,9);path.cubicTo(23,9,23,20,14,20);canvas.drawPath(path,p);path.reset();path.moveTo(8,4);path.lineTo(3,9);path.lineTo(8,14);canvas.drawPath(path,p);break;
        case "clipboard":canvas.drawRoundRect(new RectF(5,5,19,22),2,2,p);canvas.drawRoundRect(new RectF(8,2,16,7),2,2,p);break;
        case "search":canvas.drawCircle(10,10,6,p);canvas.drawLine(14.5f,14.5f,20,20,p);break;
      }canvas.restore();
    }
    public void setAlpha(int a){alpha=Math.max(0,Math.min(255,a));invalidateSelf();}public void setColorFilter(ColorFilter f){p.setColorFilter(f);invalidateSelf();}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  static final class IconButton extends Button {
    final Icon icon;final boolean filled;
    IconButton(Context c,String glyph,String label,boolean filled){super(c);this.filled=filled;icon=new Icon(glyph,filled?Color.WHITE:INK);setText("");setContentDescription(label);setPadding(0,0,0,0);setMinWidth(0);setMinHeight(0);setMinimumWidth(0);setMinimumHeight(0);setGravity(Gravity.CENTER);setStateListAnimator(null);setElevation(0);setBackground(ripple(c,filled?0xff1268ff:Color.TRANSPARENT,14));setTooltipText(label);}
    @Override protected void onDraw(Canvas c){super.onDraw(c);int size=dp(getContext(),21);icon.setBounds((getWidth()-size)/2,(getHeight()-size)/2,(getWidth()+size)/2,(getHeight()+size)/2);
      // Read the current glass role on every draw, including appearance changes.
      icon.color=filled?Color.WHITE:getBackground() instanceof AppAppearance.GlassRipple?DesignUi.GLASS_INK:MUTED;icon.draw(c);}
    @Override public void setEnabled(boolean enabled){super.setEnabled(enabled);setAlpha(enabled?1f:.35f);}
  }
}
