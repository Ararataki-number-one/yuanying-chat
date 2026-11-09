package local.pocketchat;

import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ImageSpan;
import android.widget.TextView;

/** Local country artwork for a label hint; no lookup, observation or network state. */
final class NetworkCountryIcon extends Drawable {
  private static final Typeface REGULAR=Typeface.create("sans-serif",Typeface.NORMAL),BOLD=Typeface.create("sans-serif",Typeface.BOLD);
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final String code,flag;
  private final boolean emojiAvailable;
  private final Ui.Icon neutral;
  private final int size;
  private int alpha=255;

  private NetworkCountryIcon(Context context,String code,String fallback,int sizeDp){
    this.code=NetworkCountryHint.country(code).isEmpty()?"":code.toUpperCase(java.util.Locale.ROOT);
    flag=NetworkCountryHint.flag(this.code);size=DesignUi.dp(context,sizeDp);
    neutral=new Ui.Icon(fallback,DesignUi.MUTED);
    paint.setTypeface(REGULAR);
    emojiAvailable=!flag.isEmpty()&&paint.hasGlyph(flag);setBounds(0,0,size,size);
  }

  static Drawable drawable(Context context,String code,String fallback,int sizeDp){return new NetworkCountryIcon(context,code,fallback,sizeDp);}
  static void bind(TextView view,String code,String fallback){bind(view,code,fallback,18);}
  static void bind(TextView view,String code,String fallback,int sizeDp){
    String original=view.getText().toString(),shown=displayLabel(original,code);if(!shown.equals(original))view.setText(shown);
    view.setCompoundDrawablesRelative(drawable(view.getContext(),code,fallback,sizeDp),null,null,null);
    view.setCompoundDrawablePadding(DesignUi.dp(view.getContext(),6));
    // Android tooltips consume touch even on non-clickable labels. Keep taps on
    // this decorative child available to its row, including after recycling.
    view.setTooltipText(null);
  }

  static String labeled(String value,String code){
    String country=NetworkCountryHint.country(code);
    String shown=displayLabel(value,code);
    return country.isEmpty()||code.equals(NetworkCountryHint.code(value))?shown:shown+" · "+country;
  }

  static String displayLabel(String value,String code){
    String flag=NetworkCountryHint.flag(code);if(flag.isEmpty())return value;
    String shown=value.replace(flag+" ","").replace(flag,"").trim();
    return shown.isEmpty()?NetworkCountryHint.country(code):shown;
  }

  static void append(SpannableStringBuilder text,Context context,String value,String code){
    int start=text.length();text.append('\ufffc');
    text.setSpan(new CenteredSpan(drawable(context,code,"node",16)),start,start+1,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    text.append('\u00a0').append(displayLabel(value,code));
  }

  @Override public void draw(Canvas canvas){
    Rect bounds=getBounds();
    if(code.isEmpty()){neutral.color=DesignUi.MUTED;neutral.setBounds(bounds);neutral.draw(canvas);return;}
    String text=emojiAvailable?flag:code;
    paint.setTypeface(emojiAvailable?REGULAR:BOLD);
    paint.setStyle(Paint.Style.FILL);paint.setColor(AppAppearance.color(DesignUi.MUTED));paint.setAlpha(alpha);
    paint.setTextSize(bounds.height()*(emojiAvailable?.94f:.55f));
    float width=paint.measureText(text);if(width>bounds.width())paint.setTextSize(paint.getTextSize()*bounds.width()/width);
    Paint.FontMetrics metrics=paint.getFontMetrics();
    canvas.drawText(text,bounds.exactCenterX()-paint.measureText(text)/2f,bounds.exactCenterY()-(metrics.ascent+metrics.descent)/2f,paint);
  }
  @Override public void setAlpha(int alpha){this.alpha=alpha;neutral.setAlpha(alpha);invalidateSelf();}
  @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);neutral.setColorFilter(filter);invalidateSelf();}
  @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
  @Override public int getIntrinsicWidth(){return size;}
  @Override public int getIntrinsicHeight(){return size;}

  /** Keep a small inline flag centred within the existing pending-text line. */
  private static final class CenteredSpan extends ImageSpan {
    CenteredSpan(Drawable drawable){super(drawable,ALIGN_BOTTOM);}
    @Override public int getSize(Paint paint,CharSequence text,int start,int end,Paint.FontMetricsInt metrics){
      Rect bounds=getDrawable().getBounds();
      if(metrics!=null){
        Paint.FontMetricsInt font=paint.getFontMetricsInt();int extra=Math.max(0,bounds.height()-(font.descent-font.ascent));
        metrics.ascent=font.ascent-extra/2;metrics.descent=font.descent+(extra+1)/2;
        metrics.top=Math.min(font.top,metrics.ascent);metrics.bottom=Math.max(font.bottom,metrics.descent);
      }
      return bounds.width();
    }
    @Override public void draw(Canvas canvas,CharSequence text,int start,int end,float x,int top,int y,int bottom,Paint paint){
      Drawable drawable=getDrawable();Paint.FontMetricsInt font=paint.getFontMetricsInt();
      float center=y+(font.ascent+font.descent)/2f;int save=canvas.save();
      canvas.translate(x,center-drawable.getBounds().height()/2f);drawable.draw(canvas);canvas.restoreToCount(save);
    }
  }
}
