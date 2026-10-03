package local.pocketchat;

/** AndroidX Startup must run in each activity process, not only the launcher process. */
public class EnvironmentLifecycleProvider extends androidx.startup.InitializationProvider {
  public static final class Profile1 extends EnvironmentLifecycleProvider {}
  public static final class Profile2 extends EnvironmentLifecycleProvider {}
  public static final class Profile3 extends EnvironmentLifecycleProvider {}
  public static final class Profile4 extends EnvironmentLifecycleProvider {}
  public static final class Profile5 extends EnvironmentLifecycleProvider {}
  public static final class Profile6 extends EnvironmentLifecycleProvider {}
  public static final class Profile7 extends EnvironmentLifecycleProvider {}
}
