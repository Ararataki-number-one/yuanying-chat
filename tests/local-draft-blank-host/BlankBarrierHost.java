package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.*;

/** Executes the complete fixture helper with controlled delegate/clock adapters. */
public final class BlankBarrierHost {
  static final String NONCE="0123456789abcdef0123456789abcdef";
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.put(J.obj("name",name,"pass",true));}
  static final class Call {
    final String name;final Object[] arguments;
    Call(String name,Object... arguments){this.name=name;this.arguments=arguments;}
  }
  static final class Rig implements GeckoLocalDraftBlankBarrier.Owner {
    final GeckoSession session=new GeckoSession(),foreign=new GeckoSession();
    final Original original=new Original(this);
    final ArrayList<Throwable> failures=new ArrayList<>();
    long now=100,epoch=7,command=11,expectedCommand=11;boolean active=true;
    String committed="about:blank";int commitAdvance=1;Runnable locationHook,stopHook;
    GeckoLocalDraftBlankBarrier barrier;
    Rig(){session.setProgressDelegate(original);session.setNavigationDelegate(original);}
    public boolean current(){return active&&command==expectedCommand;}
    public long epoch(){return epoch;}
    public boolean committed(String uri){return uri.equals(committed);}
    GeckoLocalDraftBlankBarrier install(){return install(NONCE,11,"off",1000);}
    GeckoLocalDraftBlankBarrier install(String nonce,long serial,String phase,long deadline){
      barrier=new GeckoLocalDraftBlankBarrier(session,nonce,serial,phase,deadline,this,()->now,failures::add);return barrier;
    }
    void start(){now=200;barrier.onPageStart(session,barrier.uri);}
    void commit(){now=300;barrier.onLocationChange(session,barrier.uri,new ArrayList<>(),Boolean.FALSE);}
    void stop(){now=400;barrier.onPageStop(session,true);}
    void complete(){start();commit();stop();}
    void rejected(String label){check(label,!barrier.ready()&&barrier.closed&&!barrier.completed&&failures.size()==1);}
  }
  static final class Original implements GeckoSession.ProgressDelegate,GeckoSession.NavigationDelegate {
    final Rig rig;final ArrayList<Call> calls=new ArrayList<>();
    final GeckoResult<AllowOrDeny> load=new GeckoResult<>(AllowOrDeny.DENY),subframe=new GeckoResult<>(AllowOrDeny.ALLOW);
    final GeckoResult<GeckoSession> popup=new GeckoResult<>(new GeckoSession());
    final GeckoResult<String> errorResult=new GeckoResult<>("about:original-error");
    String throwsAt;RuntimeException exception=new IllegalStateException("original callback exception");
    Original(Rig rig){this.rig=rig;}
    void record(String name,Object... args){calls.add(new Call(name,args));if(name.equals(throwsAt))throw exception;}
    public void onPageStart(GeckoSession s,String uri){record("start",s,uri);}
    public void onPageStop(GeckoSession s,boolean ok){record("stop",s,ok);if(rig.stopHook!=null)rig.stopHook.run();}
    public void onProgressChange(GeckoSession s,int value){record("progress",s,value);}
    public void onSecurityChange(GeckoSession s,SecurityInformation value){record("security",s,value);}
    public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState value){record("state",s,value);}
    public void onLocationChange(GeckoSession s,String uri,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
      record("location",s,uri,permissions,gesture);
      if(s==rig.session){rig.committed=uri;rig.epoch+=rig.commitAdvance;}
      if(rig.locationHook!=null)rig.locationHook.run();
    }
    public void onCanGoBack(GeckoSession s,boolean value){record("back",s,value);}
    public void onCanGoForward(GeckoSession s,boolean value){record("forward",s,value);}
    public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest value){record("load",s,value);return load;}
    public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest value){record("subframe",s,value);return subframe;}
    public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String uri){record("new",s,uri);return popup;}
    public GeckoResult<String> onLoadError(GeckoSession s,String uri,WebRequestError error){record("error",s,uri,error);return errorResult;}
  }
  static void exactForwarding(){
    Rig r=new Rig();r.install();GeckoSession f=r.foreign;
    String uri=new String("http://controlled.invalid/original");
    ArrayList<GeckoSession.PermissionDelegate.ContentPermission> perms=new ArrayList<>();
    GeckoSession.ProgressDelegate.SecurityInformation security=new GeckoSession.ProgressDelegate.SecurityInformation();
    GeckoSession.SessionState state=new GeckoSession.SessionState();
    GeckoSession.NavigationDelegate.LoadRequest load=new GeckoSession.NavigationDelegate.LoadRequest();
    WebRequestError error=new WebRequestError();
    r.barrier.onPageStart(f,uri);r.barrier.onPageStop(f,false);r.barrier.onProgressChange(f,37);
    r.barrier.onSecurityChange(f,security);r.barrier.onSessionStateChange(f,state);
    r.barrier.onLocationChange(f,uri,perms,Boolean.TRUE);r.barrier.onCanGoBack(f,true);r.barrier.onCanGoForward(f,false);
    check("Original load decision object forwarded unchanged",r.barrier.onLoadRequest(f,load)==r.original.load);
    check("Original subframe decision object forwarded unchanged",r.barrier.onSubframeLoadRequest(f,load)==r.original.subframe);
    check("Original new-session result object forwarded unchanged",r.barrier.onNewSession(f,uri)==r.original.popup);
    check("Original load-error result object forwarded unchanged",r.barrier.onLoadError(f,uri,error)==r.original.errorResult);
    String[] names={"start","stop","progress","security","state","location","back","forward","load","subframe","new","error"};
    Object[][] expected={{f,uri},{f,false},{f,37},{f,security},{f,state},{f,uri,perms,Boolean.TRUE},{f,true},{f,false},{f,load},{f,load},{f,uri},{f,uri,error}};
    check("All twelve original callbacks forwarded exactly once",r.original.calls.size()==12);
    for(int i=0;i<names.length;i++){
      Call call=r.original.calls.get(i);boolean same=call.name.equals(names[i])&&call.arguments.length==expected[i].length;
      for(int j=0;same&&j<expected[i].length;j++)same=call.arguments[j]==expected[i][j];
      check("Original callback argument identities preserved: "+names[i],same);
    }
    check("Foreign callbacks cannot complete or reject owned navigation",!r.barrier.ready()&&!r.barrier.closed&&r.failures.isEmpty());
    r.barrier.close();check("Closing owned wrapper restores both exact delegates",r.session.getProgressDelegate()==r.original&&r.session.getNavigationDelegate()==r.original);
  }
  static void exceptions(){
    for(String name:new String[]{"start","stop","progress","security","state","location","back","forward","load","subframe","new","error"}){
      Rig r=new Rig();r.install();r.original.throwsAt=name;Throwable seen=null;
      try{
        switch(name){
          case "start":r.barrier.onPageStart(r.session,r.barrier.uri);break;
          case "stop":r.barrier.onPageStop(r.session,true);break;
          case "progress":r.barrier.onProgressChange(r.session,10);break;
          case "security":r.barrier.onSecurityChange(r.session,new GeckoSession.ProgressDelegate.SecurityInformation());break;
          case "state":r.barrier.onSessionStateChange(r.session,new GeckoSession.SessionState());break;
          case "location":r.barrier.onLocationChange(r.session,r.barrier.uri,new ArrayList<>(),false);break;
          case "back":r.barrier.onCanGoBack(r.session,true);break;
          case "forward":r.barrier.onCanGoForward(r.session,true);break;
          case "load":r.barrier.onLoadRequest(r.session,new GeckoSession.NavigationDelegate.LoadRequest());break;
          case "subframe":r.barrier.onSubframeLoadRequest(r.session,new GeckoSession.NavigationDelegate.LoadRequest());break;
          case "new":r.barrier.onNewSession(r.session,"original");break;
          case "error":r.barrier.onLoadError(r.session,"original",new WebRequestError());break;
        }
      }catch(Throwable error){seen=error;}
      check("Original callback exception is not swallowed or replaced: "+name,seen==r.original.exception&&r.original.calls.size()==1&&!r.barrier.completed&&r.failures.isEmpty());
      r.barrier.close();
    }
  }
  static void accepted()throws Exception{
    for(int delta:new int[]{0,1}){
      Rig r=new Rig();r.commitAdvance=delta;r.install();check("Installed live barrier remains pending before start epoch+"+delta,!r.barrier.ready());
      r.start();check("Owned start alone cannot pass epoch+"+delta,!r.barrier.ready());
      r.commit();check("Actual commit alone cannot pass epoch+"+delta,!r.barrier.ready());r.stop();
      check("Owned start commit success-stop admits epoch+"+delta,r.barrier.ready()&&r.failures.isEmpty());
      JSONObject proof=r.barrier.proof();
      check("Proof reports actual nonce command phase and URI epoch+"+delta,proof.getString("nonce").equals(NONCE)&&proof.getLong("command")==11&&proof.getString("phase").equals("off")&&proof.getString("uri").equals(r.barrier.uri)&&proof.getInt("session")==System.identityHashCode(r.session));
      check("Proof reports original deadline and actual event times epoch+"+delta,proof.getLong("requestedAtElapsedRealtime")==100&&proof.getLong("startedAtElapsedRealtime")==200&&proof.getLong("committedAtElapsedRealtime")==300&&proof.getLong("stoppedAtElapsedRealtime")==400&&proof.getLong("deadlineElapsedRealtime")==1000&&proof.getLong("requestEpoch")==7&&proof.getLong("commitEpoch")==7+delta);
      check("Proof scope is fixture preparation without real ChatGPT epoch+"+delta,proof.getBoolean("completed")&&proof.getBoolean("fixturePreparation")&&!proof.getBoolean("realChatGPT")&&proof.getString("error").isEmpty());
      int count=r.original.calls.size();r.barrier.ready();r.barrier.proof();
      check("Reading ready and proof does not inject callbacks epoch+"+delta,r.original.calls.size()==count);
      proof.put("completed",false);check("Returned proof mutation cannot alter barrier epoch+"+delta,r.barrier.ready()&&r.barrier.proof().getBoolean("completed"));
      r.barrier.close();
    }
    for(String phase:new String[]{"off","stale-on","fresh-on"}){
      Rig r=new Rig();r.install(NONCE,23,phase,1000);
      check("URI binds exact nonce command and phase "+phase,r.barrier.uri.equals("http://127.0.0.1:8765/f04-restore-blank?nonce="+NONCE+"&command=23&phase="+phase));r.barrier.close();
    }
  }
  static void rejected(){
    Rig r=new Rig();r.commitAdvance=0;r.install();r.barrier.onPageStart(r.session,"about:blank");r.barrier.onLocationChange(r.session,"about:blank",new ArrayList<>(),false);r.barrier.onPageStop(r.session,true);
    check("Old about-blank callbacks and cached URL cannot satisfy new request",!r.barrier.ready()&&!r.barrier.closed&&r.failures.isEmpty()&&r.barrier.startedAt==-1);r.barrier.close();
    r=new Rig();r.install();r.barrier.onPageStart(r.session,r.barrier.uri.replace(NONCE,"f".repeat(32)));check("Another invocation nonce cannot start this barrier",r.barrier.startedAt==-1&&!r.barrier.ready());r.barrier.close();
    r=new Rig();r.install();r.barrier.onPageStart(r.session,r.barrier.uri.replace("command=11","command=12"));check("Another command URI cannot start this barrier",r.barrier.startedAt==-1&&!r.barrier.ready());r.barrier.close();
    r=new Rig();r.install();r.barrier.onPageStart(r.session,r.barrier.uri.replace("phase=off","phase=stale-on"));check("Another phase URI cannot start this barrier",r.barrier.startedAt==-1&&!r.barrier.ready());r.barrier.close();
    r=new Rig();r.install();r.start();r.barrier.onPageStart(r.session,r.barrier.uri);r.rejected("Duplicate owned start fails closed");
    r=new Rig();r.install();r.start();r.barrier.onPageStart(r.session,"http://127.0.0.1:8765/other");r.rejected("Foreign start after owned start fails closed");
    r=new Rig();r.install();r.start();r.barrier.onLocationChange(r.session,"http://127.0.0.1:8765/other",new ArrayList<>(),false);r.rejected("Foreign location after owned start fails closed");
    r=new Rig();r.install();r.commit();r.rejected("Commit without owned start fails closed");
    r=new Rig();r.install();r.start();r.barrier.onPageStop(r.session,true);r.rejected("Success stop without actual commit fails closed");
    r=new Rig();r.install();r.start();r.commit();r.barrier.onPageStop(r.session,false);r.rejected("Failed stop cannot complete owned blank");
    r=new Rig();r.install();r.start();r.commit();r.now=1001;r.barrier.onPageStop(r.session,true);r.rejected("Late completion cannot extend original deadline");
    r=new Rig();r.install();r.start();r.now=1001;r.barrier.ready();r.rejected("Pending barrier expiration fails at original deadline");
    r=new Rig();r.install();r.start();r.command=12;r.barrier.onPageStop(r.session,true);r.rejected("Superseding command rejects old callback ownership");
    r=new Rig();r.install();r.epoch++;r.barrier.onPageStart(r.session,r.barrier.uri);r.rejected("Epoch change before owned start fails closed");
    r=new Rig();r.install();r.start();r.epoch++;r.commit();r.rejected("Epoch change before owned commit fails closed");
    r=new Rig();r.commitAdvance=2;r.install();r.start();r.commit();r.rejected("Own commit may not advance epoch twice");
    r=new Rig();r.install();r.start();r.commit();r.epoch++;r.barrier.onPageStop(r.session,true);r.rejected("Epoch change after commit fails closed");
    r=new Rig();r.install();r.start();r.commit();r.committed="another-document";r.barrier.onPageStop(r.session,true);r.rejected("Changed committed document cannot pass owned stop");
    r=new Rig();r.install();r.session.open=false;r.barrier.ready();r.rejected("Closed session rejects barrier");
    r=new Rig();r.install();r.active=false;r.barrier.ready();r.rejected("Retired fixture rejects barrier");
    for(boolean progress:new boolean[]{true,false}){
      r=new Rig();r.install();Original replacement=new Original(r);
      if(progress)r.session.setProgressDelegate(replacement);else r.session.setNavigationDelegate(replacement);
      r.barrier.ready();r.rejected("Replacing "+(progress?"progress":"navigation")+" delegate rejects stale wrapper");
      check("Close cannot overwrite replacement "+(progress?"progress":"navigation")+" delegate",progress?r.session.getProgressDelegate()==replacement:r.session.getNavigationDelegate()==replacement);
      check("Close restores other still-owned delegate "+progress,progress?r.session.getNavigationDelegate()==r.original:r.session.getProgressDelegate()==r.original);
    }
    r=new Rig();r.install();r.complete();r.barrier.onPageStop(r.session,true);check("Duplicate completed stop rejects without a second accepted transition",!r.barrier.ready()&&r.barrier.closed&&r.failures.size()==1);
    r=new Rig();r.install();r.barrier.close();r.barrier.close();check("Closing twice is silent and never completes a pending request",!r.barrier.ready()&&r.failures.isEmpty()&&r.session.getProgressDelegate()==r.original&&r.session.getNavigationDelegate()==r.original);
  }
  static void constructorControls(){
    for(String nonce:new String[]{null,"","g".repeat(32),"f".repeat(31),"F".repeat(32)}){
      Rig r=new Rig();Throwable seen=null;try{r.install(nonce,11,"off",1000);}catch(Throwable error){seen=error;}
      check("Invalid nonce rejected before delegate replacement: "+nonce,seen instanceof IllegalArgumentException&&r.session.getProgressDelegate()==r.original&&r.session.getNavigationDelegate()==r.original);
    }
    for(String phase:new String[]{null,"seed","foreign"}){
      Rig r=new Rig();Throwable seen=null;try{r.install(NONCE,11,phase,1000);}catch(Throwable error){seen=error;}
      check("Invalid restore phase rejected before delegate replacement: "+phase,seen instanceof IllegalArgumentException&&r.session.getProgressDelegate()==r.original&&r.session.getNavigationDelegate()==r.original);
    }
    for(long command:new long[]{0,-1}){
      Rig r=new Rig();Throwable seen=null;try{r.install(NONCE,command,"off",1000);}catch(Throwable error){seen=error;}
      check("Invalid command rejected before delegate replacement: "+command,seen instanceof IllegalArgumentException&&r.session.getProgressDelegate()==r.original&&r.session.getNavigationDelegate()==r.original);
    }
    for(String fault:new String[]{"closed","retired","deadline","negative-epoch","missing-progress","missing-navigation"}){
      Rig r=new Rig();switch(fault){case "closed":r.session.open=false;break;case "retired":r.active=false;break;case "deadline":r.now=1000;break;case "negative-epoch":r.epoch=-1;break;case "missing-progress":r.session.setProgressDelegate(null);break;case "missing-navigation":r.session.setNavigationDelegate(null);break;}
      Object progress=r.session.getProgressDelegate(),navigation=r.session.getNavigationDelegate();Throwable seen=null;try{r.install();}catch(Throwable error){seen=error;}
      check("Nonlive constructor refuses without installing a wrapper: "+fault,seen instanceof IllegalStateException&&r.session.getProgressDelegate()==progress&&r.session.getNavigationDelegate()==navigation);
    }
  }
  public static void main(String[] args)throws Exception{
    exactForwarding();exceptions();accepted();rejected();constructorControls();
    System.out.println(J.obj("schema",1,"status","passed","checks",checks.length(),"results",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,
      "scope","Complete GeckoLocalDraftBlankBarrier.java with original J.java and controlled clock/owner/delegate-slot adapters; no navigation, SDK runtime or Android execution").toString());
  }
}
