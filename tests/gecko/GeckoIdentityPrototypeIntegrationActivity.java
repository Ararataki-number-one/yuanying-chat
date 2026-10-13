package local.pocketchat;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.*;
import android.util.Log;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Test-only official-SDK observations; never an applied fingerprint-template receipt. */
public final class GeckoIdentityPrototypeIntegrationActivity extends Activity {
  static final String TAG="PocketIdentityPrototype",FILE="gecko-identity-prototype-results.json";
  static final String SDK="org.mozilla.geckoview:geckoview:157.0.20261005135250";
  static final String AAR="15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268";
  final Handler handler=new Handler(Looper.getMainLooper());
  final ExecutorService storage=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray(),cases=new JSONArray(),routes=new JSONArray(),navigation=new JSONArray();
  final Map<String,JSONObject> received=new LinkedHashMap<>(),nativeAgents=new LinkedHashMap<>();
  final Map<String,JSONObject> rawObservations=new LinkedHashMap<>();
  final Map<String,GeckoSession> targets=new LinkedHashMap<>();
  JSONObject buildIdentity=new JSONObject();ChatSession owner;FixtureView view;LocalSite site;
  String source,run,origin;int caseIndex=-1,serial;boolean finished,announced;
  String[] requestedLocales;String normalizedLanguage;boolean desktop;
  long requestedAt;Runnable caseDeadline;int navigationDropped;

  static final class PrivateContext extends ContextWrapper {
    final File directory;
    PrivateContext(Context context){super(context);directory=new File(context.getNoBackupFilesDir(),"identity-prototype");}
    @Override public Context getApplicationContext(){return this;}
    @Override public File getNoBackupFilesDir(){if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("Private fixture directory unavailable");return directory;}
  }
  final class FixtureView extends GeckoWebView {
    FixtureView(Context context,ChatSession session){super(context,session);}
    @Override protected boolean allowedUrl(String target){return target!=null&&target.startsWith(origin+"/");}
    @Override JSONObject route(String target){
      JSONObject actual=super.route(target);
      if(routes.length()<64)routes.put(J.obj("url",target,"route",actual,"guardAllowed",owner.guard.allowed(),"at",SystemClock.elapsedRealtime()));
      return actual;
    }
    @Override GeckoSession newSession(){
      GeckoSession sdk=super.newSession();
      GeckoSession.NavigationDelegate original=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){navigation(s,"loadRequest",request.uri,J.obj("directNavigation",request.isDirectNavigation,"redirect",request.isRedirect,"guardAllowed",owner.guard.allowed(),"fixtureAllowed",allowedUrl(request.uri)));return original.onLoadRequest(s,request);}
        @Override public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){navigation(s,"subframeLoadRequest",request.uri,null);return original.onSubframeLoadRequest(s,request);}
        @Override public void onLocationChange(GeckoSession s,String target,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){original.onLocationChange(s,target,permissions,gesture);navigation(s,"locationChange",target,null);}
        @Override public void onCanGoBack(GeckoSession s,boolean value){original.onCanGoBack(s,value);}
        @Override public void onCanGoForward(GeckoSession s,boolean value){original.onCanGoForward(s,value);}
        @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target){return original.onNewSession(s,target);}
        @Override public GeckoResult<String> onLoadError(GeckoSession s,String target,WebRequestError error){navigation(s,"loadError",target,J.obj("code",error.code,"category",error.category,"message",error.getMessage()));return original.onLoadError(s,target,error);}
      });
      GeckoSession.PermissionDelegate permissions=sdk.getPermissionDelegate();
      sdk.setPermissionDelegate(new GeckoSession.PermissionDelegate(){
        @Override public void onAndroidPermissionsRequest(GeckoSession s,String[] requested,Callback callback){navigation(s,"androidPermissions",null,J.obj("permissions",requested==null?JSONObject.NULL:new JSONArray(Arrays.asList(requested))));permissions.onAndroidPermissionsRequest(s,requested,callback);}
        @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){navigation(s,"contentPermission",permission.uri,J.obj("permission",permission.permission,"value",permission.value,"privateMode",permission.privateMode,"thirdPartyOrigin",permission.thirdPartyOrigin));return permissions.onContentPermissionRequest(s,permission);}
        @Override public void onMediaPermissionRequest(GeckoSession s,String target,MediaSource[] video,MediaSource[] audio,MediaCallback callback){navigation(s,"mediaPermission",target,null);permissions.onMediaPermissionRequest(s,target,video,audio,callback);}
      });
      if(!announced){announced=true;handler.post(()->{if(!finished)beginCase();});}
      return sdk;
    }
  }
  void navigation(GeckoSession sdk,String kind,String target,JSONObject detail){
    if(finished)return;
    if(navigation.length()>=64){navigationDropped++;return;}
    String name="unowned";for(Map.Entry<String,GeckoSession> item:targets.entrySet())if(item.getValue()==sdk){name=item.getKey();break;}
    navigation.put(J.obj("kind",kind,"url",target,"session",System.identityHashCode(sdk),"name",name,"case",serial,"at",SystemClock.elapsedRealtime(),"detail",detail));
  }
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException("Integration package only");
    source=getIntent().getStringExtra("sourceCommit");run=getIntent().getStringExtra("runNonce");
    storage.execute(()->{
      try{
        if(source==null||!source.matches("[0-9a-f]{40}")||run==null||!run.matches("[0-9a-f]{32}"))throw new IOException("Exact source and run nonce required");
        JSONObject preparedIdentity=IntegrationBuildIdentity.read(this);
        if(!source.equals(preparedIdentity.optString("sourceCommit"))||preparedIdentity.optBoolean("dirtySource",true)||!SDK.equals(preparedIdentity.optString("sdkCoordinate")))throw new IOException("Installed clean source/official SDK identity mismatch");
        LocalSite preparedSite=new LocalSite();
        handler.post(()->{if(finished){preparedSite.close();return;}buildIdentity=preparedIdentity;site=preparedSite;origin="http://127.0.0.1:"+site.socket.getLocalPort();site.start();openBrowser();});
      }catch(Throwable failure){handler.post(()->finish(failure));}
    });
    handler.postDelayed(()->{if(!finished&&caseIndex<0)finish(new IOException("Official Gecko startup did not become ready"));},60000);
  }
  void openBrowser(){
    if(finished)return;
    try{
      Context context=new PrivateContext(getApplicationContext());
      context.getSharedPreferences("chat",0).edit().putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putInt("privacyLevel",0).putBoolean("backgroundWait",false).commit();
      ProfileCatalog.get(context).created(Profiles.slot(context));
      ChatSession.browserFactory=(c,s)->new FixtureView(c,s);owner=ChatSession.get(context);view=(FixtureView)owner.web;
      owner.handler.removeCallbacks(owner.tick);owner.networkReady=true;owner.offline=false;owner.uiVisible=true;owner.guard.setBlocked(false);
      LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);
      TextView label=new TextView(this);label.setText("Official Gecko identity prototype · controlled local observations only");layout.addView(label);
      view.setHost(this);layout.addView(view,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);
    }catch(Throwable failure){finish(failure);}
  }
  static String normalize(String tag){Locale value=Locale.forLanguageTag(tag);return value.getLanguage()+(value.getCountry().isEmpty()?"":"-"+value.getCountry());}
  void beginCase(){
    if(finished)return;
    try{
      if(caseDeadline!=null)handler.removeCallbacks(caseDeadline);
      caseIndex++;if(caseIndex==4){finish(null);return;}
      final int ticket=++serial;requestedAt=SystemClock.elapsedRealtime();received.clear();nativeAgents.clear();rawObservations.clear();targets.clear();
      requestedLocales=new String[]{caseIndex==0||caseIndex==3?"en-US":caseIndex==1?"ja-JP":"zh-Hant-TW"};
      normalizedLanguage=normalize(requestedLocales[0]);desktop=caseIndex==1;
      check("Case "+caseIndex+" uses the open production Gecko bridge",view.ready&&view.privacyReady&&view.current!=null&&view.current.isOpen());
      view.runtime.getSettings().setLocales(requestedLocales.clone());
      check("Case "+caseIndex+" retains the Java locale request",Arrays.equals(requestedLocales,view.runtime.getSettings().getLocales()));
      view.configure(desktop,0);targets.put("primary",view.current);
      if(caseIndex==3){GeckoSession second=view.newSession();second.open(view.runtime);second.getSettings().setUserAgentMode(GeckoSessionSettings.USER_AGENT_MODE_DESKTOP);targets.put("secondary",second);}
      caseDeadline=()->{if(!finished&&serial==ticket)finish(new IOException("Case "+caseIndex+" did not return complete actual context/header observations"));};handler.postDelayed(caseDeadline,15000);
      for(Map.Entry<String,GeckoSession> item:new ArrayList<>(targets.entrySet())){
        String name=item.getKey();GeckoSession sdk=item.getValue();
        sdk.getUserAgent().accept(ua->{
          if(finished||serial!=ticket||targets.get(name)!=sdk)return;
          nativeAgents.put(name,J.obj("userAgent",ua,"session",System.identityHashCode(sdk),"runtime",System.identityHashCode(view.runtime),"requestedLocales",new JSONArray(Arrays.asList(requestedLocales)),"getterLocales",new JSONArray(Arrays.asList(view.runtime.getSettings().getLocales())),"getterScope","Java requested value; not content acknowledgement","expectedSdkNormalizedLanguage",normalizedLanguage,"userAgentMode",sdk.getSettings().getUserAgentMode(),"viewportMode",sdk.getSettings().getViewportMode()));
          String target=origin+"/page?run="+run+"&case="+ticket+"&session="+name;
          if("primary".equals(name))view.loadUrl(target);else sdk.loadUri(target);
        },failure->{if(!finished&&serial==ticket)finish(new IOException("Official user-agent getter failed",failure));});
      }
    }catch(Throwable failure){finish(failure);}
  }
  void observed(int ticket,String name,JSONObject value){
    if(finished||ticket!=serial||!targets.containsKey(name)||received.containsKey(name))return;
    try{
      if(!run.equals(value.optString("run"))||value.optInt("case")!=ticket||!name.equals(value.optString("session")))throw new IOException("Observation ownership mismatch");
      rawObservations.put(name,value);
      JSONObject nativeValue=nativeAgents.get(name);if(nativeValue==null)throw new IOException("Native session request was not captured");
      JSONArray wire=site.records(ticket,name);JSONObject parent=value.getJSONObject("parent");String ua=nativeValue.getString("userAgent");
      boolean expectedDesktop=desktop||"secondary".equals(name);
      check("Case "+caseIndex+" "+name+" observes the requested official UA mode",expectedDesktop?!ua.contains("Android"):ua.contains("Android"));
      check("Case "+caseIndex+" "+name+" has all main/frame/worker fields",complete(parent)&&complete(value.getJSONObject("frame"))&&complete(value.getJSONObject("worker"))&&complete(value.getJSONObject("blobWorker")));
      for(String context:new String[]{"parent","frame","worker","blobWorker"}){
        JSONObject signal=value.getJSONObject(context);
        check("Case "+caseIndex+" "+name+" "+context+" actual UA matches native session",ua.equals(signal.getString("ua"))&&ua.contains("Firefox/157."));
        check("Case "+caseIndex+" "+name+" "+context+" observes SDK normalized language",normalizedLanguage.equalsIgnoreCase(signal.getString("language")));
        check("Case "+caseIndex+" "+name+" "+context+" agrees on observed language list",parent.getJSONArray("languages").toString().equals(signal.getJSONArray("languages").toString()));
        check("Case "+caseIndex+" "+name+" "+context+" agrees on observed timezone",parent.getString("zone").equals(signal.getString("zone"))&&parent.getInt("offset")==signal.getInt("offset"));
      }
      for(String role:new String[]{"page","frame","worker-script","page-fetch","worker-fetch","blob-worker-fetch"}){
        JSONObject header=null;for(int i=0;i<wire.length();i++){JSONObject row=wire.getJSONObject(i);if(role.equals(row.optString("role"))){if(header!=null)throw new IOException("Duplicate controlled request role "+role);header=row;}}
        check("Case "+caseIndex+" "+name+" "+role+" has real server request headers",header!=null&&ua.equals(header.getString("userAgent"))&&normalizedLanguage.equalsIgnoreCase(header.getString("acceptLanguage").split(",",2)[0].split(";",2)[0].trim()));
      }
      received.put(name,J.obj("name",name,"native",nativeValue,"observed",value,"requestHeaders",wire));
      if(received.size()!=targets.size())return;
      if(caseIndex==3)check("Two sessions share this runtime locale, not separate environment evidence",received.get("primary").getJSONObject("observed").getJSONObject("parent").getString("language").equals(received.get("secondary").getJSONObject("observed").getJSONObject("parent").getString("language")));
      JSONArray sessions=new JSONArray();for(JSONObject observation:received.values())sessions.put(observation);
      cases.put(J.obj("index",caseIndex,"serial",ticket,"requestedAt",requestedAt,"completedAt",SystemClock.elapsedRealtime(),"sessions",sessions,"status","passed"));
      handler.post(this::beginCase);
    }catch(Throwable failure){finish(failure);}
  }
  static boolean complete(JSONObject signal){
    return signal.opt("ua") instanceof String&&!signal.optString("ua").isEmpty()&&signal.opt("language") instanceof String&&!signal.optString("language").isEmpty()&&signal.optJSONArray("languages")!=null&&signal.optJSONArray("languages").length()>0&&signal.opt("cpu") instanceof Number&&signal.optInt("cpu")>0&&signal.opt("offset") instanceof Number&&signal.opt("zone") instanceof String&&!signal.optString("zone").isEmpty()&&signal.opt("intlLocale") instanceof String&&!signal.optString("intlLocale").isEmpty();
  }
  void finish(Throwable failure){
    if(finished)return;finished=true;if(caseDeadline!=null)handler.removeCallbacks(caseDeadline);
    JSONObject report=J.obj("schema",1,"status",failure==null?"passed":"failed","diagnosticOnly",true,"releaseAcceptance",false,"synthetic",true,"actualAndroidExecution",true,"actualGeckoExecution",view!=null&&view.ready,"publicNetworkTraffic",false,"sourceCommit",source,"runNonce",run,"buildIdentity",buildIdentity,"sdkCoordinate",SDK,"sdkAarSha256",AAR,"engineVersion",GeckoWebView.VERSION,"androidSdk",Build.VERSION.SDK_INT,"abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS)),"pid",android.os.Process.myPid(),"origin",origin,"cases",cases,"checks",checks,"passed",passedChecks(),"total",checks.length(),"routes",routes,"nativeRuntimeScope","Locale settings belong to one runtime shared by these sessions","environmentIsolation","Separate Android process/profile isolation is unverified by this prototype","independentTimezone","unsupported; no timezone override requested or applied","deepCustomControls","Independent timezone/Canvas/WebGL/audio/font controls not implemented","uncovered",J.arr("cross-origin frame","Shared Worker","Service Worker","RFP compatibility","real account login","native IME","separate environment isolation","restart persistence"),"scope","Actual controlled page-main/same-origin frame/Dedicated HTTP and Blob Worker readings plus first-party server request headers through the production guarded bridge. No template applied/observed repository acknowledgement.");
    reportPut(report,"nativeNavigation",navigation);reportPut(report,"nativeNavigationDropped",navigationDropped);
    if(view!=null&&view.runtime!=null){GeckoRuntimeSettings settings=view.runtime.getSettings();reportPut(report,"runtimeNetworkRequests",J.obj("lnaEnabled",settings.getLnaEnabled()==null?JSONObject.NULL:settings.getLnaEnabled(),"lnaBlocking",settings.getLnaBlocking()==null?JSONObject.NULL:settings.getLnaBlocking(),"scope","Java requested values; null means no requested override and does not establish native defaults"));}
    android.security.NetworkSecurityPolicy policy=android.security.NetworkSecurityPolicy.getInstance();
    reportPut(report,"androidCleartextPolicy",J.obj("globalPermitted",policy.isCleartextTrafficPermitted(),"loopbackPermitted",policy.isCleartextTrafficPermitted("127.0.0.1"),"localhostPermitted",policy.isCleartextTrafficPermitted("localhost"),"scope","Observed Android policy only; no policy override"));
    if(site!=null){reportPut(report,"allRequestHeaders",site.allRecords());reportPut(report,"localServer",site.diagnostics());}
    if(failure!=null){reportPut(report,"error",String.valueOf(failure));reportPut(report,"failureType",failure.getClass().getName());reportPut(report,"currentCase",caseIndex);reportPut(report,"partialObservations",new JSONObject(rawObservations));reportPut(report,"nativeRequests",new JSONObject(nativeAgents));}
    Log.i(TAG,report.toString());
    if(view!=null)view.destroy();if(owner!=null){owner.handler.removeCallbacks(owner.tick);owner.deleted=true;}if(site!=null)site.close();
    storage.execute(()->{try{File file=new File(getFilesDir(),FILE),tmp=new File(getFilesDir(),FILE+".tmp");try(FileOutputStream out=new FileOutputStream(tmp)){out.write(report.toString().getBytes(StandardCharsets.UTF_8));out.getFD().sync();}if(!tmp.renameTo(file))throw new IOException("Atomic report publication failed");}catch(Throwable error){Log.e(TAG,"Report export failed",error);}finally{storage.shutdown();}});
  }
  int passedChecks(){int count=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))count++;return count;}
  static void reportPut(JSONObject object,String key,Object value){try{object.put(key,value);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  @Override protected void onDestroy(){if(!finished)finish(new IOException("Prototype Activity destroyed before completion"));super.onDestroy();}

  final class LocalSite {
    final ServerSocket socket=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));
    final ExecutorService clients=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(8));final List<JSONObject> wire=new ArrayList<>();
    final Set<Socket> live=Collections.synchronizedSet(new HashSet<>());volatile boolean closed;
    final List<JSONObject> failures=new ArrayList<>();int accepted,parsed,completed,rejected,failuresDropped;
    LocalSite()throws IOException{}
    void start(){new Thread(()->{while(!closed)try{Socket client=socket.accept();int connection;synchronized(this){connection=++accepted;}synchronized(live){if(closed||live.size()>=12){synchronized(this){rejected++;}client.close();continue;}live.add(client);}try{clients.execute(()->serve(client,connection));}catch(RejectedExecutionException failure){synchronized(this){rejected++;}serverFailure(connection,"dispatch","",failure);live.remove(client);client.close();}}catch(IOException failure){if(!closed){serverFailure(0,"accept","",failure);handler.post(()->finish(new IOException("Local fixture accept failed",failure)));}}},"identity-local-server").start();}
    synchronized JSONArray records(int ticket,String name){JSONArray result=new JSONArray();for(JSONObject row:wire)if(row.optInt("case")==ticket&&name.equals(row.optString("session")))result.put(row);return result;}
    synchronized JSONArray allRecords(){JSONArray result=new JSONArray();for(JSONObject row:wire)result.put(row);return result;}
    synchronized JSONObject diagnostics(){return J.obj("address",socket.getInetAddress().getHostAddress(),"port",socket.getLocalPort(),"bound",socket.isBound(),"closed",closed,"acceptedConnections",accepted,"parsedRequests",parsed,"completedConnections",completed,"rejectedConnections",rejected,"failures",new JSONArray(failures),"failuresDropped",failuresDropped,"scope","Bounded actual listener/protocol state; accepted TCP does not imply a Gecko request or context observation");}
    synchronized void serverFailure(int connection,String stage,String request,Throwable failure){if(failures.size()>=16){failuresDropped++;return;}String message=String.valueOf(failure);failures.add(J.obj("connection",connection,"stage",stage,"request",request.substring(0,Math.min(1024,request.length())),"failureType",failure.getClass().getName(),"error",message.substring(0,Math.min(1024,message.length())),"at",SystemClock.elapsedRealtime()));}
    void serve(Socket client,int connection){
      String stage="requestLine",first="";
      try(Socket ignored=client){
        client.setSoTimeout(5000);InputStream in=client.getInputStream();first=line(in);String[] request=first.split(" ");if(request.length!=3)throw new IOException("Malformed HTTP request");
        URI uri=URI.create(request[1]);Map<String,String> query=query(uri.getRawQuery()),headers=new LinkedHashMap<>();int headerBytes=first.length();
        stage="headers";
        for(String value;(value=line(in)).length()>0;){headerBytes+=value.length();if(headerBytes>16384)throw new IOException("Oversized request headers");int split=value.indexOf(':');if(split<1)throw new IOException("Malformed header");headers.put(value.substring(0,split).toLowerCase(Locale.ROOT),value.substring(split+1).trim());}
        if(headers.containsKey("transfer-encoding"))throw new IOException("Chunked fixture request unsupported");
        stage="body";
        int count=Integer.parseInt(headers.getOrDefault("content-length","0"));if(count<0||count>32768)throw new IOException("Oversized observation");byte[] body=new byte[count];new DataInputStream(in).readFully(body);
        synchronized(this){parsed++;}stage="response";
        if("/favicon.ico".equals(uri.getPath())){respond(client,404,"text/plain","");return;}
        if(!run.equals(query.get("run"))||!query.getOrDefault("case","").matches("[1-4]")||!Arrays.asList("primary","secondary").contains(query.get("session"))){respond(client,403,"text/plain","Unknown fixture case");return;}
        int ticket=Integer.parseInt(query.get("case"));String name=query.get("session"),path=uri.getPath();
        String role="/page".equals(path)?"page":"/frame".equals(path)?"frame":"/worker".equals(path)?"worker-script":"/echo".equals(path)?query.getOrDefault("kind",""):"";
        if(!role.isEmpty())synchronized(this){if(wire.size()>=64)throw new IOException("Too many fixture requests");wire.add(J.obj("sequence",wire.size()+1,"case",ticket,"session",name,"role",role,"method",request[0],"path",request[1],"userAgent",headers.getOrDefault("user-agent",""),"acceptLanguage",headers.getOrDefault("accept-language",""),"at",SystemClock.elapsedRealtime()));}
        String config=J.obj("run",run,"case",ticket,"session",name,"origin",origin,"query",uri.getRawQuery()).toString();
        if("GET".equals(request[0])&&"/page".equals(path))respond(client,200,"text/html",page(config));
        else if("GET".equals(request[0])&&"/frame".equals(path))respond(client,200,"text/html","<!doctype html><script>"+signal()+"parent.postMessage({kind:'identity-frame',value:read()},location.origin)</script>");
        else if("GET".equals(request[0])&&"/worker".equals(path))respond(client,200,"application/javascript",worker(config,"worker-fetch"));
        else if("GET".equals(request[0])&&"/echo".equals(path))respond(client,200,"application/json","{\"ok\":true}");
        else if("POST".equals(request[0])&&"/report".equals(path)){JSONObject value=new JSONObject(new String(body,StandardCharsets.UTF_8));respond(client,200,"application/json","{\"ok\":true}");handler.post(()->observed(ticket,name,value));}
        else respond(client,404,"text/plain","");
      }catch(Throwable failure){if(!closed){serverFailure(connection,stage,first,failure);handler.post(()->finish(failure));}}finally{synchronized(this){completed++;}live.remove(client);}
    }
    void close(){closed=true;try{socket.close();}catch(IOException ignored){}synchronized(live){for(Socket client:live)try{client.close();}catch(IOException ignored){}}clients.shutdownNow();}
  }
  static String line(InputStream input)throws IOException{ByteArrayOutputStream bytes=new ByteArrayOutputStream();for(int value;(value=input.read())!=-1;){if(value=='\n')return bytes.toString(StandardCharsets.ISO_8859_1.name()).replace("\r","");if(bytes.size()>=8192)throw new IOException("Oversized HTTP line");bytes.write(value);}throw new EOFException();}
  static Map<String,String> query(String raw)throws IOException{Map<String,String> result=new LinkedHashMap<>();if(raw!=null)for(String item:raw.split("&")){String[] pair=item.split("=",2);String key=URLDecoder.decode(pair[0],"UTF-8"),value=pair.length==2?URLDecoder.decode(pair[1],"UTF-8"):"";if(result.put(key,value)!=null)throw new IOException("Duplicate fixture query");}return result;}
  static void respond(Socket socket,int status,String type,String value)throws IOException{byte[] body=value.getBytes(StandardCharsets.UTF_8);OutputStream out=socket.getOutputStream();out.write(("HTTP/1.1 "+status+" Fixture\r\nContent-Type: "+type+"; charset=utf-8\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();}
  static String signal(){return "function read(){const r=Intl.DateTimeFormat().resolvedOptions();return {ua:navigator.userAgent,language:navigator.language,languages:Array.from(navigator.languages),cpu:navigator.hardwareConcurrency,memory:navigator.deviceMemory??null,offset:new Date().getTimezoneOffset(),zone:r.timeZone,intlLocale:r.locale,origin:location.origin,at:performance.now()}};";}
  static String worker(String config,String role){return "const c="+config+";"+signal()+"fetch(c.origin+'/echo?'+c.query+'&kind="+role+"',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('worker echo failed');return r.json()}).then(()=>postMessage(read())).catch(e=>postMessage({error:String(e)}));";}
  static String page(String config){
    String blob=worker(config,"blob-worker-fetch");
    return "<!doctype html><meta charset=utf-8><title>Controlled identity prototype</title><h1>Official Gecko observations</h1><script>const c="+config+";"+signal()
      +"const frame=document.createElement('iframe');const fp=new Promise(resolve=>addEventListener('message',e=>{if(e.origin===c.origin&&e.source===frame.contentWindow&&e.data?.kind==='identity-frame')resolve(e.data.value)}));frame.src='/frame?'+c.query;document.body.append(frame);"
      +"function observe(w){return new Promise(resolve=>{w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=e=>{w.terminate();resolve({error:e.message})}})}"
      +"const worker=observe(new Worker('/worker?'+c.query));const blobUrl=URL.createObjectURL(new Blob(["+JSONObject.quote(blob)+"],{type:'application/javascript'}));const blobWorker=observe(new Worker(blobUrl));"
      +"Promise.all([fp,worker,blobWorker]).then(async([frame,worker,blobWorker])=>{URL.revokeObjectURL(blobUrl);const response=await fetch('/echo?'+c.query+'&kind=page-fetch',{cache:'no-store'});if(!response.ok)throw Error('page echo failed');await response.json();return fetch('/report?'+c.query,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run:c.run,case:c.case,session:c.session,parent:read(),frame,worker,blobWorker,provenance:'controlled-page-main-world'})})}).catch(e=>document.body.append(String(e)));</script>";
  }
}
