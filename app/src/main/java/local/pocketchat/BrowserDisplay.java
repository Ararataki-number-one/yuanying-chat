package local.pocketchat;

import java.util.regex.*;

/** Desktop presentation policy; browser identity and viewport have one owner. */
final class BrowserDisplay {
  static final int DESKTOP_WIDTH=1024;
  static String label(boolean desktop){return desktop?"电脑版":"手机版";}
  static boolean busy(boolean working,boolean navigating,boolean connecting,boolean recovering,boolean webBusy){return working||navigating||connecting||recovering||webBusy;}
  static String agent(String original,int protection,boolean desktop){
    Matcher chrome=Pattern.compile("(?:Chrome|Chromium)/([0-9]+(?:\\.[0-9]+)*)").matcher(original);
    if(!chrome.find())return original;
    String version=chrome.group(1);if(protection>0)version=version.split("\\.")[0]+".0.0.0";
    if(desktop)return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"+version+" Safari/537.36";
    return protection==0?original:"Mozilla/5.0 (Linux; Android 10; K; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/"+version+" Mobile Safari/537.36";
  }
  static String viewportScript(){return
    "(()=>{'use strict';if(window!==window.top||window.__pocketDesktopViewport)return;"+
    "Object.defineProperty(window,'__pocketDesktopViewport',{value:true});"+
    "const content='width="+DESKTOP_WIDTH+"';let watching=false;"+
    "const ensure=()=>{if(!document.head)return;let metas=[...document.head.querySelectorAll('meta[name=\"viewport\" i]')];"+
    "if(!metas.length){const m=document.createElement('meta');m.name='viewport';document.head.appendChild(m);metas=[m];}"+
    "for(const m of metas)if(m.content!==content)m.content=content;};"+
    "const headObserver=new MutationObserver(ensure);"+
    "const attach=()=>{if(watching||!document.head)return;watching=true;rootObserver.disconnect();"+
    "headObserver.observe(document.head,{childList:true,subtree:true,attributes:true,attributeFilter:['content','name']});ensure();};"+
    "const rootObserver=new MutationObserver(attach);rootObserver.observe(document,{childList:true,subtree:true});attach();"+
    "document.addEventListener('DOMContentLoaded',attach,{once:true});})();";
  }
}
