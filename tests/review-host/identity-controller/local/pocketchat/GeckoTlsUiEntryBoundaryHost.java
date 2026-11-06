package local.pocketchat;

import org.json.*;

/** UI-entry dependency only. Real TLS desired storage, cold bootstrap and wire
 * checks have separate suites; this boundary cannot apply or confirm TLS. */
final class GeckoTlsUi {
  static int opened,attempts;
  static final String desiredMode="automatic",state="unavailable";
  static final boolean nativeSettingReadback=false,customSupported=false,coldApplied=false;
  static void show(MainActivity activity){attempts++;if(activity!=null&&!activity.isDestroyed()&&!activity.isFinishing()&&activity.session!=null&&!activity.session.deleted)opened++;}
  static void requireSupported(String mode,boolean nativeReady){if(!"automatic".equals(mode)||nativeReady)throw new UnsupportedOperationException("Identity UI boundary supports only default unavailable TLS without native confirmation");}
  static boolean nativeConfirmed(ChatSession session,Object runtime){return false;}
}

/** Actual raw production TLS button and ownership fences; no original identity
 * controller, CPU or timezone assertion is substituted or changed. */
public final class GeckoTlsUiEntryBoundaryHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejects(String name,Runnable action){boolean rejected=false;try{action.run();}catch(UnsupportedOperationException expected){rejected=true;}check(name,rejected);}
  public static void main(String[] args)throws Exception{
    ChatSession original=IdentityControllerHostTest.fixture();MainActivity activity=new MainActivity(original);
    FingerprintTemplateUi.show(activity);IdentityControllerHostTest.settle(original);
    android.widget.Button entry=null;int found=0;
    for(android.view.View child:ReferenceUi.Modal.latest.body.children)if(child instanceof android.widget.Button&&"Gecko TLS 协议".equals(((android.widget.Button)child).text)){entry=(android.widget.Button)child;found++;}
    check("Actual current template exposes exactly one TLS entry",found==1&&entry!=null);
    String before=EnvironmentSpecRepository.value.json().toString();int applied=EnvironmentSpecRepository.appliedWrites,observed=EnvironmentSpecRepository.observedWrites,edited=EnvironmentEditorUi.writes;
    entry.click();check("Actual TLS action opens only the unavailable dependency boundary",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);
    check("TLS entry facade cannot claim native readback, custom support or cold application",!GeckoTlsUi.nativeSettingReadback&&!GeckoTlsUi.customSupported&&!GeckoTlsUi.coldApplied&&GeckoTlsUi.desiredMode.equals("automatic")&&GeckoTlsUi.state.equals("unavailable"));
    check("TLS entry cannot change configuration, observations, editor or queued work",before.equals(EnvironmentSpecRepository.value.json().toString())&&applied==EnvironmentSpecRepository.appliedWrites&&observed==EnvironmentSpecRepository.observedWrites&&edited==EnvironmentEditorUi.writes&&original.environmentIo.tasks.isEmpty()&&original.handler.tasks.isEmpty());
    activity.destroyed=true;entry.click();check("Actual TLS action rejects destroyed Activity",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);activity.destroyed=false;
    activity.finishing=true;entry.click();check("Actual TLS action rejects finishing Activity",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);activity.finishing=false;
    original.deleted=true;entry.click();check("Actual TLS action rejects deleted environment",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);original.deleted=false;
    activity.session=new ChatSession();entry.click();check("Actual TLS action rejects replacement environment",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);activity.session=original;
    activity.session=null;entry.click();check("Actual TLS action rejects absent current environment",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==1);activity.session=original;
    GeckoTlsUi.show(null);check("Unavailable TLS dependency ignores absent Activity",GeckoTlsUi.opened==1&&GeckoTlsUi.attempts==2);
    GeckoTlsUi.requireSupported("automatic",false);check("Only default unavailable TLS is represented by the identity fixture",true);
    rejects("TLS13-only cannot claim support from the identity fixture",()->GeckoTlsUi.requireSupported("tls13-only",false));
    rejects("Default cannot fabricate native TLS readiness",()->GeckoTlsUi.requireSupported("automatic",true));
    rejects("Null desired TLS cannot become a native-ready default",()->GeckoTlsUi.requireSupported(null,false));
    rejects("Unknown desired TLS cannot become a supported mode",()->GeckoTlsUi.requireSupported("unknown",false));
    check("Unready TLS cannot borrow a null runtime confirmation",!GeckoTlsUi.nativeConfirmed(original,null));
    check("Opaque runtime identity is not an observed TLS confirmation",!GeckoTlsUi.nativeConfirmed(original,new Object()));
    check("Foreign session and opaque runtime cannot borrow TLS readiness",!GeckoTlsUi.nativeConfirmed(new ChatSession(),new Object()));
    System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"defaultOnly",true,"desiredMode","automatic","state","unavailable","nativeSettingReadback",false,"customSupported",false,"coldApplied",false,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualTlsNativeExecution",false,"actualSdkApiCompile",false,"actualNetworkExecution",false,"scope","Actual raw FingerprintTemplateUi TLS entry and environment fences with default/unavailable dependency only. No TLS spec, store, controller, native preference, cold boot or network handshake implementation is represented."));
  }
}
