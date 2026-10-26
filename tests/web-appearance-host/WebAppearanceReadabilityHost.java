package local.pocketchat;

import org.json.*;

/** Production state transitions only; no Android, CSS renderer or phone timing. */
public final class WebAppearanceReadabilityHost {
  static JSONObject observed(WebAppearanceSyncHost.Fixture f,double bg,double fg){
    JSONObject value=f.observed(),sample=WebAppearanceSyncHost.sample("main",true,bg);
    WebAppearanceSyncHost.put(sample,"foregroundLuminance",fg);
    WebAppearanceSyncHost.put(value,"samples",new JSONArray().put(sample));return value;
  }
  static boolean accepted(boolean dark,double bg,double fg){
    WebAppearanceSyncHost.Fixture f=new WebAppearanceSyncHost.Fixture();if(!dark)f.sync.request(f.port,false);
    f.sync.receive(f.port,observed(f,bg,fg));return f.status().equals("confirmed");
  }
  public static void main(String[] args){
    if(args.length>0){System.out.println(WebAppearanceSyncHost.o("darkLowContrastConfirmed",accepted(true,.02,.02),"lightLowContrastConfirmed",accepted(false,.9,.8)));return;}
    WebAppearanceSyncHost.Fixture f=new WebAppearanceSyncHost.Fixture();
    WebAppearanceSyncHost.check("Nearly black text on a dark canvas cannot confirm",f.sync.receive(f.port,observed(f,.02,.02))&&!f.status().equals("confirmed"));
    WebAppearanceSyncHost.check("Native contrast diagnosis does not trust the page verdict",f.state().optString("reason").equals("color-contrast")&&f.state().optString("colorStatus").equals("mismatch"));
    WebAppearanceSyncHost.check("Contrasting text and the requested background confirm",f.sync.receive(f.port,observed(f,.02,.8))&&f.status().equals("confirmed"));
    WebAppearanceSyncHost.check("Foreground drift revokes a previously confirmed request",f.sync.receive(f.port,observed(f,.02,.02))&&f.status().equals("pending")&&f.state().optInt("attempt")==1);
    f=new WebAppearanceSyncHost.Fixture();f.sync.request(f.port,false);
    WebAppearanceSyncHost.check("Low contrast white text on a light canvas cannot confirm",f.sync.receive(f.port,observed(f,.9,.8))&&!f.status().equals("confirmed"));
    WebAppearanceSyncHost.check("Light foreground failure is diagnosed",f.state().optString("reason").equals("color-contrast"));
    WebAppearanceSyncHost.check("The minimum three to one contrast is inclusive",accepted(true,0,.1));
    WebAppearanceSyncHost.check("A value below the contrast boundary is rejected",!accepted(true,0,.099999));
    f=new WebAppearanceSyncHost.Fixture();JSONObject r=observed(f,.02,.8);
    WebAppearanceSyncHost.put(r.optJSONArray("samples").optJSONObject(0),"foregroundLuminance",JSONObject.NULL);
    WebAppearanceSyncHost.check("Unknown text colour remains unconfirmed",f.sync.receive(f.port,r)&&f.state().optString("colorStatus").equals("unavailable"));
    f=new WebAppearanceSyncHost.Fixture();r=observed(f,.02,.02);WebAppearanceSyncHost.put(r,"storage","failed");f.sync.receive(f.port,r);f.clock.advance(10000);
    WebAppearanceSyncHost.check("Unreadable colours cannot become a partial success",f.status().equals("failed")&&!f.state().optString("colorStatus").equals("verified"));
    f=new WebAppearanceSyncHost.Fixture();r=observed(f,.02,.8);WebAppearanceSyncHost.put(r,"compatibilityApplied","true");
    WebAppearanceSyncHost.check("Compatibility metadata must be a real boolean",!f.sync.receive(f.port,r)&&!f.state().optBoolean("compatibilityApplied"));
    WebAppearanceSyncHost.put(r,"compatibilityApplied",true);
    WebAppearanceSyncHost.check("A measured compatibility result can confirm",f.sync.receive(f.port,r)&&f.status().equals("confirmed")&&f.state().optBoolean("compatibilityApplied"));
    JSONObject copied=f.state();WebAppearanceSyncHost.put(copied,"compatibilityApplied",false);
    WebAppearanceSyncHost.check("A UI snapshot cannot mutate compatibility state",f.state().optBoolean("compatibilityApplied"));
    f.sync.request(f.port,false);
    WebAppearanceSyncHost.check("A fresh choice cannot inherit old compatibility confirmation",!f.state().optBoolean("compatibilityApplied")&&f.status().equals("pending"));
    r=observed(f,.02,.02);WebAppearanceSyncHost.put(r,"reason","color-contrast");
    WebAppearanceSyncHost.check("Wrong background direction still outranks claimed contrast reason",f.sync.receive(f.port,r)&&f.state().optString("reason").equals("color-mismatch"));
    f=new WebAppearanceSyncHost.Fixture();r=observed(f,.02,.8);WebAppearanceSyncHost.put(r.optJSONArray("samples").optJSONObject(0),"visible",false);
    WebAppearanceSyncHost.check("Good colours never rescue an unobserved region",f.sync.receive(f.port,r)&&!f.status().equals("confirmed"));
    System.out.println(WebAppearanceSyncHost.o("passed",WebAppearanceSyncHost.checks.length(),"results",WebAppearanceSyncHost.checks,"actualAndroidExecution",false,"actualGeckoExecution",false));
  }
}
