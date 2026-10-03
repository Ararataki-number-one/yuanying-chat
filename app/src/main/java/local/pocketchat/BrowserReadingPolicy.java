package local.pocketchat;

import java.net.URI;

/** Zoom is relative to fitting the available view, independent of device density. */
final class BrowserReadingPolicy {
  static final String ZOOM_KEY="responsiveReadingZoom",LEGACY_ZOOM_KEY="desktopReadingZoom";
  static final float MIN=1f,MAX=20f;
  static float bounded(float value){return Float.isNaN(value)||Float.isInfinite(value)?MIN:Math.max(MIN,Math.min(MAX,value));}
  static float fit(int width,float density,float viewport){return width<=0?0:Float.isFinite(viewport)&&viewport>0?width/viewport:Float.isFinite(density)&&density>0?density:0;}
  static float target(int width,float density,float viewport,float choice){return fit(width,density,viewport)*bounded(choice);}
  static float fromScale(int width,float density,float viewport,float scale){float base=fit(width,density,viewport);return base>0&&Float.isFinite(scale)&&scale>0?bounded(scale/base):MIN;}
  static float migrate(int width,float density,float choice){return width>0&&Float.isFinite(density)&&density>0?bounded(bounded(choice)*width/(BrowserDisplay.DESKTOP_WIDTH*density)):MIN;}
  static boolean chat(String url){try{URI u=new URI(url);return "https".equals(u.getScheme())&&("chatgpt.com".equals(u.getHost())||"chat.openai.com".equals(u.getHost()))&&u.getRawUserInfo()==null&&(u.getPort()==-1||u.getPort()==443);}catch(Exception e){return false;}}
  static boolean remember(boolean desktop,boolean ready,boolean gesture,String url){return desktop&&ready&&gesture&&chat(url);}
  static boolean hideNavigation(boolean chatPage,boolean rawWeb,boolean keyboard){return chatPage&&rawWeb&&keyboard;}
  static String focusScript(){return
    "(()=>{'use strict';if(window!==window.top||location.protocol!=='https:'||!['chatgpt.com','chat.openai.com'].includes(location.hostname)||location.port&&location.port!=='443')return false;"+
    "const el=document.activeElement;if(!el||!(el.tagName==='TEXTAREA'||el.isContentEditable||el.tagName==='INPUT'&&/^(text|search|email|url|tel|number|password)$/.test(el.type)))return false;"+
    "const vv=window.visualViewport,top=vv?vv.offsetTop:0,left=vv?vv.offsetLeft:0,height=vv?vv.height:window.innerHeight,width=vv?vv.width:window.innerWidth;"+
    "let r=el.getBoundingClientRect();if(el.isContentEditable){const s=window.getSelection();if(s&&s.rangeCount&&el.contains(s.anchorNode)){const caret=s.getRangeAt(0).cloneRange();caret.collapse(false);const cr=caret.getBoundingClientRect();if(cr.height>0)r=cr;}}"+
    "if(r.width===0&&r.height===0)return false;if(r.top>=top+8&&r.bottom<=top+height-8&&r.left>=left&&r.right<=left+width)return false;"+
    "el.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});return true;})();";
  }
}
