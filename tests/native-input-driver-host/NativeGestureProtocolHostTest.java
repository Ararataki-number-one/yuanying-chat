package local.pocketchat.inputdriver;

/** Execute the shipping test driver's scheduler with a controlled monotonic clock. */
public final class NativeGestureProtocolHostTest {
  static int checks;
  static void check(boolean ok){checks++;if(!ok)throw new AssertionError("protocol control "+checks);}
  static final class Runtime implements NativeGestureProtocol.Clock,NativeGestureProtocol.Injector {
    long time=1000; int calls; long downDelay,upDelay; int reject=-1; boolean lateCall;
    public long now(){return time;}
    public void until(long deadline){time=Math.max(time,deadline);}
    public NativeGestureProtocol.Attempt inject(int action,long down,long planned,long expiry,float x,float y,boolean cleanup){
      NativeGestureProtocol.Attempt r=new NativeGestureProtocol.Attempt();r.action=action;r.downTime=down;r.planned=planned;r.x=x;r.y=y;r.cleanup=cleanup;r.sync=action==1;
      r.eventTime=time;r.callStart=time+(lateCall?33:0);r.injected=true;r.accepted=cleanup||calls++!=reject;
      if(action==0)time+=downDelay;if(action==1)time+=upDelay;r.callEnd=Math.max(time,r.callStart);time=r.callEnd;return r;
    }
    NativeGestureProtocol.Trace run(String profile,long deadline){return NativeGestureProtocol.run(this,this,t->{},NativeGestureProtocol.profile(profile),deadline,540,1469,567);}
  }
  public static void main(String[] ignored){
    for(String profile:new String[]{"qualification","formal-collapse"}){
      Runtime r=new Runtime();NativeGestureProtocol.Trace t=r.run(profile,21000);int interval=profile.equals("qualification")?15:16;
      check(t.passed()&&t.events.size()==21&&t.cleanup==null);
      check(t.events.stream().filter(e->e.action==2).count()==19);
      check(t.events.get(20).eventTime==1000+20*interval&&t.events.get(20).y==567);
      check(t.events.stream().allMatch(e->e.downTime==1000));
      check(t.events.stream().filter(e->e.sync).count()==1&&t.events.get(20).sync);
    }
    Runtime delayed=new Runtime();delayed.downDelay=319;NativeGestureProtocol.Trace t=delayed.run("qualification",21000);
    check(!t.passed()&&t.events.size()==1&&t.events.get(0).callEnd-t.events.get(0).callStart==319);
    check(t.cleanup!=null&&t.cleanup.action==3&&t.cleanup.cleanup&&!t.cleanup.sync);
    Runtime expired=new Runtime();t=expired.run("qualification",1299);check(!t.passed()&&t.events.isEmpty()&&t.cleanup==null);
    Runtime rejection=new Runtime();rejection.reject=5;t=rejection.run("qualification",21000);check(!t.passed()&&t.events.size()==6&&t.cleanup!=null);
    Runtime late=new Runtime();late.lateCall=true;t=late.run("qualification",21000);check(!t.passed()&&t.events.size()==1&&t.cleanup!=null);
    Runtime upWait=new Runtime();upWait.upDelay=40;t=upWait.run("qualification",21000);check(t.passed()&&t.events.get(20).callEnd==1340&&t.events.get(20).eventTime==1300);
    Runtime upExpired=new Runtime();upExpired.upDelay=20000;t=upExpired.run("qualification",21000);check(!t.passed()&&t.events.size()==21&&t.cleanup==null);
    Runtime boundary=new Runtime();boundary.downDelay=45;t=boundary.run("qualification",21000);check(t.passed()&&t.events.get(1).planned==1015&&t.events.get(1).eventTime==1045);
    Runtime missed=new Runtime();missed.downDelay=46;t=missed.run("qualification",21000);check(!t.passed()&&t.events.size()==1);
    boolean unknown=false;try{NativeGestureProtocol.profile("slower");}catch(IllegalArgumentException expected){unknown=true;}check(unknown);
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"scope\":\"real scheduler methods with controlled clock; no Android\"}");
  }
}
