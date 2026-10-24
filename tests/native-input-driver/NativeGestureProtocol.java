package local.pocketchat.inputdriver;

import java.util.ArrayList;

/** Test-only fixed native-input schedule. Never retries or stretches a gesture. */
public final class NativeGestureProtocol {
  public static final int MOVE_COUNT=19;
  public static final class Profile {
    public final String name; public final int duration,interval,maxLate;
    private Profile(String name,int interval){this.name=name;this.interval=interval;this.duration=20*interval;this.maxLate=2*interval;}
  }
  public static Profile profile(String name){
    if("qualification".equals(name))return new Profile(name,15);
    if("formal-collapse".equals(name))return new Profile(name,16);
    throw new IllegalArgumentException("Unknown native input protocol");
  }
  public interface Clock { long now(); void until(long deadline); }
  public interface Injector { Attempt inject(int action,long downTime,long planned,long expires,float x,float y,boolean cleanup); }
  public interface Observer { void changed(Trace trace); }
  public static final class Attempt {
    public int action; public long downTime,planned,eventTime,callStart,callEnd;
    public float x,y; public boolean injected,accepted,cleanup,sync; public String error="";
  }
  public static final class Trace {
    public Profile profile; public long start,expires; public String error=""; public final ArrayList<Attempt> events=new ArrayList<>();
    public Attempt cleanup;
    public boolean passed(){return error.isEmpty()&&events.size()==MOVE_COUNT+2;}
  }
  public static Trace run(Clock clock,Injector injector,Observer observer,Profile profile,long expires,float x,float from,float to){
    Trace trace=new Trace();trace.profile=profile;trace.start=clock.now();trace.expires=expires;
    boolean down=false,up=false;
    try{
      if(trace.start+profile.duration>expires)throw new IllegalStateException("Original input deadline has insufficient time");
      observer.changed(trace);
      for(int i=0;i<MOVE_COUNT+2;i++){
        long planned=trace.start+(long)i*profile.interval;
        clock.until(planned);
        long now=clock.now();
        if(now>expires||now>planned+profile.maxLate)throw new IllegalStateException("Fixed input slot missed");
        int action=i==0?0:i==MOVE_COUNT+1?1:2;
        float y=from+(to-from)*(i*profile.interval/(float)profile.duration);
        Attempt item=injector.inject(action,trace.start,planned,expires,x,y,false);
        trace.events.add(item);
        if(item.injected&&item.accepted){if(action==0)down=true;if(action==1)up=true;}
        if(!item.injected||!item.accepted||!item.error.isEmpty())throw new IllegalStateException("Native input injection rejected: "+item.error);
        if(item.action!=action||item.downTime!=trace.start||item.planned!=planned||item.cleanup
            ||item.eventTime<planned||item.callStart<item.eventTime||item.callEnd<item.callStart
            ||item.eventTime>planned+profile.maxLate||item.callStart>planned+profile.maxLate
            ||item.callStart>expires||item.callEnd>expires||item.sync!=(action==1))throw new IllegalStateException("Invalid or late native input timing");
        observer.changed(trace);
      }
    }catch(Exception failure){trace.error=failure.toString();}
    finally{
      if(down&&!up){
        try{trace.cleanup=injector.inject(3,trace.start,clock.now(),expires,x,to,true);}
        catch(Exception failure){trace.cleanup=new Attempt();trace.cleanup.cleanup=true;trace.cleanup.action=3;trace.cleanup.error=failure.toString();}
      }
      observer.changed(trace);
    }
    return trace;
  }
  private NativeGestureProtocol(){}
}
