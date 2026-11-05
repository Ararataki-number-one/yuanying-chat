package local.pocketchat;

import org.json.*;

/** UI-entry dependency only. The actual timezone controller/UI/native bridge
 * have dedicated suites; this facade cannot apply any timezone or attest ACKs. */
final class GeckoTimeZoneUi {
  static int opened;
  static final String desiredZone="",state="unavailable";
  static final boolean nativeSettingReadback=false,customSupported=false;
  static void show(MainActivity activity){if(activity!=null&&!activity.isDestroyed()&&!activity.isFinishing()&&activity.session!=null&&!activity.session.deleted)opened++;}
  static void requireSupported(String zone,boolean nativeReady){if(zone==null||!zone.isEmpty()||nativeReady)throw new UnsupportedOperationException("Host boundary supports only default system with no native confirmation");}
}

/** Clicks the production template entry and its actual environment fences.
 * No original identity-controller assertion is substituted or modified. */
public final class GeckoTimeZoneEntryBoundaryHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejects(String name,Runnable action){boolean rejected=false;try{action.run();}catch(UnsupportedOperationException expected){rejected=true;}check(name,rejected);}
  public static void main(String[] args)throws Exception{
    ChatSession original=IdentityControllerHostTest.fixture();MainActivity activity=new MainActivity(original);
    FingerprintTemplateUi.show(activity);IdentityControllerHostTest.settle(original);
    android.widget.Button entry=null;int found=0;
    for(android.view.View child:ReferenceUi.Modal.latest.body.children)if(child instanceof android.widget.Button&&"此环境的独立时区".equals(((android.widget.Button)child).text)){entry=(android.widget.Button)child;found++;}
    check("Actual current template contains one actionable timezone entry",found==1&&entry!=null);
    String before=EnvironmentSpecRepository.value.json().toString();int applied=EnvironmentSpecRepository.appliedWrites,observed=EnvironmentSpecRepository.observedWrites,edited=EnvironmentEditorUi.writes;
    entry.click();check("Actual current template entry opens the explicit unavailable UI boundary",GeckoTimeZoneUi.opened==1);
    check("Unavailable facade never claims native ACK or custom capability",!GeckoTimeZoneUi.nativeSettingReadback&&!GeckoTimeZoneUi.customSupported&&GeckoTimeZoneUi.state.equals("unavailable")&&GeckoTimeZoneUi.desiredZone.isEmpty());
    check("Opening timezone entry cannot save configuration or observations",before.equals(EnvironmentSpecRepository.value.json().toString())&&applied==EnvironmentSpecRepository.appliedWrites&&observed==EnvironmentSpecRepository.observedWrites&&edited==EnvironmentEditorUi.writes&&original.environmentIo.tasks.isEmpty()&&original.handler.tasks.isEmpty());
    activity.destroyed=true;entry.click();check("Actual entry rejects destroyed Activity",GeckoTimeZoneUi.opened==1);activity.destroyed=false;
    activity.finishing=true;entry.click();check("Actual entry rejects finishing Activity",GeckoTimeZoneUi.opened==1);activity.finishing=false;
    original.deleted=true;entry.click();check("Actual entry rejects deleted environment",GeckoTimeZoneUi.opened==1);original.deleted=false;
    activity.session=new ChatSession();entry.click();check("Actual entry rejects replacement environment",GeckoTimeZoneUi.opened==1);activity.session=original;
    GeckoTimeZoneUi.requireSupported("",false);check("Only default system without native readiness is representable in this fixture",true);
    rejects("Custom UTC cannot be modeled as supported by this boundary",()->GeckoTimeZoneUi.requireSupported("UTC",false));
    rejects("Custom IANA cannot be modeled as supported by this boundary",()->GeckoTimeZoneUi.requireSupported("Asia/Tokyo",false));
    rejects("Default system cannot fabricate native readiness",()->GeckoTimeZoneUi.requireSupported("",true));
    rejects("Unknown desired timezone cannot fall back to native-ready default",()->GeckoTimeZoneUi.requireSupported(null,false));
    System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"defaultSystemOnly",true,"nativeSettingReadback",false,"customSupported",false,"actualAndroidExecution",false,"actualGeckoExecution",false,"scope","Actual current FingerprintTemplateUi button and environment-fencing lambda; only dependency facade is default-system/unavailable. LinearLayout adapter records existing fixture children; no timezone UI/controller/native implementation is represented."));
  }
}
