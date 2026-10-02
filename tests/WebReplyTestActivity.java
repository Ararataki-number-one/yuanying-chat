package local.pocketchat;

import org.json.*;
import android.view.KeyEvent;

public class WebReplyTestActivity extends WebReplyFixtureActivity {
  String firstId="",firstKey="",secondId="",stoppedId="";
  long notifiedAt;
  @Override void begin(){
    js("fixture.reset({});fixture.user('historical','相同问题');fixture.answer('old-answer','旧回复')",()->handler.postDelayed(()->{
      check("Loading an old conversation never starts a task",session.pending==null);
      compose("synthetic",()->js("document.querySelector('[data-testid=send-button]').click()",()->handler.postDelayed(()->{
        check("Synthetic website clicks are not treated as user gestures",session.pending==null);first();
      },1000)));
    },1500));
  }
  void first(){reset("{url:'/',delay:650}",()->{
    input.setText("独立的简洁模式草稿");
    compose("相同问题",()->tap("[data-testid=send-button]",()->waitFor("Trusted webpage send binds a new stable message",()->session.pending!=null&&session.pending.optBoolean("confirmed"),20,()->{
      if(session.pending!=null){firstId=session.pending.optString("id");firstKey=session.pending.optString("userKey");check("Website-to-conversation URL transition is persisted",session.pending.optString("confirmedUrl").endsWith("/c/web-test"));check("Observation task is distinguished from a native send","web".equals(session.pending.optString("kind")));}
      check("Native composer draft is not cleared by webpage send",input.getText().toString().equals("独立的简洁模式草稿"));
      showPage(false);showPage(true);
      check("Mode switch preserves the same waiting task",session.pending!=null&&firstId.equals(session.pending.optString("id")));
      waitFor("Webpage response completes and clears pending",()->session.pending==null,50,()->{
        JSONObject record=session.deliveries.get(firstId);check("Completion is stored on the bound delivery",record!=null&&"completed".equals(record.optString("state")));
        notifiedAt=completionPost();check("Completion produces an Android notification",notifiedAt>0);
        noResend("Observer never duplicates the website send",1,()->handler.postDelayed(()->{
          check("Subsequent polling does not notify again",completionPost()==notifiedAt);second();
        },2800));
      });
    })));
  });}
  void second(){compose("相同问题",()->tap("[data-testid=send-button]",()->waitFor("Identical prompt receives a distinct bound identity",()->session.pending!=null&&session.pending.optBoolean("confirmed"),20,()->{
    if(session.pending!=null){secondId=session.pending.optString("id");check("Repeated text does not bind the preceding message",!firstKey.equals(session.pending.optString("userKey")));check("Repeated text has its own delivery id",!firstId.equals(secondId));}
    waitFor("Second response completes independently",()->session.pending==null,50,()->noResend("Two user sends remain exactly two sends",2,this::enterAndStop));
  })));}
  void enterAndStop(){remote.requestFocus();reset("{delay:20000}",()->compose("Enter 提问",()->js("document.querySelector('textarea').focus()",()->{
    session.nativeKey(KeyEvent.KEYCODE_ENTER);
    waitFor("Trusted Enter starts one observation task",()->session.pending!=null&&session.pending.optBoolean("confirmed"),20,()->{
      if(session.pending!=null)stoppedId=session.pending.optString("id");notifiedAt=completionPost();
      tap("[data-testid=stop-button]",()->{
        check("User stop clears the waiting task",session.pending==null);
        JSONObject record=session.deliveries.get(stoppedId);check("User stop has a distinct stopped receipt",record!=null&&"stopped".equals(record.optString("state")));
        handler.postDelayed(()->{check("Stopped partial answer is never a completed notification",completionPost()==notifiedAt);noResend("Enter plus form-submit events do not duplicate sends",1,this::ambiguous);},3500);
      });
    });
  })));}
  void ambiguous(){reset("{ambiguous:true}",()->compose("ambiguous",()->tap("[data-testid=send-button]",()->handler.postDelayed(()->{
    check("Multiple new messages suspend identity binding",session.pending!=null&&!session.pending.optBoolean("confirmed")&&session.pending.optBoolean("webSuspended"));
    check("Ambiguous messages never produce a completion",completionPost()==notifiedAt);missingIdentity();
  },2000))));}
  void missingIdentity(){reset("{noId:true}",()->compose("no stable id",()->tap("[data-testid=send-button]",()->handler.postDelayed(()->{
    check("Position-only message keys cannot be adopted",session.pending!=null&&!session.pending.optBoolean("confirmed")&&session.pending.optBoolean("webSuspended"));virtualized();
  },1200))));}
  void virtualized(){reset("{virtualized:true,delay:650}",()->js("fixture.user('previous','相同问题');fixture.answer('previous-answer','原回复')",()->compose("相同问题",()->tap("[data-testid=send-button]",()->waitFor("Virtualized constant-count transcript binds the new ID",()->session.pending!=null&&session.pending.optBoolean("confirmed")&&!"id:previous".equals(session.pending.optString("userKey")),20,()->waitFor("Virtualized response completes",()->session.pending==null,50,this::attachment))))));}
  void attachment(){reset("{attachment:true,delay:650}",()->tap("[data-testid=send-button]",()->waitFor("Attachment-only webpage send binds the actual message",()->session.pending!=null&&session.pending.optBoolean("confirmed")&&"sample.pdf".equals(session.pending.optString("prompt")),20,()->waitFor("Attachment-only response completes",()->session.pending==null,50,this::error))));}
  void error(){reset("{error:true,delay:500}",()->compose("error case",()->tap("[data-testid=send-button]",()->{
    notifiedAt=completionPost();handler.postDelayed(()->{
      check("Website error prevents completion despite a copy button",session.pending!=null&&"uncertain".equals(session.deliveries.get(session.pending.optString("id")).optString("state")));
      check("Website error never triggers success notification",completionPost()==notifiedAt);wrongConversation();
    },5500);
  })));}
  void wrongConversation(){reset("{delay:1800}",()->compose("wrong conversation",()->tap("[data-testid=send-button]",()->waitFor("Navigation test starts with a confirmed request",()->session.pending!=null&&session.pending.optBoolean("confirmed"),20,()->{
    notifiedAt=completionPost();js("history.pushState({},'','/c/other')",()->handler.postDelayed(()->{
      check("Reply on a different route cannot complete original task",session.pending!=null);
      check("Wrong-route reply does not notify",completionPost()==notifiedAt);
      noResend("Navigation does not resubmit",1,()->{session.abandonWait();report("web-reply-results.json");});
    },5500));
  }))));}
}
