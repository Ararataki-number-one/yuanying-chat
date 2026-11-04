package local.pocketchat;

import java.util.*;

public final class FrameSchedulerTest {
  static int checks;
  static void check(boolean pass,String label){checks++;if(!pass)throw new AssertionError(label);}
  static final class Frames implements UiFrameScheduler.Frames {
    final List<Runnable> queue=new ArrayList<>();int maximum,cancelled;
    public void post(Runnable work){queue.add(work);maximum=Math.max(maximum,queue.size());}
    public void cancel(Runnable work){if(queue.remove(work))cancelled++;}
    void frame(){List<Runnable> now=new ArrayList<>(queue);queue.clear();for(Runnable work:now)work.run();}
  }
  public static void main(String[] args){
    Frames frames=new Frames();int[] source={0},renders={0},seen={0};UiFrameScheduler scheduler=new UiFrameScheduler(frames,()->{renders[0]++;seen[0]=source[0];});
    scheduler.request();check(frames.queue.isEmpty(),"Hidden activity queues no rendering");
    scheduler.visible(true);for(int i=1;i<=1000;i++){source[0]=i;scheduler.request();}
    check(frames.maximum==1&&frames.queue.size()==1,"1000 updates occupy one frame callback");frames.frame();check(renders[0]==1&&seen[0]==1000,"A burst renders its latest state once");
    scheduler.request();Runnable stale=frames.queue.get(0);scheduler.visible(false);check(frames.queue.isEmpty()&&frames.cancelled==1,"Pause removes pending frame work");
    scheduler.visible(true);stale.run();check(renders[0]==1&&frames.queue.size()==1,"Old queued callback cannot render or erase resumed work");frames.frame();check(renders[0]==2,"Resume paints the latest state");
    scheduler.visible(true);check(frames.queue.isEmpty(),"Repeated resume signal does not repaint");scheduler.request();scheduler.close();frames.frame();scheduler.visible(true);scheduler.request();check(frames.queue.isEmpty()&&renders[0]==2,"Destroy prevents current and future work");
    Frames reentrant=new Frames();UiFrameScheduler[] lane=new UiFrameScheduler[1];int[] count={0};lane[0]=new UiFrameScheduler(reentrant,()->{if(++count[0]==1)lane[0].request();});lane[0].visible(true);reentrant.frame();check(count[0]==1&&reentrant.queue.size()==1,"Update during paint gets one later frame");reentrant.frame();check(count[0]==2&&reentrant.queue.isEmpty(),"Reentrant update does not spin within same frame");
    System.out.println("Frame scheduler: "+checks+" checks; 1000 burst notifications -> 1 queued callback / 1 latest-state render; no Android frame-time claim");
  }
}
