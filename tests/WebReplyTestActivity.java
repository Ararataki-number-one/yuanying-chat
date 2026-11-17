package local.pocketchat;

/** Replacement for the retired confirmation/completion feature fixture. */
public class WebReplyTestActivity extends WebReplyFixtureActivity {
  @Override void begin(){reset("{delay:650}",()->{
    input.setText("独立的本地草稿");compose("网页发送",()->tap("[data-testid=send-button]",()->handler.postDelayed(()->{
      check("A trusted website send creates no native task",session.pending==null&&!prefs.contains("pending"));
      check("Website activity starts no reply service or completion notice",!ChatService.running&&completionPost()==0);
      check("Website sending preserves the independent native draft",input.getText().toString().equals("独立的本地草稿"));
      noResend("One actual website gesture remains exactly one send",1,this::again);
    },2000)));
  });}
  void again(){compose("网页发送",()->tap("[data-testid=send-button]",()->handler.postDelayed(()->{
    check("Repeated prompt text creates no native binding",session.pending==null&&session.activeDeliveryId.isEmpty());
    check("Send-result status is not rendered",!status.getText().toString().contains("发送结果")&&!status.getText().toString().contains("不会自动重发"));
    noResend("Two user gestures remain exactly two website sends",2,()->report("web-reply-results.json"));
  },2000)));}
}
