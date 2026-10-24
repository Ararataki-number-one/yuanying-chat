package local.pocketchat;

import java.util.List;
import java.util.function.Consumer;
import java.util.function.LongSupplier;
import org.json.JSONObject;
import org.mozilla.geckoview.AllowOrDeny;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.WebRequestError;

/** Fixture-only navigation preparation. Never changes the restore payload or deadline. */
final class GeckoLocalDraftBlankBarrier implements GeckoSession.ProgressDelegate, GeckoSession.NavigationDelegate {
  interface Owner {boolean current();long epoch();boolean committed(String uri);}
  final GeckoSession session;final Owner owner;final LongSupplier clock;final Consumer<Throwable> failed;
  final GeckoSession.ProgressDelegate progress;final GeckoSession.NavigationDelegate navigation;
  final String nonce,phase,uri;final long command,deadline,requestedAt,requestEpoch;
  long startedAt=-1,committedAt=-1,stoppedAt=-1,commitEpoch=-1;
  boolean completed,closed;String error="";

  GeckoLocalDraftBlankBarrier(GeckoSession session,String nonce,long command,String phase,long deadline,
      Owner owner,LongSupplier clock,Consumer<Throwable> failed){
    if(session==null||nonce==null||!nonce.matches("[0-9a-f]{32}")||command<1
        ||!("off".equals(phase)||"stale-on".equals(phase)||"fresh-on".equals(phase)))
      throw new IllegalArgumentException("Foreign F04 blank owner");
    this.session=session;this.nonce=nonce;this.command=command;this.phase=phase;this.deadline=deadline;
    this.owner=owner;this.clock=clock;this.failed=failed;requestedAt=clock.getAsLong();requestEpoch=owner.epoch();
    uri="http://127.0.0.1:8765/f04-restore-blank?nonce="+nonce+"&command="+command+"&phase="+phase;
    progress=session.getProgressDelegate();navigation=session.getNavigationDelegate();
    if(!session.isOpen()||!owner.current()||requestedAt>=deadline||requestEpoch<0||progress==null||navigation==null)
      throw new IllegalStateException("F04 blank owner is not live");
    session.setProgressDelegate(this);session.setNavigationDelegate(this);
  }
  boolean valid(){
    if(closed)return false;
    if(!owner.current()||!session.isOpen()||session.getProgressDelegate()!=this||session.getNavigationDelegate()!=this){reject("owner changed");return false;}
    if(clock.getAsLong()>deadline){reject("original deadline exceeded");return false;}
    long expected=committedAt<0?requestEpoch:commitEpoch;
    if(owner.epoch()!=expected){reject("navigation epoch changed");return false;}
    return true;
  }
  void reject(String reason){if(closed)return;error=reason;close();failed.accept(new IllegalStateException("F04 blank barrier: "+reason));}
  boolean ready(){return valid()&&completed&&owner.committed(uri);}
  void close(){
    if(session.getProgressDelegate()==this)session.setProgressDelegate(progress);
    if(session.getNavigationDelegate()==this)session.setNavigationDelegate(navigation);
    closed=true;
  }
  JSONObject proof(){return J.obj("schema",1,"kind","nonce-owned-local-blank-navigation","nonce",nonce,
      "command",command,"phase",phase,"uri",uri,"session",System.identityHashCode(session),
      "requestedAtElapsedRealtime",requestedAt,"startedAtElapsedRealtime",startedAt,
      "committedAtElapsedRealtime",committedAt,"stoppedAtElapsedRealtime",stoppedAt,
      "deadlineElapsedRealtime",deadline,"requestEpoch",requestEpoch,"commitEpoch",commitEpoch,
      "completed",completed,"error",error,"fixturePreparation",true,"realChatGPT",false);}

  @Override public void onPageStart(GeckoSession s,String target){
    progress.onPageStart(s,target);
    if(s!=session||!valid())return;
    if(!uri.equals(target)){if(startedAt>=0)reject("foreign navigation after owned start");return;}
    if(startedAt>=0){reject("duplicate owned start");return;}
    startedAt=clock.getAsLong();
  }
  @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){
    // Validate before forwarding: the production location callback may advance
    // its epoch once as it registers this exact owned navigation.
    boolean before=s==session&&valid();
    navigation.onLocationChange(s,target,permissions,gesture);
    if(!before||closed)return;
    if(!uri.equals(target)){if(startedAt>=0)reject("foreign location after owned start");return;}
    long epoch=owner.epoch();
    if(startedAt<0||committedAt>=0||!owner.current()||!owner.committed(uri)
        ||(epoch!=requestEpoch&&epoch!=requestEpoch+1)){reject("unowned location commit");return;}
    committedAt=clock.getAsLong();commitEpoch=epoch;
    valid();
  }
  @Override public void onPageStop(GeckoSession s,boolean success){
    progress.onPageStop(s,success);
    if(s!=session||!valid()||startedAt<0)return;
    if(!success||committedAt<0||!owner.committed(uri)||completed){reject("uncommitted or failed owned stop");return;}
    stoppedAt=clock.getAsLong();completed=true;
  }
  @Override public void onProgressChange(GeckoSession s,int value){progress.onProgressChange(s,value);}
  @Override public void onSecurityChange(GeckoSession s,SecurityInformation value){progress.onSecurityChange(s,value);}
  @Override public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState value){progress.onSessionStateChange(s,value);}
  @Override public void onCanGoBack(GeckoSession s,boolean value){navigation.onCanGoBack(s,value);}
  @Override public void onCanGoForward(GeckoSession s,boolean value){navigation.onCanGoForward(s,value);}
  @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest value){return navigation.onLoadRequest(s,value);}
  @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest value){return navigation.onSubframeLoadRequest(s,value);}
  @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String value){return navigation.onNewSession(s,value);}
  @Override public GeckoResult<String> onLoadError(GeckoSession s,String uri,WebRequestError error){return navigation.onLoadError(s,uri,error);}
}
