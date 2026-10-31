package local.pocketchat;

/** AndroidX Startup must run in each activity process, not only the launcher process. */
public class EnvironmentLifecycleProvider extends androidx.startup.InitializationProvider {
  @Override public android.os.Bundle call(String method,String arg,android.os.Bundle extras){
    boolean policy="backgroundReplyPolicyChanged".equals(method);
    if(!"appVisibility".equals(method)&&!policy)return super.call(method,arg,extras);
    if(android.os.Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException("仅应用可读取界面状态");
    android.os.Bundle value=AppVisibility.snapshot();
    if(extras==null||extras.getInt("expectedPid",-1)!=android.os.Process.myPid())value.putBoolean("known",false);
    if(policy&&value.getBoolean("known"))BackgroundReplyPolicy.policyChanged(getContext(),extras.getLong("revision",0));
    return value;
  }
  public static final class Profile1 extends EnvironmentLifecycleProvider {}
  public static final class Profile2 extends EnvironmentLifecycleProvider {}
  public static final class Profile3 extends EnvironmentLifecycleProvider {}
  public static final class Profile4 extends EnvironmentLifecycleProvider {}
  public static final class Profile5 extends EnvironmentLifecycleProvider {}
  public static final class Profile6 extends EnvironmentLifecycleProvider {}
  public static final class Profile7 extends EnvironmentLifecycleProvider {}
}
