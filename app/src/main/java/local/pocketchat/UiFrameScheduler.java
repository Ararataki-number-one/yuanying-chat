package local.pocketchat;

/** A bounded presentation lane. Session state changes remain immediate; views draw the latest state once per frame. */
final class UiFrameScheduler {
  interface Frames {void post(Runnable frame);void cancel(Runnable frame);}
  final Frames frames;final Runnable render;boolean visible,closed;long epoch;Runnable pending;
  UiFrameScheduler(Frames frames,Runnable render){this.frames=frames;this.render=render;}
  void request(){
    if(!visible||closed||pending!=null)return;
    final long ticket=epoch;pending=()->{if(closed||!visible||ticket!=epoch)return;pending=null;render.run();};frames.post(pending);
  }
  void visible(boolean value){
    if(closed||visible==value)return;visible=value;epoch++;
    if(pending!=null){frames.cancel(pending);pending=null;}
    if(value)request();
  }
  void close(){visible(false);closed=true;}
}
