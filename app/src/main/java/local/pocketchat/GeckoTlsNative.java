package local.pocketchat;

import java.util.*;
import java.util.function.*;
import org.mozilla.geckoview.*;

/** Public pinned native preferences only; the request path never uses JavaScript TLS claims. */
@androidx.annotation.OptIn(markerClass=org.mozilla.geckoview.ExperimentalGeckoViewApi.class)
final class GeckoTlsNative implements GeckoTlsController.NativeAccess {
  static final String RFP="privacy.resistFingerprinting",H2="network.http.http2.enabled",H3="network.http.http3.enable";
  final BooleanSupplier owner;
  GeckoTlsNative(BooleanSupplier owner){this.owner=owner;}
  public boolean current(){return owner.getAsBoolean();}
  private boolean admitted(Consumer<Throwable> failure){if(current())return true;failure.accept(new IllegalStateException("TLS native runtime retired"));return false;}
  public void configure(GeckoTlsSpec desired,Consumer<GeckoTlsController.Readback> success,Consumer<Throwable> failure){
    try{
      if(desired==null){failure.accept(new IllegalArgumentException("TLS desired policy missing"));return;}if(!admitted(failure))return;
      GeckoPreferenceController.clearGeckoUserPref(GeckoTlsProfile.MIN).accept(ignored->{
        if(!admitted(failure))return;
        GeckoPreferenceController.clearGeckoUserPref(GeckoTlsProfile.MAX).accept(cleared->{
          if(!admitted(failure))return;
          if(desired.isDefault()){read(success,failure);return;}
          GeckoPreferenceController.setGeckoPref(GeckoTlsProfile.MAX,Integer.valueOf(4),GeckoPreferenceController.PREF_BRANCH_DEFAULT).accept(max->{
            if(!admitted(failure))return;
            GeckoPreferenceController.setGeckoPref(GeckoTlsProfile.MIN,Integer.valueOf(4),GeckoPreferenceController.PREF_BRANCH_DEFAULT).accept(min->{if(admitted(failure))read(success,failure);},failure::accept);
          },failure::accept);
        },failure::accept);
      },failure::accept);
    }catch(RuntimeException unavailable){failure.accept(unavailable);}
  }
  public void read(Consumer<GeckoTlsController.Readback> success,Consumer<Throwable> failure){
    try{GeckoPreferenceController.getGeckoPrefs(Arrays.asList(GeckoTlsProfile.MIN,GeckoTlsProfile.MAX,RFP,H2,H3)).accept(values->{
      try{
        if(!current()||values==null||values.size()!=5)throw new IllegalStateException("TLS native runtime retired");
        Map<String,GeckoPreferenceController.GeckoPreference<?>> prefs=new HashMap<>();
        for(GeckoPreferenceController.GeckoPreference<?> value:values){if(value==null||!Arrays.asList(GeckoTlsProfile.MIN,GeckoTlsProfile.MAX,RFP,H2,H3).contains(value.pref)||prefs.put(value.pref,value)!=null)throw new IllegalStateException("TLS native preference binding");}
        GeckoPreferenceController.GeckoPreference<?> min=prefs.get(GeckoTlsProfile.MIN),max=prefs.get(GeckoTlsProfile.MAX);
        for(GeckoPreferenceController.GeckoPreference<?> value:Arrays.asList(min,max))if(value==null||value.type!=GeckoPreferenceController.PREF_TYPE_INT||!(value.defaultValue instanceof Integer)||!(value.getValue() instanceof Integer)||value.userValue!=null&&!(value.userValue instanceof Integer))throw new IllegalStateException("TLS native preference type");
        for(String key:Arrays.asList(RFP,H2,H3)){GeckoPreferenceController.GeckoPreference<?> value=prefs.get(key);if(value==null||value.type!=GeckoPreferenceController.PREF_TYPE_BOOL||!(value.getValue() instanceof Boolean))throw new IllegalStateException("TLS protected preference type");}
        success.accept(new GeckoTlsController.Readback((Integer)min.getValue(),(Integer)max.getValue(),(Integer)min.defaultValue,(Integer)max.defaultValue,min.getHasUserChangedValue(),max.getHasUserChangedValue(),(Boolean)prefs.get(RFP).getValue(),(Boolean)prefs.get(H2).getValue(),(Boolean)prefs.get(H3).getValue()));
      }catch(RuntimeException rejected){failure.accept(rejected);}
    },failure::accept);}catch(RuntimeException unavailable){failure.accept(unavailable);}
  }
}
