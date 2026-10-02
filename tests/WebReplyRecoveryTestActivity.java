package local.pocketchat;

import org.json.*;

public class WebReplyRecoveryTestActivity extends WebReplyFixtureActivity {
  @Override void begin(){if(getIntent().getBooleanExtra("restore",false)){restore();return;}
    boolean uncertain=getIntent().getBooleanExtra("uncertain",false);
    reset(uncertain?"{submitDelay:60000}":"{delay:60000}",()->compose("进程恢复原请求",()->tap("[data-testid=send-button]",()->waitFor("Recovery request is persisted",()->session.pending!=null&&(uncertain||session.pending.optBoolean("confirmed")),30,()->{
      write("web-recovery-stage.json",J.obj("waiting",true,"uncertain",uncertain,"id",session.pending==null?"":session.pending.optString("id")));
    }))));
  }
  void restore(){JSONObject job=session.pending;check("Original pending record survives process death",job!=null);if(job==null){report("web-recovery-results.json");return;}String id=job.optString("id");boolean confirmed=job.optBoolean("confirmed");String key=confirmed?job.optString("userKey").replaceFirst("^id:",""):"old-same-text";
    js("fixture.reset({});fixture.user("+JSONObject.quote(key)+","+JSONObject.quote(job.optString("prompt"))+");fixture.answer('recovered-answer','恢复后读取到的完整回复')",()->{
      if(confirmed)waitFor("Reloaded original message completes without another send",()->session.pending==null,60,()->{
        check("Recovery completes the original delivery id",id.equals(prefs.getString("lastCompletedId","")));
        check("Recovery produces a completion notification",completionPost()>0);
        noResend("Process recovery has zero website submissions",0,()->report("web-recovery-results.json"));
      });
      else handler.postDelayed(()->{
        check("Unconfirmed restart remains suspended",session.pending!=null&&session.pending.optBoolean("webSuspended")&&!session.pending.optBoolean("confirmed"));
        check("Same text in restored history is never rebound",completionPost()==0);
        noResend("Uncertain recovery has zero website submissions",0,()->report("web-uncertain-recovery-results.json"));
      },5500);
    });
  }
}
