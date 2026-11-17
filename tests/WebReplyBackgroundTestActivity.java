package local.pocketchat;

/** The old background reply worker is retired; the website remains usable. */
public class WebReplyBackgroundTestActivity extends WebReplyFixtureActivity {
  @Override void begin(){AppSettings.setBackgroundReplyPolicy(this,true);BackgroundReplyPolicy.policyChanged(this,0);
    reset("{delay:650}",()->compose("网页后台测试",()->tap("[data-testid=send-button]",()->{
      check("Legacy background setting cannot reactivate a reply worker",!BackgroundReplyPolicy.enabledCached()&&!ChatService.running&&session.pending==null);
      write("web-background-stage.json",J.obj("waiting",true,"foregroundService",false,"contract","browser-result-removal-v1"));moveTaskToBack(true);
      handler.postDelayed(()->{check("Application stayed in background",!session.uiVisible);check("Background website creates no native reply status or notice",session.pending==null&&!ChatService.running&&completionPost()==0);noResend("Background browser does not repeat a send",1,()->report("web-background-results.json"));},2500);
    })));
  }
}
