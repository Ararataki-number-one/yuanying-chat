package local.pocketchat;

import java.io.IOException;
import org.json.JSONObject;

/** Prepared config application. Busy tasks defer before side effects; a runtime
 * acknowledgement is separate from saving desired settings. The caller owns
 * actual Gecko/network application and rollback, never this persistence class. */
final class EnvironmentApplyCoordinator {
  final EnvironmentSpecRepository repository;
  EnvironmentApplyCoordinator(EnvironmentSpecRepository repository){this.repository=repository;}
  static final class Prepared {
    final EnvironmentSpec.Identity identity;
    final long revision;
    final EnvironmentSpec.Configuration configuration;
    final boolean deferred;
    Prepared(EnvironmentSpec spec,boolean busy){identity=spec.identity;revision=spec.desiredRevision;configuration=spec.desired();deferred=busy;}
  }
  Prepared prepare(boolean busy)throws Exception{return new Prepared(repository.load(),busy);}
  /** Run immediately before changing runtime settings, and again before accepting
   * an async result. A stale result must never be recorded as current. */
  void requireCurrent(Prepared prepared)throws Exception{
    if(prepared.deferred)throw new IOException("当前任务结束后再应用环境配置");
    EnvironmentSpec current=repository.load();if(!current.identity.equals(prepared.identity))throw new IOException("环境已改变，取消本次应用");EnvironmentSpec.requireRevision(prepared.revision,current.desiredRevision);
  }
  EnvironmentSpec acknowledge(Prepared prepared,String actualEngineVersion)throws Exception{
    requireCurrent(prepared);return repository.markApplied(prepared.identity,prepared.revision,actualEngineVersion);
  }
  EnvironmentSpec observe(Prepared prepared,JSONObject observations)throws Exception{
    return repository.recordObservation(prepared.identity,prepared.revision,observations);
  }
}
