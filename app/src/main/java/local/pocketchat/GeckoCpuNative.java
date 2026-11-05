package local.pocketchat;

import java.util.*;
import java.util.function.*;
import org.mozilla.geckoview.*;

/** Public, pinned Gecko embedding API. No page scripts or extension privileges. */
final class GeckoCpuNative implements GeckoCpuController.NativeAccess {
  private static final String RFP="privacy.resistFingerprinting";
  final BooleanSupplier current;
  GeckoCpuNative(BooleanSupplier current){this.current=current;}
  public boolean current(){return current.getAsBoolean();}
  public void configure(Integer cap,Consumer<GeckoCpuController.Readback> success,Consumer<Throwable> failure){
    try{
      GeckoPreferenceController.clearGeckoUserPref(GeckoCpuProfile.PREF).accept(ignored->{
        if(!current()){failure.accept(new IllegalStateException("CPU native runtime retired"));return;}
        if(cap==null){read(success,failure);return;}
        GeckoPreferenceController.setGeckoPref(GeckoCpuProfile.PREF,cap,GeckoPreferenceController.PREF_BRANCH_DEFAULT)
          .accept(done->read(success,failure),failure::accept);
      },failure::accept);
    }catch(RuntimeException error){failure.accept(error);}
  }
  public void read(Consumer<GeckoCpuController.Readback> success,Consumer<Throwable> failure){
    try{GeckoPreferenceController.getGeckoPrefs(Arrays.asList(GeckoCpuProfile.PREF,RFP)).accept(values->{
      try{
        if(!current()||values==null||values.size()!=2)throw new IllegalStateException("CPU native runtime retired");
        GeckoPreferenceController.GeckoPreference<?> cpu=null,rfp=null;
        for(GeckoPreferenceController.GeckoPreference<?> value:values){
          if(GeckoCpuProfile.PREF.equals(value.pref)&&cpu==null)cpu=value;
          else if(RFP.equals(value.pref)&&rfp==null)rfp=value;
          else throw new IllegalStateException("CPU native preference binding");
        }
        if(cpu==null||rfp==null||cpu.type!=GeckoPreferenceController.PREF_TYPE_INT||!(cpu.defaultValue instanceof Integer)
            ||cpu.userValue!=null&&!(cpu.userValue instanceof Integer)||rfp.type!=GeckoPreferenceController.PREF_TYPE_BOOL||!(rfp.getValue() instanceof Boolean))throw new IllegalStateException("CPU native preference type");
        int defaultValue=(Integer)cpu.defaultValue,value=(Integer)cpu.getValue();
        if(defaultValue<1||value<1)throw new IllegalStateException("CPU native preference value");
        success.accept(new GeckoCpuController.Readback(value,defaultValue,cpu.getHasUserChangedValue(),(Boolean)rfp.getValue()));
      }catch(RuntimeException rejected){failure.accept(rejected);}
    },failure::accept);}catch(RuntimeException error){failure.accept(error);}
  }
}
