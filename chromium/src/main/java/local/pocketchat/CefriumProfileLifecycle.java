package local.pocketchat;

import android.content.Context;
import android.os.Looper;
import com.cefrium.Cefrium;
import com.cefrium.CefriumProfile;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/** Active browser callbacks and SDK erasure are kept on the engine's main thread. */
final class CefriumProfileLifecycle {
  private static final Map<EnvironmentSpec.Identity,Set<Runnable>> BROWSERS=new HashMap<>();
  private CefriumProfileLifecycle() {}

  /** Register after initialize and before creating a browser. Invoke the returned action when the Activity closes. */
  static Runnable track(Context context,EnvironmentSpec.Identity identity,Runnable stopExactBrowser)throws IOException {
    if(Looper.myLooper()!=Looper.getMainLooper()||!Cefrium.isInitialized())throw new IOException("Chromium 主进程尚未运行");
    if(!ProfileCatalog.get(context).identity(Profiles.slot(context)).equals(identity))
      throw new IOException("Chromium 环境已改变，请重新打开");
    ChromiumProfileCleanup.registerLive(context,CefriumProfileLifecycle::delete);
    BROWSERS.computeIfAbsent(identity,unused->new LinkedHashSet<>()).add(stopExactBrowser);
    return ()->{Set<Runnable> open=BROWSERS.get(identity);if(open!=null){open.remove(stopExactBrowser);if(open.isEmpty())BROWSERS.remove(identity);}};
  }

  private static boolean delete(Context context,EnvironmentSpec.Identity identity)throws IOException {
    if(!Cefrium.isInitialized())return false;
    Set<Runnable> open=BROWSERS.get(identity);
    if(open!=null)for(Runnable stop:new ArrayList<>(open))stop.run();
    String name=ChromiumEntry.profileName(identity);
    File expected=ChromiumProfileCleanup.profileDirectory(context,identity);
    File actual=CefriumProfile.get(name).getDirectory();
    if(actual==null||Files.isSymbolicLink(expected.toPath())||!expected.equals(actual.getCanonicalFile()))return false;
    if(!CefriumProfile.delete(name))return false;
    return Files.notExists(expected.toPath(),LinkOption.NOFOLLOW_LINKS);
  }
}
