package local.pocketchat;

import android.content.Context;
import java.io.IOException;
import java.io.InputStream;
import java.util.Objects;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import org.json.JSONObject;

/** Serial environment-policy I/O. Page ownership and permission to send network
 * traffic remain with BrowserActivity; completing a job never grants either.
 * Submit and close from the UI thread. Accepted writes drain on close, while
 * results queued for the previous Activity are no longer delivered. */
final class ChromiumFingerprintJobs implements AutoCloseable {
  interface Success<T> { void complete(T value); }
  interface Failure { void failed(Exception failure); }
  private interface Work<T> { T run() throws Exception; }

  static final class Loaded {
    final ChromiumFingerprintStore.State state;
    final ChromiumFingerprintSpec spec;
    final String script;
    Loaded(ChromiumFingerprintStore.State state,ChromiumFingerprintSpec spec,String script){
      this.state=state;this.spec=spec;this.script=script;
    }
  }

  static final class Saved {
    final ChromiumFingerprintStore.State state;
    final ChromiumFingerprintSpec spec;
    Saved(ChromiumFingerprintStore.State state){
      this.state=state;spec=ChromiumFingerprintSpec.from(state.spec());
    }
  }

  private final Context context;
  private final ExecutorService worker;
  private final Executor delivery;
  private volatile boolean closed;

  ChromiumFingerprintJobs(Context context,Executor delivery){
    this(context,Executors.newSingleThreadExecutor(r->new Thread(r,"chromium-fingerprint-state")),delivery);
  }

  ChromiumFingerprintJobs(Context context,ExecutorService worker,Executor delivery){
    this.context=Objects.requireNonNull(context.getApplicationContext());
    this.worker=Objects.requireNonNull(worker);
    this.delivery=Objects.requireNonNull(delivery);
  }

  static boolean samePolicy(ChromiumFingerprintStore.State first,ChromiumFingerprintStore.State second){
    return first!=null&&second!=null&&first.identity.equals(second.identity)
        &&first.revision==second.revision&&first.seed.equals(second.seed)
        &&first.spec().toString().equals(second.spec().toString());
  }

  void load(String cachedScript,Success<Loaded> success,Failure failure){
    submit(()->{
      ChromiumFingerprintStore.State state=ChromiumFingerprintStore.load(context);
      ChromiumFingerprintSpec spec=ChromiumFingerprintSpec.from(state.spec());
      String script=cachedScript;
      if(script==null){
        try(InputStream input=context.getAssets().open("chromium-fingerprint.js")){
          script=J.text(input,256*1024);
        }
      }
      return new Loaded(state,spec,script);
    },success,failure);
  }

  void save(ChromiumFingerprintStore.State expected,JSONObject desired,boolean rotateSeed,
      Success<Saved> success,Failure failure){
    String snapshot=desired.toString();
    submit(()->{
      ChromiumFingerprintStore.State state=rotateSeed
          ?ChromiumFingerprintStore.rotate(context,expected.identity,expected.revision)
          :ChromiumFingerprintStore.save(context,expected.identity,expected.revision,new JSONObject(snapshot));
      return new Saved(state);
    },success,failure);
  }

  void validate(ChromiumFingerprintStore.State expected,ChromiumFingerprintStore.Binding binding,
      JSONObject fields,Success<JSONObject> success,Failure failure){
    String snapshot=fields.toString();
    submit(()->{
      ChromiumFingerprintStore.State actual=ChromiumFingerprintStore.load(context);
      if(!samePolicy(actual,expected))throw new IOException("指纹配置已改变，请重新读取后加载网页");
      return binding==null?null:activateAndRecord(expected,binding,snapshot);
    },success,failure);
  }

  void activate(ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,
      JSONObject fields,Success<JSONObject> success,Failure failure){
    String snapshot=fields.toString();
    submit(()->activateAndRecord(state,binding,snapshot),success,failure);
  }

  private JSONObject activateAndRecord(ChromiumFingerprintStore.State state,
      ChromiumFingerprintStore.Binding binding,String fields)throws Exception{
    ChromiumFingerprintStore.activate(context,state.identity,state.revision,binding);
    return ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,new JSONObject(fields));
  }

  void record(ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,
      JSONObject fields,Success<JSONObject> success,Failure failure){
    String snapshot=fields.toString();
    submit(()->ChromiumFingerprintStore.record(context,state.identity,state.revision,binding,new JSONObject(snapshot)),success,failure);
  }

  void retire(ChromiumFingerprintStore.State state,ChromiumFingerprintStore.Binding binding,Failure failure){
    submit(()->{ChromiumFingerprintStore.retire(context,state.identity,binding);return null;},ignored->{},failure);
  }

  private <T> void submit(Work<T> work,Success<T> success,Failure failure){
    if(closed)throw new RejectedExecutionException("Chromium fingerprint jobs are closed");
    try{
      worker.execute(()->{
        final T value;
        try{value=work.run();}
        catch(Exception error){deliver(()->failure.failed(error));return;}
        // Keep delivery outside the I/O catch: a consumer exception must not be
        // misreported as a storage failure or cause a second completion.
        deliver(()->success.complete(value));
      });
    }catch(RejectedExecutionException rejected){
      // Submission is a UI-thread operation. Report rejection synchronously so
      // loading/saving/pending flags cannot remain stuck waiting for no job.
      failure.failed(rejected);
    }
  }

  private void deliver(Runnable result){
    if(!closed)delivery.execute(()->{if(!closed)result.run();});
  }

  @Override public void close(){
    closed=true;
    worker.shutdown();
  }
}
