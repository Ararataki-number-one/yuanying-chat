package local.pocketchat;

import android.os.Bundle;

/** Synthetic native presentation only; does not connect a route or apply a template. */
public final class UiDetailsIntegrationActivity extends MainActivity {
  @Override public void onCreate(Bundle state){
    if(!getPackageName().endsWith(".test"))throw new SecurityException();
    ChatSession.get(this).manualAttention=true;
    getIntent().putExtra("openWindowAction","native-smoke");super.onCreate(state);
    handler.post(()->{
      handler.removeCallbacks(ticker);
      if("environment-picker".equals(getIntent().getStringExtra("detailScene")))ProfileUi.show(this);
      if("templates".equals(getIntent().getStringExtra("detailScene")))FingerprintTemplateUi.show(this,(spec,done)->done.accept(""));
      if("zoom".equals(getIntent().getStringExtra("detailScene")))BrowserReadingUi.show(this);
      if("audit".equals(getIntent().getStringExtra("detailScene")))EnvironmentAuditUi.show(this);
    });
  }
  @Override void startNetwork(){}
}
