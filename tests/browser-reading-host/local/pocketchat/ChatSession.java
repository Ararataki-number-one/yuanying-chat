package local.pocketchat;

import java.util.*;

/** Minimal host doubles, not an Android runtime or real WebView renderer. */
final class ChatSession {
  final Prefs prefs;final Queue handler=new Queue();final Context context=new Context();final Web web=new Web();
  ChatSession(Prefs p){prefs=p;}
  static class Prefs {final Map<String,Float> data=new HashMap<>();boolean contains(String key){return data.containsKey(key);}float getFloat(String key,float fallback){return data.getOrDefault(key,fallback);}Prefs edit(){return this;}Prefs putFloat(String key,float value){data.put(key,value);return this;}void apply(){}}
  static class Queue {final List<Runnable> tasks=new ArrayList<>();void removeCallbacks(Runnable r){tasks.removeIf(item->item==r);}void postDelayed(Runnable r,long delay){tasks.add(r);}void drain(){List<Runnable> pending=new ArrayList<>(tasks);tasks.clear();for(Runnable r:pending)r.run();}}
  static class Context {Context getResources(){return this;}Context getDisplayMetrics(){return this;}float density=3;}
  interface Layout {void changed(Object v,int l,int t,int r,int b,int ol,int ot,int or,int ob);}
  interface Touch {boolean touch(Object v,android.view.MotionEvent event);}
  static class Web {
    int width=1080,height=1600,initial,zoomCalls,scriptCalls;float scale=3;boolean measuredViewportRequired;String url="https://chatgpt.com/c/one",script="";Layout layout;Touch touch;BrowserReading reading;
    boolean requiresViewportMeasurement(){return measuredViewportRequired;}
    boolean readingPage(String target){return BrowserReadingPolicy.chat(target);}
    boolean setReadingLayout(float choice){return false;}
    void addOnLayoutChangeListener(Layout cb){layout=cb;}void setOnTouchListener(Touch cb){touch=cb;}int getWidth(){return width;}String getUrl(){return url;}void setInitialScale(int percent){initial=percent;}float getScale(){return scale;}
    void zoomBy(float factor){zoomCalls++;scale*=factor;if(reading!=null)reading.scaled(scale);}void evaluateJavascript(String code,Object cb){scriptCalls++;script=code;}
    void size(int w,int h){int priorW=width,priorH=height;width=w;height=h;layout.changed(this,0,0,w,h,0,0,priorW,priorH);}
  }
}
