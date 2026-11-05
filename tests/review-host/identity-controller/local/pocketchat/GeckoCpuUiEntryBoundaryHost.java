package local.pocketchat;

import org.json.*;

/** Entry dependency only. Actual CPU desired/UI/native paths run in their own
 * suites; this identity fixture cannot apply or confirm a CPU preference. */
final class GeckoCpuUi {
  static int opened;
  static final String desiredMode="automatic",state="unavailable";
  static final boolean nativeSettingReadback=false,customSupported=false;
  static void show(MainActivity activity){if(activity!=null&&!activity.isDestroyed()&&!activity.isFinishing()&&activity.session!=null&&!activity.session.deleted)opened++;}
  static void requireSupported(String mode,boolean nativeReady){if(!"automatic".equals(mode)||nativeReady)throw new UnsupportedOperationException("Identity UI boundary has no native CPU support");}
}

/** Current production template button and exact existing environment fences. */
public final class GeckoCpuUiEntryBoundaryHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejects(String name,Runnable action){boolean rejected=false;try{action.run();}catch(UnsupportedOperationException expected){rejected=true;}check(name,rejected);}
  public static void main(String[] args)throws Exception{
    ChatSession original=IdentityControllerHostTest.fixture();MainActivity activity=new MainActivity(original);
    FingerprintTemplateUi.show(activity);IdentityControllerHostTest.settle(original);
    android.widget.Button entry=null;int found=0;
    for(android.view.View child:ReferenceUi.Modal.latest.body.children)if(child instanceof android.widget.Button&&"Gecko CPU 可见数上限".equals(((android.widget.Button)child).text)){entry=(android.widget.Button)child;found++;}
    check("Actual current template exposes exactly one CPU-cap entry",found==1&&entry!=null);
    String before=EnvironmentSpecRepository.value.json().toString();int applied=EnvironmentSpecRepository.appliedWrites,observed=EnvironmentSpecRepository.observedWrites,edited=EnvironmentEditorUi.writes;
    entry.click();check("Actual CPU entry reaches unavailable dependency boundary",GeckoCpuUi.opened==1);
    check("CPU entry facade cannot assert native or custom support",!GeckoCpuUi.nativeSettingReadback&&!GeckoCpuUi.customSupported&&GeckoCpuUi.desiredMode.equals("automatic")&&GeckoCpuUi.state.equals("unavailable"));
    check("CPU entry cannot alter identity configuration, observations or tasks",before.equals(EnvironmentSpecRepository.value.json().toString())&&applied==EnvironmentSpecRepository.appliedWrites&&observed==EnvironmentSpecRepository.observedWrites&&edited==EnvironmentEditorUi.writes&&original.environmentIo.tasks.isEmpty()&&original.handler.tasks.isEmpty());
    activity.destroyed=true;entry.click();check("Actual CPU action rejects destroyed Activity",GeckoCpuUi.opened==1);activity.destroyed=false;
    activity.finishing=true;entry.click();check("Actual CPU action rejects finishing Activity",GeckoCpuUi.opened==1);activity.finishing=false;
    original.deleted=true;entry.click();check("Actual CPU action rejects deleted environment",GeckoCpuUi.opened==1);original.deleted=false;
    activity.session=new ChatSession();entry.click();check("Actual CPU action rejects replacement environment",GeckoCpuUi.opened==1);activity.session=original;
    GeckoCpuUi.requireSupported("automatic",false);check("Only automatic unavailable state is modeled in identity fixture",true);
    rejects("Cap1 cannot claim native support from identity fixture",()->GeckoCpuUi.requireSupported("1",false));
    rejects("Cap2 cannot claim native support from identity fixture",()->GeckoCpuUi.requireSupported("2",false));
    rejects("Automatic cannot fabricate native readiness",()->GeckoCpuUi.requireSupported("automatic",true));
    rejects("Unknown mode cannot fabricate native default",()->GeckoCpuUi.requireSupported(null,false));
    System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"automaticOnly",true,"nativeSettingReadback",false,"customSupported",false,"actualAndroidExecution",false,"actualGeckoExecution",false,"scope","Actual current FingerprintTemplateUi CPU action and environment fences, with automatic/unavailable dependency facade only. No CPU spec/store/controller or native implementation is represented."));
  }
}
