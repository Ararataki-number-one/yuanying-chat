package local.pocketchat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.AbstractExecutorService;
import java.util.concurrent.Executor;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONArray;
import org.json.JSONObject;

/** Whole production jobs/store/spec classes; explicit queues and vault faults. */
public final class ChromiumFingerprintJobsHost {
  static final ArrayList<String> checks=new ArrayList<>();
  static Path root;
  static int sequence;
  static void check(String label,boolean condition){
    if(!condition)throw new AssertionError(label);
    checks.add(label);
  }

  static final class Capture<T> {
    int successes,failures;T value;Exception error;
    void complete(T value){successes++;this.value=value;}
    void failed(Exception error){failures++;this.error=error;}
  }

  static final class Queue implements Executor {
    final ArrayDeque<Runnable> tasks=new ArrayDeque<>();
    public void execute(Runnable task){tasks.add(task);}
    void drain(){while(!tasks.isEmpty())tasks.remove().run();}
  }

  static final class Worker extends AbstractExecutorService {
    final ArrayDeque<Runnable> tasks=new ArrayDeque<>();
    boolean reject,closed;int immediateStops;
    public void execute(Runnable task){
      if(reject||closed)throw new RejectedExecutionException("Injected worker rejection");
      tasks.add(task);
    }
    void drain()throws Exception{
      while(!tasks.isEmpty()){
        Runnable task=tasks.remove();AtomicReference<Throwable> failure=new AtomicReference<>();
        Thread thread=new Thread(()->{try{task.run();}catch(Throwable error){failure.set(error);}},"jobs-host-worker");
        thread.start();thread.join();
        if(failure.get()!=null)throw new AssertionError("Uncaught worker failure",failure.get());
      }
    }
    public void shutdown(){closed=true;}
    public List<Runnable> shutdownNow(){immediateStops++;closed=true;return Collections.emptyList();}
    public boolean isShutdown(){return closed;}
    public boolean isTerminated(){return closed&&tasks.isEmpty();}
    public boolean awaitTermination(long timeout,TimeUnit unit){return isTerminated();}
  }

  static final class Host {
    final TestContext context;final Worker worker=new Worker();final Queue ui=new Queue();
    final ChromiumFingerprintJobs jobs;
    Host()throws Exception{
      context=new TestContext(root.resolve("case-"+sequence++),
          new EnvironmentSpec.Identity(2,4,"00000000-0000-0000-0000-000000000002"));
      jobs=new ChromiumFingerprintJobs(context,worker,ui);
    }
    ChromiumFingerprintStore.State state()throws Exception{return ChromiumFingerprintStore.load(context);}
    void drain()throws Exception{worker.drain();ui.drain();}
    byte[] bytes()throws Exception{return new SecretStore(context).get(ChromiumFingerprintStore.STORE);}
  }

  static ChromiumFingerprintStore.Binding binding(long navigation){
    return new ChromiumFingerprintStore.Binding("host.webview","157.0","jobs-host",1,navigation);
  }
  static JSONObject fields(){return J.obj("nativeSetup",J.obj("state","native-readback","value",J.obj("configured",true)));}
  static JSONObject desired(boolean desktop){return ChromiumFingerprintSpec.from(J.obj("display",desktop?"desktop":"mobile")).json();}

  static void loading()throws Exception{
    Host h=new Host();Capture<ChromiumFingerprintJobs.Loaded> loaded=new Capture<>();
    h.jobs.load(null,loaded::complete,loaded::failed);
    check("Load performs no storage or asset I/O on submission",h.context.vault.puts==0&&h.context.assets.opens==0&&loaded.successes==0);
    h.worker.drain();
    check("Load uses background I/O and waits for UI delivery",h.context.vault.puts==1&&h.context.assets.opens==1&&loaded.successes==0&&h.ui.tasks.size()==1);
    h.ui.drain();
    check("Loaded state and parsed policy match the stored environment",loaded.successes==1&&loaded.failures==0&&loaded.value.state.identity.equals(h.state().identity)&&loaded.value.spec.protectedMode());
    check("Loaded script is read and its stream is closed",loaded.value.script.equals("host-script")&&h.context.assets.closes==1);
    Capture<ChromiumFingerprintJobs.Loaded> cached=new Capture<>();h.context.assets.failRead=true;
    h.jobs.load("cached-script",cached::complete,cached::failed);h.drain();
    check("Reload reuses the submitted cached script",cached.successes==1&&cached.value.script.equals("cached-script")&&h.context.assets.opens==1);

    Host assetFailure=new Host();assetFailure.context.assets.failRead=true;Capture<ChromiumFingerprintJobs.Loaded> missing=new Capture<>();
    assetFailure.jobs.load(null,missing::complete,missing::failed);assetFailure.drain();
    check("Asset read failure is delivered once without a loaded policy",missing.failures==1&&missing.successes==0);

    Host oversized=new Host();char[] many=new char[256*1024+1];Arrays.fill(many,'x');oversized.context.assets.script=new String(many);
    Capture<ChromiumFingerprintJobs.Loaded> bounded=new Capture<>();oversized.jobs.load(null,bounded::complete,bounded::failed);oversized.drain();
    check("Script loading retains its original size bound and closes on failure",bounded.failures==1&&bounded.successes==0&&oversized.context.assets.closes==1);

    Host vaultFailure=new Host();vaultFailure.state();byte[] before=vaultFailure.bytes();vaultFailure.context.vault.failRead=true;
    Capture<ChromiumFingerprintJobs.Loaded> unreadable=new Capture<>();vaultFailure.jobs.load(null,unreadable::complete,unreadable::failed);vaultFailure.drain();vaultFailure.context.vault.failRead=false;
    check("Storage read failure is delivered without replacing saved state",unreadable.failures==1&&unreadable.successes==0&&Arrays.equals(before,vaultFailure.bytes()));
  }

  static void saving()throws Exception{
    Host h=new Host();ChromiumFingerprintStore.State before=h.state();JSONObject spec=desired(true);
    Capture<ChromiumFingerprintJobs.Saved> saved=new Capture<>();h.jobs.save(before,spec,false,saved::complete,saved::failed);spec.put("display","mobile");
    check("Save waits for the worker before changing durable policy",h.state().revision==before.revision&&saved.successes==0);
    h.drain();ChromiumFingerprintStore.State actual=h.state();
    check("Queued save uses submitted specification snapshot",saved.successes==1&&saved.value.spec.desktop()&&ChromiumFingerprintSpec.from(actual.spec()).desktop());
    check("Ordinary save preserves the stable seed and increments revision",actual.seed.equals(before.seed)&&actual.revision==before.revision+1&&saved.failures==0);
    Capture<ChromiumFingerprintJobs.Saved> same=new Capture<>();h.jobs.save(actual,actual.spec(),false,same::complete,same::failed);h.drain();
    check("Unchanged save retains its original revision",same.successes==1&&same.value.state.revision==actual.revision);
    Capture<ChromiumFingerprintJobs.Saved> rotated=new Capture<>();h.jobs.save(actual,actual.spec(),true,rotated::complete,rotated::failed);h.drain();
    check("Explicit rotation changes only the stable seed and revision",rotated.successes==1&&!rotated.value.state.seed.equals(actual.seed)&&rotated.value.state.revision==actual.revision+1&&rotated.value.state.spec().toString().equals(actual.spec().toString()));

    Host conflict=new Host();ChromiumFingerprintStore.State expected=conflict.state();Capture<ChromiumFingerprintJobs.Saved> first=new Capture<>(),second=new Capture<>();
    conflict.jobs.save(expected,desired(true),false,first::complete,first::failed);
    conflict.jobs.save(expected,desired(false),false,second::complete,second::failed);conflict.drain();
    check("Serial saves preserve revision CAS instead of overwriting a newer policy",first.successes==1&&second.failures==1&&second.successes==0&&ChromiumFingerprintSpec.from(conflict.state().spec()).desktop());

    Host failed=new Host();ChromiumFingerprintStore.State old=failed.state();byte[] durable=failed.bytes();failed.context.vault.failPut=true;
    Capture<ChromiumFingerprintJobs.Saved> notSaved=new Capture<>();failed.jobs.save(old,desired(true),false,notSaved::complete,notSaved::failed);failed.drain();
    check("Failed policy publication reports failure and preserves old bytes",notSaved.failures==1&&notSaved.successes==0&&Arrays.equals(durable,failed.bytes()));
  }

  static void bindings()throws Exception{
    Host h=new Host();ChromiumFingerprintStore.State state=h.state();ChromiumFingerprintStore.Binding binding=binding(1);
    Capture<JSONObject> validated=new Capture<>();h.jobs.validate(state,null,fields(),validated::complete,validated::failed);h.drain();
    check("Background surface validation does not create a foreground binding",validated.successes==1&&validated.value==null&&ChromiumFingerprintStore.lastReceipt(h.context,state.identity,state.revision,binding).length()==0);
    JSONObject nativeFields=fields();Capture<JSONObject> active=new Capture<>();h.jobs.activate(state,binding,nativeFields,active::complete,active::failed);
    nativeFields.getJSONObject("nativeSetup").put("state","failed");h.drain();
    check("Activation records a detached snapshot of native fields",active.successes==1&&active.value.getJSONObject("fields").getJSONObject("nativeSetup").getString("state").equals("native-readback"));
    check("Activation and receipt retain exact runtime and page identity",active.value.getString("runtimeEpoch").equals(binding.runtimeEpoch)&&active.value.getLong("navigationGeneration")==binding.navigationGeneration&&!active.value.getBoolean("fingerprintProtectionVerified"));
    Capture<JSONObject> observed=new Capture<>();JSONObject observedFields=J.obj("pageSelfTest",J.obj("state","failed"));
    h.jobs.record(state,binding,observedFields,observed::complete,observed::failed);observedFields.getJSONObject("pageSelfTest").put("state","page-observed");h.drain();
    check("Observation persistence retains the submitted failure snapshot",observed.successes==1&&observed.value.getJSONObject("fields").getJSONObject("pageSelfTest").getString("state").equals("failed"));

    Capture<JSONObject> newest=new Capture<>(),obsolete=new Capture<>();Capture<Void> retire=new Capture<>();ChromiumFingerprintStore.Binding next=binding(2);
    h.jobs.activate(state,next,fields(),newest::complete,newest::failed);
    h.jobs.retire(state,binding,retire::failed);
    h.jobs.record(state,next,fields(),obsolete::complete,obsolete::failed);h.drain();
    check("Retiring an older binding does not clear the newly activated one",newest.successes==1&&obsolete.successes==1&&retire.failures==0);
    Capture<JSONObject> afterRetire=new Capture<>();h.jobs.retire(state,next,retire::failed);
    h.jobs.record(state,next,fields(),afterRetire::complete,afterRetire::failed);h.drain();
    check("Retire and record execute in submitted order",afterRetire.failures==1&&afterRetire.successes==0&&ChromiumFingerprintStore.lastReceipt(h.context,state.identity,state.revision,next).length()==0);

    Host changed=new Host();ChromiumFingerprintStore.State original=changed.state();JSONObject raw=ChromiumFingerprintStoreHost.rawObject(changed.context);
    raw.put("seed",original.seed.equals(String.join("",Collections.nCopies(64,"f")))?String.join("",Collections.nCopies(64,"e")):String.join("",Collections.nCopies(64,"f")));
    ChromiumFingerprintStoreHost.writeRaw(changed.context,raw.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    Capture<JSONObject> stale=new Capture<>();changed.jobs.validate(original,binding(1),fields(),stale::complete,stale::failed);changed.drain();
    check("Validation rejects changed seed with identical revision",stale.failures==1&&stale.successes==0);

    Host unavailable=new Host();ChromiumFingerprintStore.State valid=unavailable.state();Capture<JSONObject> ready=new Capture<>();unavailable.jobs.activate(valid,binding(1),fields(),ready::complete,ready::failed);unavailable.drain();unavailable.context.vault.failPut=true;
    Capture<JSONObject> writeFailure=new Capture<>();unavailable.jobs.record(valid,binding(1),fields(),writeFailure::complete,writeFailure::failed);unavailable.drain();
    check("Receipt write failure is delivered once without a success",writeFailure.failures==1&&writeFailure.successes==0);
  }

  static void rejectionAndClose()throws Exception{
    Host rejected=new Host();ChromiumFingerprintStore.State state=rejected.state();rejected.worker.reject=true;
    Capture<ChromiumFingerprintJobs.Loaded> load=new Capture<>();rejected.jobs.load("cache",load::complete,load::failed);
    check("Rejected load reports one failure immediately",load.failures==1&&load.error instanceof RejectedExecutionException&&load.successes==0);
    Capture<ChromiumFingerprintJobs.Saved> save=new Capture<>();rejected.jobs.save(state,desired(true),false,save::complete,save::failed);
    check("Rejected save reports one failure immediately",save.failures==1&&save.successes==0);
    Capture<JSONObject> validation=new Capture<>(),activation=new Capture<>(),record=new Capture<>();Capture<Void> retirement=new Capture<>();
    rejected.jobs.validate(state,binding(1),fields(),validation::complete,validation::failed);
    rejected.jobs.activate(state,binding(1),fields(),activation::complete,activation::failed);
    rejected.jobs.record(state,binding(1),fields(),record::complete,record::failed);
    rejected.jobs.retire(state,binding(1),retirement::failed);
    check("Rejected binding jobs each report their own failure",validation.failures==1&&activation.failures==1&&record.failures==1&&retirement.failures==1&&rejected.worker.tasks.isEmpty()&&rejected.ui.tasks.isEmpty());

    Host draining=new Host();ChromiumFingerprintStore.State prior=draining.state();Capture<ChromiumFingerprintJobs.Saved> accepted=new Capture<>();
    draining.jobs.save(prior,desired(true),false,accepted::complete,accepted::failed);draining.jobs.close();draining.drain();
    check("Close drains an accepted policy write without UI delivery",ChromiumFingerprintSpec.from(draining.state().spec()).desktop()&&accepted.successes==0&&accepted.failures==0);
    check("Close preserves orderly executor shutdown",draining.worker.closed&&draining.worker.immediateStops==0);
    boolean refused=false;try{draining.jobs.load("cache",ignored->{},ignored->{});}catch(RejectedExecutionException expected){refused=true;}
    check("New work after close is explicitly rejected",refused&&draining.worker.tasks.isEmpty());

    Host queued=new Host();Capture<ChromiumFingerprintJobs.Loaded> completed=new Capture<>();queued.jobs.load(null,completed::complete,completed::failed);queued.worker.drain();queued.jobs.close();queued.ui.drain();
    check("Close suppresses a result already queued for UI",completed.successes==0&&completed.failures==0);

    Host cleanup=new Host();ChromiumFingerprintStore.State policy=cleanup.state();Capture<JSONObject> bound=new Capture<>();
    cleanup.jobs.activate(policy,binding(1),fields(),bound::complete,bound::failed);cleanup.drain();
    cleanup.jobs.retire(policy,binding(1),error->{throw new AssertionError(error);});cleanup.jobs.close();cleanup.drain();
    check("Close drains accepted binding retirement",ChromiumFingerprintStore.lastReceipt(cleanup.context,policy.identity,policy.revision,binding(1)).length()==0);

    Host consumer=new Host();Capture<ChromiumFingerprintJobs.Loaded> callback=new Capture<>();RuntimeException sentinel=new IllegalStateException("Injected UI consumer failure");
    consumer.jobs.load(null,value->{callback.complete(value);throw sentinel;},callback::failed);consumer.worker.drain();
    RuntimeException seen=null;try{consumer.ui.drain();}catch(RuntimeException failure){seen=failure;}
    check("UI consumer exception is not misreported as an I/O failure",seen==sentinel&&callback.successes==1&&callback.failures==0);
  }

  public static void main(String[] args)throws Exception{
    root=Paths.get(args[0]);Files.createDirectories(root);
    loading();saving();bindings();rejectionAndClose();
    System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));
  }
}
