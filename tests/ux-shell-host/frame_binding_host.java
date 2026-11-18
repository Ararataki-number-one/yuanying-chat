package local.pocketchat;

import java.util.*;

/** Exact production model-mirroring/render-request members, with deterministic app adapters. */
final class FrameBindingHost {
  static int checks,immediateSnapshots;
  static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
  static void mirrored(MainActivity owner,int event){
    Session s=owner.session;
    if(owner.pending!=s.pending||owner.entries!=s.entries||owner.networkReady!=s.networkReady
        ||owner.submitting!=s.submitting||!owner.conversation.equals(s.conversation))
      throw new AssertionError("Synchronous model mirrors stale before frame at event "+event);
    immediateSnapshots++;
  }
  static void update(Session session,int event){
    session.pending=new Object();session.entries=new Object();session.networkReady=event%2==0;
    session.submitting=event%3==0;session.conversation="conversation-"+event;session.status="status-"+event;
    session.navigating=event%4==0;if(session.web!=null){session.web.back=event%5==0;session.web.forward=event%7==0;}
  }
  static MainActivity fresh(Frames frames){
    MainActivity owner=new MainActivity();owner.session=new Session();owner.loading=new Loading();owner.designChrome=new Chrome();owner.geckoAddress=new Address();owner.chatDownloadProgress=new ChatDownloadProgressUi(owner);
    owner.remote=new Browser(owner);owner.session.web=owner.remote;owner.toolsPanel=new ToolsState();
    owner.sessionUi=new UiFrameScheduler(frames,owner::applySession);return owner;
  }
  public static void main(String[] args){
    Frames frames=new Frames();MainActivity owner=fresh(frames);owner.sessionUi.visible(true);
    for(int event=1;event<=1000;event++){update(owner.session,event);owner.requestSessionUi();owner.chatDownloadProgress.observer.onChange(false);mirrored(owner,event);}
    owner.session.attachmentIssue=AttachmentIssue.PAGE_CHANGED;
    owner.ticker.run();
    check(immediateSnapshots==1000,"Every one of1000 observer events synchronously exposes current download/conversation model aliases");
    check(frames.queue.size()==1&&frames.posts==1,"1000 observer notifications retain one pending presentation frame");
    check(owner.paints==0&&owner.loading.updates==0&&owner.designChrome.updates==0&&owner.metrics==0,"Coalesced notifications perform no premature native rendering");
    check(owner.geckoAddress.updates==0,"Queued notifications do not refresh the address before their frame");
    check(owner.toolsPanel.updates==0,"Queued notifications do not update the open tools panel before their frame");
    check(owner.session.reading.calls==0&&owner.readingLayouts==0,"Queued notifications do not invoke reading presentation before their frame");
    frames.runOne();
    check(owner.paints==1&&owner.last.conversation.equals("conversation-1000")&&owner.last.pending==owner.session.pending&&owner.last.entries==owner.session.entries,"One frame observes final conversation and object identities");
    check(owner.last.networkReady==owner.session.networkReady&&owner.last.submitting==owner.session.submitting&&owner.last.status.equals("status-1000"),"One frame observes final flags and status");
    check(owner.lastIssue==AttachmentIssue.PAGE_CHANGED,"The session frame carries the typed attachment reason independently of the status wording");
    check(owner.loading.updates==1&&owner.designChrome.updates==1&&owner.metrics==1,"Actual applySession invokes each presentation consumer once");
    check(owner.chatDownloadProgress.updates==1,"Session, download and periodic notifications share the same presentation frame");
    check(owner.geckoAddress.updates==1,"One coalesced frame refreshes the current address once");
    check(owner.toolsPanel.updates==1,"One coalesced frame updates the open tools panel once");
    check(owner.toolsPanel.back&&!owner.toolsPanel.forward&&owner.toolsPanel.loading,"The open tools panel receives the final history and loading state");
    check(owner.session.reading.calls==1&&owner.readingLayouts==1&&!owner.session.reading.keyboardVisible,"The actual reading helper invokes both presentation boundaries once per frame");
    check(owner.handler.delayed==1,"Periodic timer retains its one-second continuation");
    check(frames.queue.isEmpty()&&owner.sessionUi.pending==null,"Completed frame leaves no recurring presentation work");
    int statusPaints=owner.paints,progressPaints=owner.chatDownloadProgress.updates;
    owner.remote.back=false;owner.remote.forward=true;owner.session.navigating=false;
    for(int tick=0;tick<1000;tick++)owner.chatDownloadProgress.observer.onChange(false);owner.ticker.run();
    check(frames.queue.size()==1,"Download-only notifications and the timer share one pending frame");frames.runOne();
    check(owner.paints==statusPaints&&owner.chatDownloadProgress.updates==progressPaints+1,"Download and timer presentation updates do not redisplay unchanged session status");
    check(owner.geckoAddress.updates==2,"The next presentation frame refreshes the address once without replaying the burst");
    check(owner.toolsPanel.updates==2&&!owner.toolsPanel.back&&owner.toolsPanel.forward&&!owner.toolsPanel.loading,"The next presentation frame forwards changed history and completed loading once");
    check(owner.session.reading.calls==2&&owner.readingLayouts==2,"Download and timer updates invoke the actual reading helper once in their shared frame");

    update(owner.session,1001);owner.requestSessionUi();Runnable paused=frames.peek();
    int paints=owner.paints,cancellations=frames.cancels,toolUpdates=owner.toolsPanel.updates;
    owner.sessionUi.visible(false);
    check(frames.queue.isEmpty()&&frames.cancels==cancellations+1,"Pause visibility cancels the pending presentation callback");
    update(owner.session,1002);owner.requestSessionUi();mirrored(owner,1002);
    paused.run();
    check(owner.paints==paints&&frames.queue.isEmpty(),"Paused model events still synchronize but queued or stale frames cannot paint");
    check(owner.toolsPanel.updates==toolUpdates,"Paused and stale frames cannot update the tools panel");
    owner.sessionUi.visible(true);paused.run();
    check(owner.paints==paints&&frames.queue.size()==1,"A previous visibility epoch cannot paint after resume");
    update(owner.session,1003);owner.requestSessionUi();mirrored(owner,1003);frames.runOne();
    check(owner.paints==paints+1&&owner.last.conversation.equals("conversation-1003"),"Resume paints the latest retained model once");
    check(owner.toolsPanel.updates==toolUpdates+1&&owner.toolsPanel.back==owner.remote.back&&owner.toolsPanel.forward==owner.remote.forward&&owner.toolsPanel.loading==owner.session.navigating,"Resume updates tools from the current session once");

    update(owner.session,1004);owner.requestSessionUi();Runnable destroyed=frames.peek();
    Object retainedPending=owner.pending,retainedEntries=owner.entries;String retainedConversation=owner.conversation;
    int readingCalls=owner.session.reading.calls,readingLayouts=owner.readingLayouts;
    paints=owner.paints;cancellations=frames.cancels;toolUpdates=owner.toolsPanel.updates;owner.destroyed=true;owner.sessionUi.close();
    update(owner.session,1005);owner.requestSessionUi();owner.applySession();destroyed.run();
    check(frames.queue.isEmpty()&&frames.cancels==cancellations+1,"Destroy closes the presentation lane and cancels its callback");
    check(owner.paints==paints&&owner.pending==retainedPending&&owner.entries==retainedEntries&&owner.conversation.equals(retainedConversation),"Destroyed observer requests and direct applies neither mutate owner aliases nor paint");
    check(owner.session.reading.calls==readingCalls&&owner.readingLayouts==readingLayouts,"Destroyed applies and stale frames do not invoke reading presentation");
    check(owner.toolsPanel.updates==toolUpdates,"Destroyed applies and stale frames do not update the tools panel");

    MainActivity early=new MainActivity();early.session=new Session();update(early.session,2000);early.requestSessionUi();mirrored(early,2000);
    check(early.paints==1&&early.last.conversation.equals("conversation-2000"),"Startup without an installed frame lane preserves the existing immediate apply path");
    Frames idleFrames=new Frames();MainActivity idle=fresh(idleFrames);update(idle.session,3000);idle.requestSessionUi();mirrored(idle,3000);
    check(idle.paints==0&&idleFrames.queue.isEmpty(),"A not-yet-visible frame lane synchronizes model aliases without scheduling paint");
    idle.sessionUi.visible(true);Session replacement=new Session();replacement.web=idle.remote;update(replacement,3001);idle.session=replacement;idle.requestSessionUi();mirrored(idle,3001);idleFrames.runOne();
    check(idle.last.pending==replacement.pending&&idle.last.entries==replacement.entries&&idle.last.conversation.equals("conversation-3001"),"A queued frame uses the current session after owner session replacement");
    int before=idle.paints;idle.session=null;idle.requestSessionUi();idleFrames.runOne();
    check(idle.paints==before,"Missing session is safe and cannot render stale session data");
    MainActivity reading=new MainActivity();reading.session=new Session();reading.keyboardVisible=true;
    reading.updateReadingLayout();check(!reading.session.reading.keyboardVisible&&reading.readingLayouts==1,"A visible keyboard without a hub does not enable reading keyboard mode");
    reading.hub=new AppHub();reading.hub.page=AppHub.CHAT;reading.updateReadingLayout();
    check(reading.session.reading.keyboardVisible&&reading.session.reading.calls==2&&reading.readingLayouts==2,"The actual helper forwards visible keyboard state on the chat page");
    reading.hub.page=AppHub.CHAT+1;reading.updateReadingLayout();check(!reading.session.reading.keyboardVisible,"A non-chat page clears reading keyboard mode");
    reading.hub.page=AppHub.CHAT;reading.keyboardVisible=false;reading.updateReadingLayout();check(!reading.session.reading.keyboardVisible,"A hidden keyboard clears reading keyboard mode on chat");
    reading.session=null;reading.updateReadingLayout();check(reading.readingLayouts==5,"The actual helper invokes the focus-layout boundary even without a session");
    System.out.println("{\"status\":\"passed\",\"passed\":"+checks+",\"total\":"+checks+",\"burstEvents\":1000,\"burstPendingFrames\":1,\"burstPaints\":1,\"immediateModelSnapshotsVerified\":"+immediateSnapshots+",\"actualAndroidExecution\":false}");
  }
}

final class MainActivity {
  boolean active=true;final HostHandler handler=new HostHandler();
  boolean finishing;boolean isFinishing(){return finishing;}
  boolean keyboardVisible;AppHub hub;int readingLayouts;
  void applyFocusLayout(){readingLayouts++;}
  Session session;UiFrameScheduler sessionUi;boolean destroyed,networkReady,submitting,sessionStatusDirty=true;
  Object pending,entries;String conversation="";Loading loading;Chrome designChrome;Address geckoAddress;ChatDownloadProgressUi chatDownloadProgress;
  Browser remote;ToolsState toolsPanel;
  int paints,metrics;Paint last;
  AttachmentIssue lastIssue;
  void renderStatus(String value,AttachmentIssue issue){lastIssue=issue;paints++;last=new Paint(pending,entries,conversation,networkReady,submitting,value);}
  /* PRODUCTION_METHODS */
  /* TICKER */
}
final class Session {
  AttachmentIssue attachmentIssue;
  final Reading reading=new Reading();
  Object pending,entries;boolean networkReady,submitting,navigating;String conversation="",status="";Browser web;
}
// Browser observation and native panel rendering are explicit boundaries; the
// production frame dispatch and forward-availability methods execute verbatim.
final class Browser {boolean back,forward;final DisplayContext displayContext;Browser(MainActivity owner){displayContext=new DisplayContext(owner);}boolean canGoBack(){return back;}boolean canGoForward(){return forward;}}
final class DisplayContext {final MainActivity owner;DisplayContext(MainActivity owner){this.owner=owner;}MainActivity getBaseContext(){return owner;}}
final class ToolsState {int updates;boolean back,forward,loading;void navigationState(boolean back,boolean forward,boolean loading){updates++;this.back=back;this.forward=forward;this.loading=loading;}}
final class GeckoAddressUi {/* ADDRESS_METHODS */}
final class Reading {int calls;boolean keyboardVisible;void keyboard(boolean value){calls++;keyboardVisible=value;}}
final class AppHub {static final int CHAT=0;int page;}
final class Paint {
  final Object pending,entries;final String conversation,status;final boolean networkReady,submitting;
  Paint(Object pending,Object entries,String conversation,boolean ready,boolean submitting,String status){this.pending=pending;this.entries=entries;this.conversation=conversation;this.networkReady=ready;this.submitting=submitting;this.status=status;}
}
final class Loading {int updates;void update(){updates++;}}
final class Chrome {int updates;void update(){updates++;}}
final class Address {int updates;void refresh(){updates++;}}
final class NetworkMetricsUi {static void update(MainActivity owner){owner.metrics++;if(owner.designChrome!=null)owner.designChrome.update();}}
final class HostHandler {int delayed;void postDelayed(Runnable next,long interval){if(interval!=1000)throw new AssertionError("Unexpected periodic cadence");delayed++;}}
abstract class ContentObserver {ContentObserver(HostHandler handler){}public abstract void onChange(boolean self);}
final class ChatDownloadProgressUi {
  final MainActivity a;final ContentObserver observer;int updates;
  ChatDownloadProgressUi(MainActivity a){this.a=a;/* DOWNLOAD_OBSERVER */}
  void update(){updates++;}
}
final class Frames implements UiFrameScheduler.Frames {
  final ArrayDeque<Runnable> queue=new ArrayDeque<>();int posts,cancels;
  public void post(Runnable frame){posts++;queue.addLast(frame);}
  public void cancel(Runnable frame){cancels++;queue.remove(frame);}
  Runnable peek(){if(queue.size()!=1)throw new AssertionError("Expected exactly one pending frame");return queue.getFirst();}
  void runOne(){if(!queue.isEmpty())queue.removeFirst().run();}
}
