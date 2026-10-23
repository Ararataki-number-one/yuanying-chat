package local.pocketchat;

import android.content.Context;
import android.os.Looper;
import java.io.File;

/** Capture identity on the operation's background thread, before recording any event. */
final class NetworkDiagnosticStore {
  static NetworkDiagnostics forContext(Context context,NetworkDiagnostics.Source source){
    // No directory getters or catalog reads here: both can perform disk I/O.
    return NetworkDiagnostics.unbound(Profiles.slot(context),source);
  }
  static boolean bind(NetworkDiagnostics diagnostics,Context context){
    requireBackground();if(diagnostics.bound())return true;
    try{int slot=Profiles.slot(context);Context profile=Profiles.context(context,slot);
      EnvironmentSpec.Identity identity=ProfileCatalog.get(profile).identity(slot);
      return diagnostics.slot==slot&&diagnostics.bind(new File(profile.getNoBackupFilesDir(),"network-diagnostics"),identity.environmentId,identity.generation);
    }catch(Exception unavailable){return false;}
  }
  static boolean bind(NetworkDiagnostics diagnostics,Context context,String environmentId,long generation){
    requireBackground();try{int slot=Profiles.slot(context);Context profile=Profiles.context(context,slot);
      EnvironmentSpec.Identity identity=ProfileCatalog.get(profile).identity(slot);
      return diagnostics.slot==slot&&identity.environmentId.equals(environmentId)&&identity.generation==generation
        &&diagnostics.bind(new File(profile.getNoBackupFilesDir(),"network-diagnostics"),environmentId,generation);
    }catch(Exception unavailable){return false;}
  }
  static String summary(Context context,String environmentId,long generation){
    requireBackground();int slot=Profiles.slot(context);Context profile=Profiles.context(context,slot);
    try{EnvironmentSpec.Identity identity=ProfileCatalog.get(profile).identity(slot);
      if(!identity.environmentId.equals(environmentId)||identity.generation!=generation)return "环境已变化，诊断不可用";
      String result=NetworkDiagnostics.readSummary(new File(profile.getNoBackupFilesDir(),"network-diagnostics"),slot,environmentId,generation);
      EnvironmentSpec.Identity after=ProfileCatalog.get(profile).identity(slot);
      return identity.equals(after)?result:"环境已变化，诊断不可用";
    }catch(Exception unavailable){return "环境已变化，诊断不可用";}
  }
  static String summary(Context context){
    requireBackground();try{EnvironmentSpec.Identity identity=ProfileCatalog.get(context).identity(Profiles.slot(context));
      return summary(context,identity.environmentId,identity.generation);
    }catch(Exception unavailable){return "环境已变化，诊断不可用";}
  }
  private static void requireBackground(){if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("Resolve diagnostics on a background thread");}
}
