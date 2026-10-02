package local.pocketchat;

public class WebReplyBackgroundTestActivity extends WebReplyFixtureActivity {
  boolean serviceStarted;
  @Override void begin(){reset("{delay:10000}",()->compose("网页后台通知测试",()->tap("[data-testid=send-button]",()->waitFor("Webpage gesture starts foreground waiting service",()->session.pending!=null&&session.pending.optBoolean("confirmed")&&ChatService.running,30,()->{
    serviceStarted=ChatService.running;write("web-background-stage.json",J.obj("waiting",true,"foregroundService",serviceStarted));
    moveTaskToBack(true);
    waitFor("Background webpage reply completes",()->session.pending==null,100,()->{
      check("Application stayed in background",!session.uiVisible);
      check("Completion notification exists",completionPost()>0);
      waitFor("Waiting service stops after completion",()->!ChatService.running,15,()->noResend("Background monitoring never resends",1,()->report("web-background-results.json")));
    });
  }))));}
}
