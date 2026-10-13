package local.pocketchat;

import org.json.JSONArray;
import org.json.JSONObject;

public final class DeferredBrowserHostTest {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static ChatSession fixture(){ChatSession session=new ChatSession();session.prefs.values.put("privacyLevel",1);if(!DeferredBrowserSettings.save(session,2,true))throw new AssertionError("Fixture queue failed");session.identityApplicationPending=true;return session;}
  static JSONObject inspect(ChatSession session){return J.obj("url",session.web.url,"busy",false,"draft","user draft unchanged","draftRaw","user draft unchanged");}
  static JSONObject state(){return J.obj("ok",true,"draft","user draft unchanged");}
  static void failedNewQueue(ChatSession session){session.prefs.failCommit=true;if(DeferredBrowserSettings.save(session,0,false))throw new AssertionError("Queue failure control did not run");session.prefs.failCommit=false;session.identity.queueUnavailable=true;session.identityApplicationPending=false;}
  static void retained(ChatSession session,String phase){
    check(phase+" does not reconfigure the current browser",session.applied==0);
    check(phase+" preserves privacy and display",session.privacy.level()==1&&!session.context.desktop&&session.context.displayWrites==0);
    check(phase+" retains the older queue without applying it",DeferredBrowserSettings.pending(session)&&session.prefs.getInt("nextPrivacyLevel",-1)==2);
    check(phase+" releases the capture operation",!session.operation&&!session.configurationCapture);
  }
  public static void main(String[] args)throws Exception{
    ChatSession session=fixture();DeferredBrowserSettings.drain(session);failedNewQueue(session);session.reply("inspect",inspect(session));retained(session,"Failed queue before inspect return");check("Failed queue before inspect schedules no further read",session.actions.isEmpty());
    session=fixture();DeferredBrowserSettings.drain(session);session.reply("inspect",inspect(session));failedNewQueue(session);session.reply("page-state",state());retained(session,"Failed queue before page-state return");check("Failed queue before page-state schedules no draft writer",session.webStore.worker.jobs.isEmpty());
    session=fixture();DeferredBrowserSettings.drain(session);session.reply("inspect",inspect(session));session.reply("page-state",state());failedNewQueue(session);session.webStore.worker.run();session.handler.run();retained(session,"Failed queue during delayed draft persistence");check("Failed queue after persistence schedules no final inspect",session.actions.isEmpty());
    session=fixture();DeferredBrowserSettings.drain(session);session.reply("inspect",inspect(session));session.reply("page-state",state());session.webStore.worker.run();session.handler.run();failedNewQueue(session);session.reply("inspect",inspect(session));retained(session,"Failed queue before final inspection return");
    session=fixture();session.identity.queueUnavailable=true;DeferredBrowserSettings.apply(session);check("Direct apply also rejects an unavailable candidate",session.applied==0&&session.context.displayWrites==0&&DeferredBrowserSettings.pending(session));
    session=fixture();session.deleted=true;DeferredBrowserSettings.apply(session);check("Deleted environment cannot apply an old queue",session.applied==0&&session.context.displayWrites==0);
    session=fixture();DeferredBrowserSettings.cancel(session);DeferredBrowserSettings.apply(session);check("An empty queue cannot trigger reconfiguration",session.applied==0&&session.context.displayWrites==0);
    session=fixture();DeferredBrowserSettings.drain(session);session.reply("inspect",inspect(session));session.reply("page-state",state());session.webStore.worker.run();session.handler.run();session.reply("inspect",inspect(session));check("The normal captured idle flow applies once",session.applied==1&&session.privacy.level()==2&&session.context.desktop&&!DeferredBrowserSettings.pending(session));check("The normal flow clears capture and pending maintenance",!session.operation&&!session.configurationCapture&&!session.identityApplicationPending);
    System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"scope","Production DeferredBrowserSettings with deterministically delayed inspect/page-state/draft writer callbacks and persistence doubles; no Android or real draft storage").toString());
  }
}
