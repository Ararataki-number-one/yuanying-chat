package local.pocketchat;

/** Classifies an ordinary reading swipe without consuming or modifying input. */
final class ChromeCollapseGesture {
  static final int NONE=0,HIDE=1,SHOW=-1;
  final float threshold,slop;
  final long longPressTimeout;
  private boolean active,moved;
  private float x,y;
  private long started;

  ChromeCollapseGesture(float threshold,float slop,long longPressTimeout){
    this.threshold=threshold;this.slop=slop;this.longPressTimeout=longPressTimeout;
  }

  void begin(float x,float y,long at,boolean enabled){
    cancel();if(!enabled||!Float.isFinite(x)||!Float.isFinite(y))return;
    active=true;this.x=x;this.y=y;started=at;
  }

  void move(float x,float y,int pointers,long at){
    if(!active)return;
    if(pointers!=1||!Float.isFinite(x)||!Float.isFinite(y)||at<started){cancel();return;}
    float dx=Math.abs(x-this.x),dy=Math.abs(y-this.y);
    // A selection long press and horizontal code/table panning are not reading swipes.
    if(!moved&&at-started>=longPressTimeout||dx>slop&&dx>dy*1.25f){cancel();return;}
    if(Math.max(dx,dy)>slop)moved=true;
  }

  int finish(float x,float y,long at){
    move(x,y,1,at);if(!active)return NONE;
    float dx=Math.abs(x-this.x),dy=y-this.y;cancel();
    if(Math.abs(dy)<threshold||Math.abs(dy)<dx*1.5f)return NONE;
    return dy<0?HIDE:SHOW;
  }

  void cancel(){active=false;moved=false;}
}
