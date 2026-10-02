package local.pocketchat;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.view.Gravity;
import android.widget.Button;

final class Ui {
  static final int INK=0xff1e293b,MUTED=0xff64748b,PAPER=0xfff4f6fa,SOFT=0xffeaf1ff;
  static int dp(Context c,int n){return (int)(c.getResources().getDisplayMetrics().density*n+.5f);}
  static GradientDrawable shape(Context c,int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(c,radius));return d;}
  static RippleDrawable ripple(Context c,int color,int radius){return new RippleDrawable(ColorStateList.valueOf(0x18000000),shape(c,color,radius),shape(c,Color.WHITE,radius));}
  static final class Icon extends Drawable {
    String name;final Paint p=new Paint(3);int color;
    Icon(String name,int color){this.name=name;this.color=color;}
    public void draw(Canvas canvas){Rect b=getBounds();canvas.save();canvas.translate(b.left,b.top);canvas.scale(b.width()/24f,b.height()/24f);p.setColor(color);p.setStrokeWidth(1.7f);p.setStyle(Paint.Style.STROKE);p.setStrokeCap(Paint.Cap.ROUND);p.setStrokeJoin(Paint.Join.ROUND);
      Path path=new Path();
      switch(name){
        case "window":path.moveTo(12,3);path.lineTo(21,8);path.lineTo(21,18);path.lineTo(12,23);path.lineTo(3,18);path.lineTo(3,8);path.close();canvas.drawPath(path,p);canvas.drawLine(3,8,12,13,p);canvas.drawLine(21,8,12,13,p);canvas.drawLine(12,13,12,23,p);break;
        case "shield":path.moveTo(12,2);path.lineTo(21,6);path.lineTo(20,15);path.quadTo(18,20,12,23);path.quadTo(6,20,4,15);path.lineTo(3,6);path.close();canvas.drawPath(path,p);path.reset();path.moveTo(8,12);path.lineTo(11,15);path.lineTo(17,8);canvas.drawPath(path,p);break;
        case "lock":canvas.drawRoundRect(new RectF(5,10,19,22),3,3,p);canvas.drawArc(new RectF(8,2,16,14),180,180,false,p);canvas.drawCircle(12,15,1,p);canvas.drawLine(12,16,12,18,p);break;
        case "star":for(int i=0;i<10;i++){double angle=-Math.PI/2+i*Math.PI/5;float radius=i%2==0?10:4.8f;float x=12+(float)Math.cos(angle)*radius,y=12+(float)Math.sin(angle)*radius;if(i==0)path.moveTo(x,y);else path.lineTo(x,y);}path.close();canvas.drawPath(path,p);break;
        case "filter":path.moveTo(3,4);path.lineTo(21,4);path.lineTo(14,12);path.lineTo(14,20);path.lineTo(10,22);path.lineTo(10,12);path.close();canvas.drawPath(path,p);break;
        case "pause":canvas.drawLine(8,5,8,19,p);canvas.drawLine(16,5,16,19,p);break;
        case "brand":canvas.drawCircle(12,12,10,p);p.setStyle(Paint.Style.FILL);canvas.drawCircle(12,7,2,p);path.moveTo(12,9);path.lineTo(8,14);path.lineTo(5,18);path.quadTo(12,15,19,18);path.lineTo(16,14);path.close();canvas.drawPath(path,p);break;
        case "hamburger":canvas.drawLine(3,6,21,6,p);canvas.drawLine(3,12,21,12,p);canvas.drawLine(3,18,21,18,p);break;
        case "menu":canvas.drawLine(4,8,20,8,p);canvas.drawLine(4,15,14,15,p);break;
        case "new":path.moveTo(13,5);path.lineTo(6,5);path.quadTo(4,5,4,7);path.lineTo(4,18);path.quadTo(4,20,6,20);path.lineTo(17,20);path.quadTo(19,20,19,18);path.lineTo(19,12);canvas.drawPath(path,p);path.reset();path.moveTo(10,14);path.lineTo(11,10);path.lineTo(18,3);path.lineTo(21,6);path.lineTo(14,13);path.close();canvas.drawPath(path,p);break;
        case "more":p.setStyle(Paint.Style.FILL);for(int x:new int[]{5,12,19})canvas.drawCircle(x,12,1.5f,p);break;
        case "plus":canvas.drawLine(5,12,19,12,p);canvas.drawLine(12,5,12,19,p);break;
        case "arrow":canvas.drawLine(12,18,12,5,p);path.moveTo(6,11);path.lineTo(12,5);path.lineTo(18,11);canvas.drawPath(path,p);break;
        case "back":path.moveTo(14,5);path.lineTo(7,12);path.lineTo(14,19);canvas.drawPath(path,p);break;
        case "chevron":path.moveTo(7,10);path.lineTo(12,15);path.lineTo(17,10);canvas.drawPath(path,p);break;
        case "close":canvas.drawLine(6,6,18,18,p);canvas.drawLine(18,6,6,18,p);break;
        case "file":path.moveTo(5,3);path.lineTo(14,3);path.lineTo(19,8);path.lineTo(19,21);path.lineTo(5,21);path.close();canvas.drawPath(path,p);path.reset();path.moveTo(14,3);path.lineTo(14,8);path.lineTo(19,8);canvas.drawPath(path,p);canvas.drawLine(8,13,16,13,p);canvas.drawLine(8,17,14,17,p);break;
        case "image":canvas.drawRoundRect(new RectF(3,3,21,21),4,4,p);canvas.drawCircle(8,8,1.4f,p);path.moveTo(4,18);path.lineTo(10,12);path.lineTo(14,16);path.lineTo(17,13);path.lineTo(21,17);canvas.drawPath(path,p);break;
        case "download":canvas.drawLine(12,3,12,15,p);path.moveTo(7,10);path.lineTo(12,15);path.lineTo(17,10);canvas.drawPath(path,p);path.reset();path.moveTo(4,16);path.lineTo(4,21);path.lineTo(20,21);path.lineTo(20,16);canvas.drawPath(path,p);break;
        case "globe":canvas.drawCircle(12,12,9,p);canvas.drawOval(new RectF(8,3,16,21),p);canvas.drawLine(3,12,21,12,p);break;
        case "undo":path.moveTo(4,9);path.lineTo(14,9);path.cubicTo(23,9,23,20,14,20);canvas.drawPath(path,p);path.reset();path.moveTo(8,4);path.lineTo(3,9);path.lineTo(8,14);canvas.drawPath(path,p);break;
        case "clipboard":canvas.drawRoundRect(new RectF(5,5,19,22),2,2,p);canvas.drawRoundRect(new RectF(8,2,16,7),2,2,p);break;
        case "search":canvas.drawCircle(10,10,6,p);canvas.drawLine(14.5f,14.5f,20,20,p);break;
        case "chat":canvas.drawRoundRect(new RectF(3,4,21,18),5,5,p);path.moveTo(6,18);path.lineTo(5,22);path.lineTo(11,18);canvas.drawPath(path,p);break;
        case "settings":canvas.drawLine(4,7,20,7,p);canvas.drawLine(4,17,20,17,p);p.setStyle(Paint.Style.FILL);p.setColor(Color.WHITE);canvas.drawCircle(9,7,3,p);canvas.drawCircle(16,17,3,p);p.setStyle(Paint.Style.STROKE);p.setColor(color);canvas.drawCircle(9,7,3,p);canvas.drawCircle(16,17,3,p);break;
      }canvas.restore();
    }
    public void setAlpha(int a){p.setAlpha(a);}public void setColorFilter(ColorFilter f){p.setColorFilter(f);}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  }
  static final class IconButton extends Button {
    final Icon icon;final boolean filled;
    IconButton(Context c,String glyph,String label,boolean filled){super(c);this.filled=filled;icon=new Icon(glyph,filled?Color.WHITE:INK);setText("");setContentDescription(label);setPadding(0,0,0,0);setMinWidth(0);setMinHeight(0);setMinimumWidth(0);setMinimumHeight(0);setGravity(Gravity.CENTER);setStateListAnimator(null);setElevation(0);setBackground(ripple(c,filled?0xff1268ff:Color.TRANSPARENT,28));}
    @Override protected void onDraw(Canvas c){super.onDraw(c);int size=dp(getContext(),filled?21:23);icon.setBounds((getWidth()-size)/2,(getHeight()-size)/2,(getWidth()+size)/2,(getHeight()+size)/2);icon.color=filled?Color.WHITE:MUTED;icon.draw(c);}
    @Override public void setEnabled(boolean enabled){super.setEnabled(enabled);setAlpha(enabled?1f:.35f);}
  }
}
