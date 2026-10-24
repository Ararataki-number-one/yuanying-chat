package local.pocketchat;

import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Real framework binding; only the destination component is a controlled fault. */
@android.annotation.TargetApi(28)
public final class NetworkClientBindingIntegrationActivity extends Activity {
  static final String PACKAGE="local.pocketchat.test",ACTION="networkClientBinding";
  static final String MISSING="local.pocketchat.AbsentNetworkClientBindingFixture";
  final Handler main=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray();
  final List<RedirectContext> contexts=new ArrayList<>();final List<NetworkTransportClient> clients=new ArrayList<>();
  final JSONObject result=J.obj("schema",1,"status","failed","actualAndroidExecution",true,
    "actualFrameworkBinding",true,"actualMessengerIpc",true,"actualProductionClient",true,
    "actualProductionNetworkService",false,"actualMihomoExecution",false,"actualGeckoExecution",false,
    "manualServiceConnectionCallbacks",0,"automaticBindRetryAdded",false,
    "securityExceptionAndroidAcceptance",false,"bindingDiedAndroidAcceptance",false,
    "physicalPhoneAcceptance",false,"realUserProxyAcceptance",false,
    "scope","Complete production Client; real Android bind/unbind and Messenger. Only this fixture's explicit destination is redirected to private test Services. The normal Mihomo service does not return null in this test; no physical-device or user-route cause/speed claim.");
  IntegrationEventStore events;String nonce,source;JSONObject identity;
  @Override public void onCreate(Bundle saved){super.onCreate(saved);
    if(!PACKAGE.equals(getPackageName())||Build.VERSION.SDK_INT<28)throw new SecurityException("Integration package on Android28+ required");
    new Thread(this::exercise,"framework-client-binding-fixture").start();
  }
  <T>T ui(Callable<T> task)throws Exception{
    CompletableFuture<T> done=new CompletableFuture<>();main.post(()->{try{done.complete(task.call());}catch(Throwable error){done.completeExceptionally(error);}});
    return done.get(10,TimeUnit.SECONDS);
  }
  void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new IllegalStateException(name);}
  void exercise(){
    try{
      identity=IntegrationBuildIdentity.read(this);source=getIntent().getStringExtra("sourceCommit");nonce=getIntent().getStringExtra("eventNonce");
      if(source==null||!source.equals(identity.optString("sourceCommit"))||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new SecurityException("Exact build and invocation required");
      events=new IntegrationEventStore(this,0,nonce,ACTION,1,identity);
      result.put("sourceCommit",source).put("buildIdentity",identity).put("runNonce",nonce)
        .put("clientPid",android.os.Process.myPid()).put("clientUid",android.os.Process.myUid())
        .put("clientProcess",Application.getProcessName()).put("androidSdk",Build.VERSION.SDK_INT)
        .put("bindingTimeoutSeconds",10).put("replyTimeoutSeconds",15).put("detachTimeoutSeconds",5);
      check("Fixture runs in its separate integration process",(PACKAGE+":transport_binding_fixture").equals(Application.getProcessName()));
      check("Fixture process owns the installed package UID",android.os.Process.myUid()==getApplicationInfo().uid);
      result.put("environmentIdentity",ProfileCatalog.get(this).identity(0).json());
      nullThenMessenger();missingComponent();
      result.put("status","passed");
    }catch(Throwable error){put(result,"error",error.toString());}
    finally{
      if(!"passed".equals(result.optString("status"))){JSONArray observed=new JSONArray();for(NetworkTransportClient client:clients)try{observed.put(journal(client));}catch(Exception missing){observed.put(J.obj("owner",client.diagnostics.owner,"unavailable",missing.toString()));}put(result,"failureJournals",observed);}
      put(result,"checks",checks);put(result,"checkCount",checks.length());
      try{put(result,"bindings",ui(()->{JSONArray observations=new JSONArray();for(RedirectContext context:contexts)observations.put(context.snapshot());return observations;}));}
      catch(Throwable snapshot){put(result,"bindingSnapshotError",snapshot.toString());put(result,"status","failed");}
      // Freeze and publish the original result before touching failed-case resources.
      try{if(events==null)throw new IllegalStateException("Fixture build identity was not established");
        events.emit(ACTION,result);CountDownLatch stored=new CountDownLatch(1);IntegrationEventStore.IO.execute(stored::countDown);
        if(!stored.await(5,TimeUnit.SECONDS)||!IntegrationEventStore.file(this,0,nonce,1).isFile())throw new IOException("Original binding event was not published");
      }catch(Throwable originalPublication){Log.e("PocketClientBinding",J.obj("sourceCommit",source,"runNonce",nonce,"buildIdentity",identity,"acceptance",false,"error",originalPublication.toString()).toString());}
      try{ui(()->{for(RedirectContext context:contexts)context.cleanupOwn();
        stopService(new Intent(this,NullService.class));stopService(new Intent(this,MessengerService.class));return null;});}
      catch(Throwable cleanup){Log.e("PocketClientBinding","Private fixture cleanup failed",cleanup);}
      main.post(this::finish);
    }
  }
  NetworkTransportClient client(RedirectContext context){
    NetworkTransportClient client=new NetworkTransportClient(context,value->{});context.client=client;contexts.add(context);clients.add(client);return client;
  }
  JSONObject failedCall(NetworkTransportClient client)throws Exception{
    long began=SystemClock.elapsedRealtime();Throwable failure=null;
    try{client.call("snapshot","");}catch(Exception error){failure=error;}
    long ended=SystemClock.elapsedRealtime();
    return J.obj("began",began,"ended",ended,"elapsedMs",ended-began,
      "failureClass",failure==null?"":failure.getClass().getName(),"failed",failure!=null);
  }
  void nullThenMessenger()throws Exception{
    result.put("phase","actual-null-call");
    RedirectContext context=new RedirectContext(getApplicationContext(),false);NetworkTransportClient client=client(context);
    JSONObject failure=failedCall(client);result.put("nullWaiter",failure);
    check("Actual null binding releases original caller before its ten second deadline",failure.getBoolean("failed")&&"java.io.IOException".equals(failure.getString("failureClass"))&&failure.getLong("elapsedMs")<10000);
    ui(()->null);Attempt first=context.attempts.get(0);
    check("First real bind was accepted for the private null Service",context.attempts.size()==1&&first.accepted&&first.target.equals(NullService.class.getName()));
    check("Null callback releases the captured production gate",first.gate.getCount()==0&&ui(()->!client.bound&&client.service==null&&client.requests.isEmpty()));
    awaitUnbound(first);
    check("Null owner is actually unbound once through Android",first.unbindAttempts==1&&first.unbindSuccesses==1);
    JSONObject nullService=readReceipt(this,nonce,"null");result.put("nullService",nullService);
    result.put("nullServiceRaw",rawReceipt(this,nonce,"null"));
    check("Private Service records a real null onBind in another process",nullService.getBoolean("returnedNull")&&nullService.getInt("servicePid")!=android.os.Process.myPid()&&nullService.getInt("serviceUid")==android.os.Process.myUid());
    JSONObject callback=journal(client);result.put("nullCallbackJournal",callback);
    check("Actual production callback journal contains exactly one owned null binding",eventCount(callback,"IPC_NULL_BINDING")==1&&eventCount(callback,"IPC_CONNECTED")==0);
    result.put("phase","ordinary-messenger-call");JSONObject recovered=client.call("snapshot","");result.put("recoveredState",recovered);
    JSONObject messengerBind=readReceipt(this,nonce,"messenger");
    check("Next ordinary production call receives the real Messenger reply",nonce.equals(recovered.optString("fixtureNonce"))&&"messenger".equals(recovered.optString("fixtureRole"))&&recovered.optInt("serviceUid")==android.os.Process.myUid()&&recovered.optInt("servicePid")==messengerBind.getInt("servicePid")&&recovered.optInt("servicePid")!=android.os.Process.myPid());
    Attempt second=ui(()->context.attempts.get(1));
    check("Next demand binds a distinct owner and gate without automatic retry",ui(()->context.attempts.size()==2&&second.owner!=first.owner&&second.gate!=first.gate&&second.accepted&&client.bound));
    result.put("phase","actual-detach");client.detach();awaitUnbound(second);
    check("Explicit detach unbinds only the Messenger owner once",second.unbindAttempts==1&&second.unbindSuccesses==1&&first.unbindAttempts==1&&ui(()->!client.bound&&client.service==null&&client.requests.isEmpty()));
    JSONObject messenger=awaitMessengerReceipt(2);result.put("messengerService",messenger);
    result.put("messengerServiceRaw",rawReceipt(this,nonce,"messenger"));
    check("Service received original snapshot and detach command envelopes",messenger.getJSONArray("messages").length()==2&&messenger.getJSONArray("messages").getJSONObject(0).getString("action").equals("snapshot")&&messenger.getJSONArray("messages").getJSONObject(1).getString("action").equals("detach"));
    check("Real Messenger command sender UID matches the owned package",messenger.getJSONArray("messages").getJSONObject(0).getInt("sendingUid")==android.os.Process.myUid()&&messenger.getJSONArray("messages").getJSONObject(1).getInt("sendingUid")==android.os.Process.myUid());
    check("Both actual bind attempts have one successful framework unbind",ui(()->context.attempts.size()==2&&context.outstanding()==0&&context.unbindCount()==2));
    result.put("completedCallbackJournal",journal(client));
  }
  void missingComponent()throws Exception{
    result.put("phase","actual-missing-component");
    ComponentName missing=new ComponentName(this,MISSING);boolean absent=false;
    try{getPackageManager().getServiceInfo(missing,0);}catch(PackageManager.NameNotFoundException expected){absent=true;}
    check("Missing-component fault names an absent component in this test package",absent);
    RedirectContext context=new RedirectContext(getApplicationContext(),true);NetworkTransportClient client=client(context);
    JSONObject failure=failedCall(client);result.put("missingWaiter",failure);ui(()->null);Attempt attempt=context.attempts.get(0);awaitUnbound(attempt);
    check("Real missing-component bind returns false and wakes its caller",failure.getBoolean("failed")&&failure.getLong("elapsedMs")<10000&&!attempt.accepted&&attempt.error.isEmpty());
    check("False-return framework dispatcher is released exactly once",attempt.unbindAttempts==1&&attempt.unbindSuccesses==1&&ui(()->context.attempts.size()==1&&context.outstanding()==0&&!client.bound&&client.service==null));
    JSONObject journal=journal(client);result.put("missingCallbackJournal",journal);
    check("Actual missing bind rejection is distinct from a null callback",eventCount(journal,"IPC_BIND_REJECTED")==1&&eventCount(journal,"IPC_NULL_BINDING")==0&&eventCount(journal,"IPC_CONNECTED")==0);
  }
  void awaitUnbound(Attempt attempt)throws Exception{
    long began=SystemClock.elapsedRealtime(),deadline=began+3000;
    while(ui(()->attempt.unbindSuccesses)!=1){if(SystemClock.elapsedRealtime()>=deadline)throw new IOException("Owned framework unbind not observed");Thread.sleep(20);}
  }
  JSONObject journal(NetworkTransportClient client)throws Exception{
    long began=SystemClock.elapsedRealtime();if(!NetworkDiagnostics.flushForTest(3000))throw new IOException("Actual diagnostic journal did not flush");
    EnvironmentSpec.Identity environment=ProfileCatalog.get(client.context).identity(0);
    File directory=new File(Profiles.context(client.context,0).getNoBackupFilesDir(),"network-diagnostics");
    String raw=NetworkDiagnostics.readSummary(directory,0,environment.environmentId,environment.generation);
    JSONArray owned=new JSONArray();for(String line:raw.split("\n")){String[] fields=line.split("\t",-1);if(fields.length==12&&fields[4].equals(client.diagnostics.owner))owned.put(line);}
    return J.obj("diagnosticWaitBegan",began,"diagnosticWaitEnded",SystemClock.elapsedRealtime(),"diagnosticWaitLimitMs",3000,
      "owner",client.diagnostics.owner,"environmentIdentity",environment.json(),"rawSummary",raw,"ownedRows",owned,
      "journalMonotonicClock","System.nanoTime()/1000000; distinct from elapsedRealtime call/wait clocks",
      "source","actual NetworkDiagnostics records emitted only by this production Client callback/command paths; no ServiceConnection method is called by the fixture");
  }
  static int eventCount(JSONObject journal,String event)throws Exception{int count=0;JSONArray rows=journal.getJSONArray("ownedRows");for(int i=0;i<rows.length();i++){String[] fields=rows.getString(i).split("\t",-1);if(fields[8].equals(event))count++;}return count;}
  JSONObject awaitMessengerReceipt(int minimum)throws Exception{
    long deadline=SystemClock.elapsedRealtime()+3000;while(true){JSONObject value=readReceipt(this,nonce,"messenger");if(value.optJSONArray("messages")!=null&&value.getJSONArray("messages").length()>=minimum)return value;if(SystemClock.elapsedRealtime()>=deadline)throw new IOException("Messenger Service receipt missing");Thread.sleep(20);}
  }
  static final class Attempt {
    final int number;final ServiceConnection owner;final CountDownLatch gate;final String target;final long began;
    boolean accepted;long ended;String error="",unbindError="";int unbindAttempts,unbindSuccesses;
    Attempt(int number,ServiceConnection owner,CountDownLatch gate,String target){this.number=number;this.owner=owner;this.gate=gate;this.target=target;began=SystemClock.elapsedRealtime();}
    JSONObject json(){return J.obj("number",number,"connectionIdentity",System.identityHashCode(owner),"connectionClass",owner.getClass().getName(),"gateIdentity",System.identityHashCode(gate),"gateCount",gate.getCount(),"target",target,"began",began,"ended",ended,"accepted",accepted,"error",error,"unbindError",unbindError,"unbindAttempts",unbindAttempts,"unbindSuccesses",unbindSuccesses);}
  }
  final class RedirectContext extends ContextWrapper {
    final boolean missing;final List<Attempt> attempts=new ArrayList<>();NetworkTransportClient client;
    RedirectContext(Context base,boolean missing){super(base);this.missing=missing;}
    @Override public Context getApplicationContext(){return this;}
    @Override public boolean bindService(Intent intent,ServiceConnection owner,int flags){
      if(Looper.myLooper()!=Looper.getMainLooper()||!new ComponentName(this,NetworkTransportService.class).equals(intent.getComponent())||flags!=Context.BIND_AUTO_CREATE)throw new SecurityException("Only this Client's explicit bind may be redirected");
      String target=missing?MISSING:attempts.isEmpty()?NullService.class.getName():MessengerService.class.getName();
      Attempt attempt=new Attempt(attempts.size()+1,owner,client.connected,target);attempts.add(attempt);
      Intent redirected=new Intent(intent).setComponent(new ComponentName(this,target)).setAction(ACTION+"."+nonce+"."+target)
        .putExtra("sourceCommit",source).putExtra("runNonce",nonce);
      try{return attempt.accepted=super.bindService(redirected,owner,flags);}catch(RuntimeException error){attempt.error=error.getClass().getName();throw error;}finally{attempt.ended=SystemClock.elapsedRealtime();}
    }
    @Override public void unbindService(ServiceConnection owner){
      Attempt selected=null;for(Attempt attempt:attempts)if(attempt.owner==owner)selected=attempt;
      if(selected==null)throw new SecurityException("Unowned fixture unbind");selected.unbindAttempts++;
      try{super.unbindService(owner);selected.unbindSuccesses++;}catch(RuntimeException error){selected.unbindError=error.toString();throw error;}
    }
    int outstanding(){int count=0;for(Attempt attempt:attempts)if(attempt.unbindSuccesses!=1)count++;return count;}
    int unbindCount(){int count=0;for(Attempt attempt:attempts)count+=attempt.unbindAttempts;return count;}
    JSONObject snapshot(){JSONArray rows=new JSONArray();for(Attempt attempt:attempts)rows.put(attempt.json());return J.obj("missingComponent",missing,"attempts",rows,"outstanding",outstanding());}
    void cleanupOwn(){for(Attempt attempt:attempts)if(attempt.unbindSuccesses==0)try{super.unbindService(attempt.owner);}catch(Exception ignored){}}
  }
  static File receiptFile(Context context,String nonce,String role)throws Exception{
    if(!nonce.matches("[0-9a-f]{32}")||!Arrays.asList("null","messenger").contains(role))throw new SecurityException("Owned receipt required");
    return new File(context.getFilesDir(),"network-client-binding-"+nonce+"-"+role+".json");
  }
  static JSONObject serviceReceipt(Service service,Intent intent,String role)throws Exception{
    JSONObject build=IntegrationBuildIdentity.read(service);String nonce=intent.getStringExtra("runNonce"),source=intent.getStringExtra("sourceCommit");
    if(!PACKAGE.equals(service.getPackageName())||!build.getString("sourceCommit").equals(source)||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new SecurityException("Owned framework Service invocation required");
    return J.obj("schema",1,"runNonce",nonce,"sourceCommit",source,"buildIdentity",build,"serviceClass",service.getClass().getName(),"servicePid",android.os.Process.myPid(),"serviceUid",android.os.Process.myUid(),"serviceProcess",Application.getProcessName(),"onBindAt",SystemClock.elapsedRealtime(),"onBindMainLooper",Looper.myLooper()==Looper.getMainLooper(),"role",role);
  }
  static void writeReceipt(Context context,String nonce,String role,JSONObject value)throws Exception{
    AtomicFile file=new AtomicFile(receiptFile(context,nonce,role));FileOutputStream stream=null;
    try{stream=file.startWrite();stream.write((value.toString()+"\n").getBytes(StandardCharsets.UTF_8));file.finishWrite(stream);}catch(Exception error){if(stream!=null)file.failWrite(stream);throw error;}
  }
  static JSONObject readReceipt(Context context,String nonce,String role)throws Exception{
    try(InputStream stream=new FileInputStream(receiptFile(context,nonce,role))){return new JSONObject(J.text(stream,65536));}
  }
  static JSONObject rawReceipt(Context context,String nonce,String role)throws Exception{
    byte[] data;try(InputStream stream=new FileInputStream(receiptFile(context,nonce,role))){data=J.read(stream,65536);}
    StringBuilder hash=new StringBuilder();for(byte value:MessageDigest.getInstance("SHA-256").digest(data))hash.append(String.format(Locale.ROOT,"%02x",value&255));
    return J.obj("rawUtf8",new String(data,StandardCharsets.UTF_8),"utf8Bytes",data.length,"sha256",hash.toString());
  }
  static void put(JSONObject value,String key,Object data){try{value.put(key,data);}catch(Exception error){throw new IllegalStateException(error);}}
  public static final class NullService extends Service {
    @Override public IBinder onBind(Intent intent){try{JSONObject receipt=serviceReceipt(this,intent,"null");receipt.put("returnedNull",true);writeReceipt(this,receipt.getString("runNonce"),"null",receipt);return null;}catch(Exception error){throw new IllegalStateException("Private null Service receipt",error);}}
  }
  public static final class MessengerService extends Service {
    JSONObject receipt;String nonce;final JSONArray messages=new JSONArray();
    final Messenger endpoint=new Messenger(new Handler(Looper.getMainLooper()){@Override public void handleMessage(Message request){
      try{
        if(receipt==null||request.what!=NetworkTransportService.COMMAND||request.sendingUid!=android.os.Process.myUid()||request.replyTo==null)throw new SecurityException("Owned production Messenger command required");
        Bundle data=request.getData();String action=data.getString("action","");
        if(data.getInt("slot",-1)!=0||!Arrays.asList("snapshot","detach").contains(action)||!data.getString("configuration","").isEmpty())throw new SecurityException("Only controlled snapshot/detach accepted");
        JSONObject row=J.obj("id",data.getString("id"),"slot",data.getInt("slot"),"action",action,"configuration",data.getString("configuration"),"generation",data.getString("generation"),"stopReason",data.getString("stopReason"),"expectedGeneration",data.getString("expectedGeneration"),"sendingUid",request.sendingUid,"receivedAt",SystemClock.elapsedRealtime());messages.put(row);
        JSONObject state=J.obj("slot",0,"alive",false,"state","fixture","generation","fixture-"+nonce,"servicePid",android.os.Process.myPid(),"serviceUid",android.os.Process.myUid(),"fixtureNonce",nonce,"fixtureRole","messenger");
        Message response=Message.obtain(null,NetworkTransportService.REPLY);Bundle reply=new Bundle();reply.putString("id",data.getString("id"));reply.putString("json",J.obj("ok",true,"state",state).toString());response.setData(reply);request.replyTo.send(response);
        row.put("replySent",true);receipt.put("messages",messages);writeReceipt(MessengerService.this,nonce,"messenger",receipt);
      }catch(Exception error){Log.e("PocketClientBinding","Private Messenger receipt failed",error);}
    }});
    @Override public IBinder onBind(Intent intent){try{receipt=serviceReceipt(this,intent,"messenger");nonce=receipt.getString("runNonce");receipt.put("returnedNull",false).put("messages",messages);writeReceipt(this,nonce,"messenger",receipt);return endpoint.getBinder();}catch(Exception error){throw new IllegalStateException("Private Messenger Service receipt",error);}}
  }
}
