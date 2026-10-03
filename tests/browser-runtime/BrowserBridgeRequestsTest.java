package local.pocketchat;

import java.util.*;

/** Adversarial ordering during reload, popup closing and extension reconnect. */
public final class BrowserBridgeRequestsTest {
  static final class Clock implements BrowserBridgeRequests.Timer {
    final List<Runnable> tasks=new ArrayList<>();
    public void schedule(Runnable task,long delay){tasks.add(task);}
    public void cancel(Runnable task){tasks.remove(task);}
    void advance(){for(Runnable task:new ArrayList<>(tasks))task.run();}
  }
  static int checks;
  static void check(String message,boolean value){if(!value)throw new AssertionError(message);checks++;}
  public static void main(String[] args){
    Clock clock=new Clock();BrowserBridgeRequests bridge=new BrowserBridgeRequests(clock,"null");
    Object oldPage=new Object(),newPage=new Object();List<String> received=new ArrayList<>();
    int old=bridge.add(oldPage,value->received.add("old:"+value),10000);
    int next=bridge.add(newPage,value->received.add("new:"+value),10000);
    check("A stale connection cannot answer the new page",!bridge.complete(oldPage,next,"wrong"));
    check("Rejecting a stale answer keeps both requests pending",bridge.size()==2&&received.isEmpty());
    bridge.cancel(oldPage);
    check("Closing a popup cancels only its own page",received.equals(Arrays.asList("old:null"))&&bridge.size()==1);
    bridge.cancel(oldPage);
    check("The old page's delayed disconnect leaves the new request intact",bridge.size()==1&&received.size()==1);
    check("The new page still receives its result",bridge.complete(newPage,next,"correct")&&received.get(1).equals("new:correct"));
    check("Completed requests release their timeout tasks",clock.tasks.isEmpty());
    check("Duplicate answers never call the user callback twice",!bridge.complete(newPage,next,"duplicate")&&received.size()==2);
    check("Old page answers remain ignored after navigation",!bridge.complete(oldPage,old,"late"));
    int stalled=bridge.add(newPage,value->received.add("timeout:"+value),10000);clock.advance();clock.advance();
    check("A stalled request completes exactly once",received.get(2).equals("timeout:null")&&received.size()==3&&bridge.size()==0);
    check("Answers after timeout cannot revive an expired request",!bridge.complete(newPage,stalled,"late"));
    bridge.add(newPage,null,10000);
    check("Fire-and-forget evaluation retains neither callback nor timeout",clock.tasks.isEmpty()&&bridge.size()==0);
    bridge.add(oldPage,value->{received.add("replace:"+value);bridge.add(newPage,v->received.add("replacement:"+v),10000);},10000);
    bridge.cancel(oldPage);
    check("A retry created by cancellation belongs to the new connection",bridge.size()==1);
    bridge.cancel(oldPage);clock.advance();
    check("An old disconnect cannot cancel a reentrant retry",received.get(received.size()-1).equals("replacement:null")&&bridge.size()==0);
    BrowserBridgeRequests cookies=new BrowserBridgeRequests(clock,null);List<String> cookieValues=new ArrayList<>();
    Object oldHost=new Object(),newHost=new Object();
    cookies.add(oldHost,cookieValues::add,5000);int current=cookies.add(newHost,cookieValues::add,5000);
    cookies.cancel(oldHost);
    check("Cookie reconnect reports old-host failure with actual null",cookieValues.size()==1&&cookieValues.get(0)==null);
    check("The new host's cookies are still returned",cookies.complete(newHost,current,"session=synthetic")&&cookieValues.get(1).equals("session=synthetic"));
    check("Repeated cookie requests do not accumulate completed timers",clock.tasks.isEmpty());
    for(int i=0;i<1000;i++){int id=bridge.add(newPage,value->{},10000);bridge.complete(newPage,id,"ok");}
    check("Continuous browser inspection releases 1000 completed requests",bridge.size()==0&&clock.tasks.isEmpty());
    bridge.add(oldPage,value->received.add("closed:"+value),10000);bridge.add(newPage,value->received.add("closed:"+value),10000);bridge.clear();
    check("Shutdown releases both connections and their timers",bridge.size()==0&&clock.tasks.isEmpty());
    System.out.println("{\"passed\":"+checks+",\"scope\":\"production request lifecycle on JVM, no Android renderer\"}");
  }
}
