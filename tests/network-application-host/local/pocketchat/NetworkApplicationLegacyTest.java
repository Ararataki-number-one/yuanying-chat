package local.pocketchat;
import org.json.*;
public final class NetworkApplicationLegacyTest {
 public static void main(String[] args)throws Exception{
  NetworkApplicationProviderTest.setup(true);NetworkUiProvider provider=NetworkApplicationProviderTest.provider;
  provider.profile.model=EnvironmentSpec.initial(provider.profile.identity,provider.profile.model.desired());
  NetworkApplicationProviderTest.begin();NetworkApplicationProviderTest.drive();
  boolean falseSuccess=provider.ok&&provider.message.contains("并应用");
  System.out.println(J.obj("status",falseSuccess?"expected-baseline-failure":"baseline-not-reproduced","falseSuccessReproduced",falseSuccess,"expectedNoApplied",!falseSuccess,"callbackOk",provider.ok,"message",provider.message,"modelAppliedRevision",provider.profile.model.appliedRevision,"freshVerificationCalls",NetworkApplicationProviderTest.network.freshCalls,"actualAndroidExecution",false,"actualCoreVerification",false));
  if(!falseSuccess)throw new AssertionError("Original ready-only false positive was not reproduced");
 }
}
