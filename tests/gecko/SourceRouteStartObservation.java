package local.pocketchat;

import android.os.SystemClock;
import org.json.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

/** Test-only observation of the original start monitor and worker. Never changes network state. */
final class SourceRouteStartObservation {
  static long now(){return SystemClock.elapsedRealtimeNanos();}
  static JSONObject copy(JSONObject value){return value==null?new JSONObject():J.parse(value.toString());}
  static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException error){throw new IllegalStateException(error);}}
  static void require(boolean value,String text)throws IOException{if(!value)throw new IOException("Start observation: "+text);}
  static final class Root {
    final String caseId,source,nonce;final NativeNetwork.Callback callback;final int callbackId;
    final JSONArray admissions=new JSONArray(),invocations=new JSONArray(),errors=new JSONArray();
    JSONObject registration;Invocation running;final CompletableFuture<Void> completion=new CompletableFuture<>();
    Root(NativeNetwork.Callback callback,int id,String caseId,String source,String nonce){this.callback=callback;callbackId=id;this.caseId=caseId;this.source=source;this.nonce=nonce;}
  }
  static final class Binding {
    final Root root;final int request;final NativeNetwork.RecoveryCallback callback;
    Binding(Root root,int request,NativeNetwork.RecoveryCallback callback){this.root=root;this.request=request;this.callback=callback;}
  }
  static final class Registration {
    final Root root;final NativeNetwork.Callback callback;final ArrayList<NativeNetwork.Callback> before;final JSONObject record;final Binding binding;
    Registration(Root root,NativeNetwork.Callback callback,ArrayList<NativeNetwork.Callback> before,JSONObject record,Binding binding){this.root=root;this.callback=callback;this.before=before;this.record=record;this.binding=binding;}
  }
  static final class Invocation {
    final Root root;final JSONObject record;
    Invocation(Root root,JSONObject record){this.root=root;this.record=record;}
  }
  static final class Stop {
    final Invocation invocation;final JSONObject identity,owned;
    Stop(Invocation invocation,JSONObject identity,JSONObject owned){this.invocation=invocation;this.identity=identity;this.owned=owned;}
  }
  final IdentityHashMap<Object,Integer> ids=new IdentityHashMap<>();
  final IdentityHashMap<NativeNetwork.Callback,Root> roots=new IdentityHashMap<>();
  final IdentityHashMap<NativeNetwork.RecoveryCallback,Binding> recoveries=new IdentityHashMap<>();
  final IdentityHashMap<JSONObject,Stop> stops=new IdentityHashMap<>();
  final ThreadLocal<Invocation> current=new ThreadLocal<>();
  int nextObject,nextRegistration,nextInvocation;Root latestRoot;
  int id(Object value){Integer found=ids.get(value);if(found==null){found=++nextObject;ids.put(value,found);}return found;}
  JSONArray waiterIds(List<NativeNetwork.Callback> values){JSONArray out=new JSONArray();for(NativeNetwork.Callback value:values)out.put(id(value));return out;}
  void error(Root root,String value){if(root!=null){root.errors.put(value);root.completion.completeExceptionally(new IOException("Start observation: "+value));}}
  Root waitingRoot(NativeNetwork network){for(NativeNetwork.Callback callback:network.startWaiters){Root root=roots.get(callback);if(root!=null)return root;}return null;}
  static long invocationId(Invocation value){return value==null?0:value.record.optLong("invocationId");}
  static long threadId(Invocation value){return value==null?0:value.record.optLong("javaThreadId");}
  private synchronized Root rootObserved(NativeNetwork.Callback callback,String caseId,String source,String nonce){Root value=new Root(callback,id(callback),caseId,source,nonce);if(roots.containsKey(callback))error(value,"root callback reused");roots.put(callback,value);latestRoot=value;return value;}
  private synchronized void recoveryObserved(NativeNetwork.RecoveryCallback callback,int request,Root root){if(root==null)return;if(recoveries.containsKey(callback))error(root,"recovery callback reused");recoveries.put(callback,new Binding(root,request,callback));}
  private synchronized Registration registrationBeforeObserved(NativeNetwork network,NativeNetwork.Callback callback,int mode){
    Root root=waitingRoot(network),declared=roots.get(callback);Binding binding=callback instanceof NativeNetwork.RecoveryAdapter?recoveries.get(((NativeNetwork.RecoveryAdapter)callback).callback):null;
    if(root==null)root=declared!=null?declared:binding==null?null:binding.root;if(root==null)return null;
    ArrayList<NativeNetwork.Callback> before=new ArrayList<>(network.startWaiters);boolean actualRoot=callback==root.callback;
    JSONObject record=J.obj("registrationId",++nextRegistration,"mode",mode,"callbackId",id(callback),"callbackKind",actualRoot?"restart":binding!=null?"recovery":"other","request",binding==null?0:binding.request,"caseId",binding==null?root.caseId:binding.root.caseId,"beganAtNs",now(),"monitorHeldBefore",Thread.holdsLock(network),"startingBefore",network.starting,"restartQueuedBefore",network.restartQueued,"waitersBefore",waiterIds(before),"invocationIdBefore",invocationId(root.running),"workerThreadIdBefore",threadId(root.running),"adapterCallbackMatches",binding!=null&&callback instanceof NativeNetwork.RecoveryAdapter&&((NativeNetwork.RecoveryAdapter)callback).callback==binding.callback);
    Registration result=new Registration(root,callback,before,record,binding);
    if(actualRoot&&root.registration==null)root.registration=record;else{root.admissions.put(record);if(actualRoot)error(root,"root callback registered more than once");}
    if(declared!=null&&declared!=root||binding!=null&&binding.root!=root)error(root,"registration crossed root scopes");return result;
  }
  private synchronized void registrationAfterObserved(NativeNetwork network,Registration registration){
    if(registration==null)return;Root root=registration.root;JSONObject value=registration.record;ArrayList<NativeNetwork.Callback> after=new ArrayList<>(network.startWaiters);
    boolean append=after.size()==registration.before.size()+1&&after.get(after.size()-1)==registration.callback;
    for(int i=0;append&&i<registration.before.size();i++)append=registration.before.get(i)==after.get(i);
    put(value,"endedAtNs",now());put(value,"monitorHeldAfter",Thread.holdsLock(network));put(value,"startingAfter",network.starting);put(value,"restartQueuedAfter",network.restartQueued);put(value,"waitersAfter",waiterIds(after));put(value,"exactAppend",append);put(value,"rootCallbackRetained",registration.before.contains(root.callback)&&after.contains(root.callback));put(value,"invocationIdAfter",invocationId(root.running));put(value,"workerThreadIdAfter",threadId(root.running));
  }
  private void workerBeforeObserved(NativeNetwork network,int mode){synchronized(network){synchronized(this){
    Root root=waitingRoot(network);if(root==null){current.remove();return;}
    if(current.get()!=null||root.running!=null)error(root,"overlapping worker invocation");
    JSONObject row=J.obj("invocationId",++nextInvocation,"rootRegistrationId",root.registration==null?0:root.registration.optInt("registrationId"),"rootCallbackId",root.callbackId,"caseId",root.caseId,"mode",mode,"javaThreadId",Thread.currentThread().getId(),"beganAtNs",now(),"waitersBefore",waiterIds(network.startWaiters),"startingBefore",network.starting,"restartQueuedBefore",network.restartQueued);
    Invocation value=new Invocation(root,row);root.invocations.put(row);root.running=value;current.set(value);
  }}}
  private void workerAfterObserved(NativeNetwork network,int mode){synchronized(network){synchronized(this){
    Invocation value=current.get();if(value==null)return;Root root=value.root;JSONObject row=value.record;
    if(root.running!=value||row.optInt("mode")!=mode||row.optLong("javaThreadId")!=Thread.currentThread().getId())error(root,"worker completion identity changed");
    put(row,"endedAtNs",now());put(row,"waitersAfter",waiterIds(network.startWaiters));put(row,"startingAfter",network.starting);put(row,"restartQueuedAfter",network.restartQueued);root.running=null;current.remove();
    if(root.invocations.length()!=1||network.starting||network.restartQueued||!network.startWaiters.isEmpty())error(root,"worker completion still has another start invocation or pending waiters");
    if(root.errors.length()==0)root.completion.complete(null);
  }}}
  private synchronized void stopBeforeObserved(NativeNetwork network,JSONObject row){
    if(row==null)return;Invocation invocation=current.get();if(invocation==null){put(row,"startInvocation",J.obj("status","unknown-worker"));return;}
    Root root=invocation.root;JSONObject owned=copy(row.optJSONObject("owned"));JSONObject identity=J.obj("invocationId",invocationId(invocation),"rootRegistrationId",invocation.record.optInt("rootRegistrationId"),"rootCallbackId",root.callbackId,"caseId",root.caseId,"javaThreadId",Thread.currentThread().getId(),"beganAtNs",now(),"owned",owned);
    if(!root.caseId.equals(row.optString("caseId")))error(root,"stop crossed root scopes");stops.put(row,new Stop(invocation,identity,owned));put(row,"startInvocation",identity);
  }
  private synchronized void stopAfterObserved(NativeNetwork network,JSONObject row){
    if(row==null)return;Stop stop=stops.get(row);if(stop==null)return;Invocation active=current.get();put(stop.identity,"endedAtNs",now());put(stop.identity,"invocationIdAfter",invocationId(active));put(stop.identity,"javaThreadIdAfter",Thread.currentThread().getId());
    if(active!=stop.invocation||active.root.running!=active)error(stop.invocation.root,"stop crossed worker invocation");
  }
  synchronized void hookError(String hook,Throwable failure){error(latestRoot,hook+":"+failure.getClass().getSimpleName());}
  Root root(NativeNetwork.Callback callback,String caseId,String source,String nonce){try{return rootObserved(callback,caseId,source,nonce);}catch(Throwable failure){hookError("root",failure);return null;}}
  void recovery(NativeNetwork.RecoveryCallback callback,int request,Root root){try{recoveryObserved(callback,request,root);}catch(Throwable failure){hookError("recovery",failure);}}
  Registration registrationBefore(NativeNetwork network,NativeNetwork.Callback callback,int mode){try{return registrationBeforeObserved(network,callback,mode);}catch(Throwable failure){hookError("registrationBefore",failure);return null;}}
  void registrationAfter(NativeNetwork network,Registration registration){try{registrationAfterObserved(network,registration);}catch(Throwable failure){hookError("registrationAfter",failure);}}
  void workerBefore(NativeNetwork network,int mode){try{workerBeforeObserved(network,mode);}catch(Throwable failure){hookError("workerBefore",failure);}}
  void workerAfter(NativeNetwork network,int mode){try{workerAfterObserved(network,mode);}catch(Throwable failure){hookError("workerAfter",failure);}}
  void stopBefore(NativeNetwork network,JSONObject row){try{stopBeforeObserved(network,row);}catch(Throwable failure){hookError("stopBefore",failure);}}
  void stopAfter(NativeNetwork network,JSONObject row){try{stopAfterObserved(network,row);}catch(Throwable failure){hookError("stopAfter",failure);}}
  synchronized CompletableFuture<Void> workerCompletion(Root root){
    if(root==null){CompletableFuture<Void> missing=new CompletableFuture<>();missing.completeExceptionally(new IOException("Start observation: missing root"));return missing;}
    if(root.errors.length()>0&&!root.completion.isDone())root.completion.completeExceptionally(new IOException("Start observation: incomplete worker observation"));
    return root.completion;
  }
  synchronized JSONObject snapshot(Root root){if(root==null)return J.obj("schema",1,"status","missing-root");return J.obj("schema",1,"caseId",root.caseId,"sourceCommit",root.source,"runNonce",root.nonce,"rootCallbackId",root.callbackId,"rootRegistration",copy(root.registration),"admissions",J.parse(J.obj("values",root.admissions).toString()).optJSONArray("values"),"workerInvocations",J.parse(J.obj("values",root.invocations).toString()).optJSONArray("values"),"errors",J.parse(J.obj("values",root.errors).toString()).optJSONArray("values"));}
  synchronized JSONObject joinFor(int request,JSONObject row)throws Exception{
    Stop stop=stops.get(row);require(stop!=null,"stop has no observed worker");Root root=stop.invocation.root;JSONObject original=root.registration,worker=stop.invocation.record,identity=stop.identity;
    require(original!=null,"root observation is incomplete");require(root.invocations.length()==1&&root.invocations.getJSONObject(0)==worker,"root waiters crossed worker invocations");require(root.errors.length()==0,"root observation is incomplete");
    require(original.getInt("mode")==2&&original.getString("callbackKind").equals("restart")&&original.getInt("callbackId")==root.callbackId&&original.getJSONArray("waitersBefore").length()==0&&!original.getBoolean("startingBefore")&&original.getBoolean("startingAfter")&&!original.getBoolean("restartQueuedBefore")&&!original.getBoolean("restartQueuedAfter")&&original.getBoolean("monitorHeldBefore")&&original.getBoolean("monitorHeldAfter")&&original.getBoolean("exactAppend")&&original.getJSONArray("waitersAfter").length()==1&&original.getJSONArray("waitersAfter").getInt(0)==root.callbackId,"root was not an isolated original restart");
    require(worker.getInt("mode")==2&&worker.getInt("rootRegistrationId")==original.getInt("registrationId")&&worker.getLong("endedAtNs")>=identity.getLong("endedAtNs")&&worker.getJSONArray("waitersBefore").length()==1&&worker.getJSONArray("waitersBefore").getInt(0)==root.callbackId&&worker.getJSONArray("waitersAfter").length()==0&&!worker.getBoolean("startingAfter")&&!worker.getBoolean("restartQueuedBefore")&&!worker.getBoolean("restartQueuedAfter"),"worker was queued, replaced, or incomplete");
    require(root.admissions.length()==1,"unexpected additional start admission");JSONObject admission=root.admissions.getJSONObject(0);
    require(admission.getInt("request")==request&&admission.getInt("mode")==1&&admission.getString("callbackKind").equals("recovery")&&admission.getString("caseId").equals(root.caseId)&&admission.getBoolean("adapterCallbackMatches")&&admission.getBoolean("monitorHeldBefore")&&admission.getBoolean("monitorHeldAfter")&&admission.getBoolean("startingBefore")&&admission.getBoolean("startingAfter")&&!admission.getBoolean("restartQueuedBefore")&&!admission.getBoolean("restartQueuedAfter")&&admission.getBoolean("exactAppend")&&admission.getBoolean("rootCallbackRetained"),"recovery was not appended to the same active restart");
    require(admission.getJSONArray("waitersBefore").length()==1&&admission.getJSONArray("waitersBefore").getInt(0)==root.callbackId&&admission.getJSONArray("waitersAfter").length()==2&&admission.getJSONArray("waitersAfter").getInt(0)==root.callbackId&&admission.getJSONArray("waitersAfter").getInt(1)==admission.getInt("callbackId"),"waiter identities changed");
    long invocation=worker.getLong("invocationId"),thread=worker.getLong("javaThreadId");require(invocation>0&&thread>0&&identity.getLong("invocationId")==invocation&&identity.getLong("invocationIdAfter")==invocation&&identity.getLong("javaThreadId")==thread&&identity.getLong("javaThreadIdAfter")==thread&&admission.getLong("invocationIdBefore")==invocation&&admission.getLong("invocationIdAfter")==invocation&&admission.getLong("workerThreadIdBefore")==thread&&admission.getLong("workerThreadIdAfter")==thread,"join or stop crossed actual worker execution");
    require(identity.getString("caseId").equals(root.caseId)&&row.getString("caseId").equals(root.caseId)&&identity.getInt("rootRegistrationId")==original.getInt("registrationId")&&identity.getInt("rootCallbackId")==root.callbackId&&identity.getJSONObject("owned").toString().equals(stop.owned.toString())&&row.getJSONObject("owned").toString().equals(stop.owned.toString()),"stop owner changed");
    require(original.getLong("endedAtNs")<=worker.getLong("beganAtNs")&&worker.getLong("beganAtNs")<=identity.getLong("beganAtNs")&&identity.getLong("beganAtNs")<=identity.getLong("endedAtNs")&&worker.getLong("beganAtNs")<=admission.getLong("beganAtNs")&&admission.getLong("beganAtNs")<=admission.getLong("endedAtNs")&&admission.getLong("endedAtNs")<=worker.getLong("endedAtNs"),"join timing has no single worker");
    return J.obj("schema",1,"caseId",root.caseId,"sourceCommit",root.source,"runNonce",root.nonce,"request",request,"registrationId",admission.getInt("registrationId"),"callbackId",admission.getInt("callbackId"),"rootRegistrationId",original.getInt("registrationId"),"rootCallbackId",root.callbackId,"invocationId",invocation,"javaThreadId",thread,"stopBeganAtNs",row.getLong("beganAtNs"),"stopEndedAtNs",row.getLong("endedAtNs"),"owned",copy(stop.owned),"admission",copy(admission));
  }
}
