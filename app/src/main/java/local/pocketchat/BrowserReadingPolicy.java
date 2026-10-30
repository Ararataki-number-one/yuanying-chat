package local.pocketchat;

import java.net.URI;

/** Zoom is relative to fitting the available view, independent of device density. */
final class BrowserReadingPolicy {
  static final String ZOOM_KEY="responsiveReadingZoom",LEGACY_ZOOM_KEY="desktopReadingZoom";
  static final float MIN=.6f,MAX=20f;
  static float bounded(float value){return Float.isNaN(value)||Float.isInfinite(value)?1f:Math.max(MIN,Math.min(MAX,value));}
  static float fit(int width,float density,float viewport){return width<=0?0:Float.isFinite(viewport)&&viewport>0?width/viewport:Float.isFinite(density)&&density>0?density:0;}
  static float target(int width,float density,float viewport,float choice){return fit(width,density,viewport)*bounded(choice);}
  static boolean fitted(int width,float scale,float viewport,float layout){
    if(width<=0||!Float.isFinite(scale)||scale<=0||!Float.isFinite(viewport)||viewport<=0||!Float.isFinite(layout)||layout<=0)return false;
    double residual=Math.abs((double)scale*viewport/layout-width);
    // clientWidth is integral. Allow its sub-CSS-pixel rounding, while keeping
    // both the native width error below 6px and the page edge within 1 CSS px.
    return residual<6&&residual<=scale;
  }
  static double zoomError(int width,float scale,float viewport,float choice){
    if(width<=0||!Float.isFinite(scale)||scale<=0||!Float.isFinite(viewport)||viewport<=0||!Float.isFinite(choice)||choice<=0)return Double.POSITIVE_INFINITY;
    return Math.abs((double)scale*viewport/width-choice);
  }
  static boolean restored(int width,float scale,float viewport,float choice){return zoomError(width,scale,viewport,choice)<=.035;}
  static float fromScale(int width,float density,float viewport,float scale){float base=fit(width,density,viewport);return base>0&&Float.isFinite(scale)&&scale>0?bounded(scale/base):MIN;}
  static float migrate(int width,float density,float choice){return width>0&&Float.isFinite(density)&&density>0?Math.max(1f,bounded(bounded(choice)*width/(BrowserDisplay.DESKTOP_WIDTH*density))):1f;}
  static boolean chat(String url){try{URI u=new URI(url);return "https".equals(u.getScheme())&&("chatgpt.com".equals(u.getHost())||"chat.openai.com".equals(u.getHost()))&&u.getRawUserInfo()==null&&(u.getPort()==-1||u.getPort()==443);}catch(Exception e){return false;}}
  static boolean remember(boolean desktop,boolean ready,boolean gesture,String url){return desktop&&ready&&gesture&&chat(url);}
  static boolean hideNavigation(boolean chatPage,boolean rawWeb,boolean keyboard){return chatPage&&rawWeb&&keyboard;}
  static float focusScroll(float top,float bottom,float caretTop,float caretBottom,float height,float margin,float pixelsPerCss){
    if(!Float.isFinite(top)||!Float.isFinite(bottom)||!Float.isFinite(height)||!Float.isFinite(margin)||!Float.isFinite(pixelsPerCss)||height<=0||pixelsPerCss<=0||margin<0||bottom<=top||height<=margin*2)return 0;
    if(bottom-top>height-margin*2){if(!Float.isFinite(caretTop)||!Float.isFinite(caretBottom)||caretBottom<=caretTop||caretBottom-caretTop>height-margin*2)return 0;top=caretTop;bottom=caretBottom;}
    float delta=top<margin?top-margin:bottom>height-margin?bottom-(height-margin):0;
    return Math.abs(delta)<.5f?0:delta/pixelsPerCss;
  }
  static String literal(String value){StringBuilder out=new StringBuilder("\"");for(int i=0;i<value.length();i++){char c=value.charAt(i);if(c=='\\'||c=='\"')out.append('\\').append(c);else if(c<32||c=='\u2028'||c=='\u2029')out.append(String.format(java.util.Locale.ROOT,"\\u%04x",(int)c));else out.append(c);}return out.append('"').toString();}
  static String focusScript(){return focusScript("https://chatgpt.com/c/reading");}
  static String focusScript(String expectedUrl){return
    "(()=>{'use strict';if(window!==window.top||location.href!=="+literal(expectedUrl)+")return false;"+
    "const el=document.activeElement;if(!el||!(el.tagName==='TEXTAREA'||el.isContentEditable||el.tagName==='INPUT'&&/^(text|search|email|url|tel|number|password)$/.test(el.type)))return false;"+
    "const r=el.getBoundingClientRect();if(r.width<=0||r.height<=0)return false;const box=r=>({left:r.left+scrollX,right:r.right+scrollX,top:r.top+scrollY,bottom:r.bottom+scrollY});let caret=null;"+
    "if(el.isContentEditable){const s=window.getSelection();if(s&&s.rangeCount&&el.contains(s.anchorNode)&&el.contains(s.focusNode)){const range=s.getRangeAt(0).cloneRange();range.setStart(s.focusNode,s.focusOffset);range.collapse(true);const cr=range.getBoundingClientRect();if(cr.height>0)caret=box(cr);}}"+
    "return {ok:true,url:location.href,document:performance.timeOrigin,rect:box(r),caret};})();";
  }
}
