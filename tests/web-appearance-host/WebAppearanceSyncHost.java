package local.pocketchat;

import java.util.*;
import org.json.*;

/** Executes the production state machine with a deterministic clock, without Android. */
public final class WebAppearanceSyncHost {
  static final String DOC="document-one-123456789",OTHER="document-two-123456789";
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(o("name",name,"passed",pass));if(!pass)throw new AssertionError(name);}
  static JSONObject o(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);return result;}catch(JSONException e){throw new AssertionError(e);}}
  static JSONObject clone(JSONObject value){try{return new JSONObject(value.toString());}catch(JSONException e){throw new AssertionError(e);}}
  static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException e){throw new AssertionError(e);}}
  static JSONObject sample(String region,boolean visible,double background){return o("region",region,"visible",visible,"background","rgb(20, 20, 20)","foreground",background>=.5?"rgb(20, 20, 20)":"rgb(240, 240, 240)","backgroundLuminance",background,"foregroundLuminance",background>=.5?.02:.8);}
  static final class Port {public boolean equals(Object other){return other instanceof Port;}public int hashCode(){return 1;}}
  static final class Clock implements BrowserBridgeRequests.Timer {
    long now;final Map<Runnable,Long> active=new IdentityHashMap<>();final List<Runnable> scheduled=new ArrayList<>();
    public void schedule(Runnable task,long delay){active.put(task,now+delay);scheduled.add(task);}
    public void cancel(Runnable task){active.remove(task);}
    void advance(long amount){long end=now+amount;int turns=0;while(true){Runnable first=null;long at=Long.MAX_VALUE;for(Map.Entry<Runnable,Long> row:active.entrySet())if(row.getValue()<at){first=row.getKey();at=row.getValue();}if(first==null||at>end)break;if(++turns>100)throw new AssertionError("unbounded timer loop");active.remove(first);now=at;first.run();}now=end;}
  }
  static final class Fixture {
    final Clock clock=new Clock();final List<JSONObject> sent=new ArrayList<>();final List<Object> targets=new ArrayList<>();
    boolean throwing;final WebAppearanceSync sync=new WebAppearanceSync(clock,(port,message)->{targets.add(port);sent.add(WebAppearanceSyncHost.clone(message));if(throwing)throw new IllegalStateException("private exception with credentials must never escape");});
    final Object port=new Port();
    Fixture(){sync.connect(port,DOC,true);}
    JSONObject state(){return sync.snapshot(port);}
    JSONObject receipt(String stage){JSONObject command=sent.get(sent.size()-1);return o("kind","appearanceReceipt","protocol",1,"documentId",command.opt("documentId"),"version",command.opt("version"),"dark",command.opt("dark"),"stage",stage);}
    JSONObject observed(){JSONObject r=receipt("observed");put(r,"attributesApplied",true);put(r,"storage","unchanged");put(r,"colorStatus","verified");put(r,"reason","");put(r,"samples",new JSONArray().put(sample("main",true,.02)).put(sample("composer",true,.03)));return r;}
    String status(){return state().optString("status");}
  }
  static void boundedAndStages(){
    Fixture f=new Fixture();check("Connect immediately sends one document/version bound instruction",f.sent.size()==1&&f.sent.get(0).optString("kind").equals("appearance")&&f.sent.get(0).optInt("protocol")==1&&f.sent.get(0).optString("documentId").equals(DOC)&&f.sent.get(0).optBoolean("dark"));
    check("Fresh snapshot pending and no fabricated receipt",f.status().equals("pending")&&!f.state().optBoolean("received")&&!f.state().optBoolean("applied"));
    f.clock.advance(1499);check("No retry before1500ms",f.sent.size()==1);
    check("Received receipt accepted",f.sync.receive(f.port,f.receipt("received")));
    JSONObject applied=f.receipt("applied");put(applied,"attributesApplied",true);put(applied,"storage","written");check("Applied receipt accepted without a colour claim",f.sync.receive(f.port,applied)&&f.status().equals("pending"));
    f.clock.advance(1);check("Received/applied do not extend first deadline",f.sent.size()==2&&f.state().optInt("attempt")==2);
    f.clock.advance(1500);check("Third attempt has a strictly new version",f.sent.size()==3&&f.sent.get(2).optInt("version")>f.sent.get(1).optInt("version"));
    f.clock.advance(1500);check("No acknowledgement terminates after4500ms and three sends",f.status().equals("failed")&&f.state().optString("reason").equals("receipt-timeout")&&f.clock.active.isEmpty());
    f.clock.advance(100000);check("Exhausted request never sends a fourth attempt",f.sent.size()==3);
    for(int i=0;i<20;i++)f.sync.connect(f.port,DOC,true);check("Duplicate ready cannot restart an exhausted document",f.sent.size()==3);
    f.sync.request(f.port,true);check("Explicit same-theme resync starts a new bounded request",f.sent.size()==4&&f.state().optInt("attempt")==1&&f.status().equals("pending"));
  }
  static void strictBinding(){
    Fixture f=new Fixture();JSONObject original=f.observed();int version=f.state().optInt("version");
    for(Object bad:new Object[]{true,"1",1.5,2147483648L,JSONObject.NULL}){JSONObject r=clone(original);put(r,"version",bad);check("Invalid version type/value ignored: "+String.valueOf(bad),!f.sync.receive(f.port,r)&&f.state().optInt("version")==version&&!f.state().optBoolean("received"));}
    JSONObject r=clone(original);put(r,"protocol",true);check("Boolean protocol cannot equal numeric1",!f.sync.receive(f.port,r));
    r=clone(original);put(r,"dark",1);check("Numeric dark cannot equal boolean true",!f.sync.receive(f.port,r));
    r=clone(original);put(r,"dark",false);check("Opposite desired theme ignored",!f.sync.receive(f.port,r));
    r=clone(original);put(r,"documentId",OTHER);check("Different document ignored",!f.sync.receive(f.port,r));
    check("Equal but nonidentical port cannot acknowledge another port",!f.sync.receive(new Port(),original));
    check("Invalid document token creates no binding",!f.sync.connect(new Object(),"bad",true));
    f.sync.request(f.port,false);check("Old request cannot confirm a changed intent",!f.sync.receive(f.port,original)&&f.status().equals("pending"));
    r=f.observed();put(r,"version",(double)r.optInt("version"));JSONArray light=new JSONArray().put(sample("main",true,.9));put(r,"samples",light);check("Integral bridge Number encodings remain supported",f.sync.receive(f.port,r)&&f.status().equals("confirmed"));
    check("Late received cannot downgrade an observed confirmation",!f.sync.receive(f.port,f.receipt("received"))&&f.status().equals("confirmed"));
  }
  static void coloursAndStorage(){
    Fixture stalePreference=new Fixture();JSONObject stale=stalePreference.observed();put(stale,"storage","failed");put(stale,"reason","storage-preference-mismatch");stalePreference.sync.receive(stalePreference.port,stale);check("A changed persisted preference cannot retain an earlier confirmation",!stalePreference.status().equals("confirmed")&&stalePreference.state().optString("reason").equals("storage-preference-mismatch"));
    Fixture hiddenMain=new Fixture();JSONObject hidden=hiddenMain.observed();put(hidden.optJSONArray("samples").optJSONObject(0),"visible",false);hiddenMain.sync.receive(hiddenMain.port,hidden);check("Visible composer cannot hide an unpainted main region",!hiddenMain.status().equals("confirmed"));
    Fixture f=new Fixture();JSONObject good=f.observed();check("Actual visible chat samples and persisted preference confirm",f.sync.receive(f.port,good)&&f.status().equals("confirmed")&&f.clock.active.isEmpty());
    JSONObject copy=f.state();try{copy.getJSONArray("samples").getJSONObject(0).put("background","rgb(255, 255, 255)");}catch(JSONException e){throw new AssertionError(e);}check("Snapshot consumers cannot mutate saved sample data",!f.state().toString().contains("255, 255, 255"));
    for(String storage:new String[]{"unavailable","failed"}){
      Fixture p=new Fixture();for(int i=1;i<=3;i++){JSONObject r=p.observed();put(r,"storage",storage);check("Storage "+storage+" observed attempt"+i,p.sync.receive(p.port,r));if(i<3)p.clock.advance(1500);}
      check("Dark current colours with unpersisted preference are partial: "+storage,p.status().equals("partial")&&p.state().optBoolean("applied")&&p.state().optString("colorStatus").equals("verified")&&p.clock.active.isEmpty());
    }
    Fixture p=new Fixture();JSONObject wrong=p.observed();put(wrong,"samples",new JSONArray().put(sample("main",true,.02)).put(sample("composer",true,.95)));p.sync.receive(p.port,wrong);check("One white visible composer prevents all-chat confirmation",p.status().equals("pending")&&p.state().optString("colorStatus").equals("mismatch"));
    p=new Fixture();wrong=p.observed();put(wrong,"samples",new JSONArray().put(sample("main",true,.02)).put(sample("composer",false,.95)));check("An unpainted reported chat region leaves full colour confirmation pending",p.sync.receive(p.port,wrong)&&!p.status().equals("confirmed"));
    p=new Fixture();wrong=p.observed();put(wrong,"samples",new JSONArray().put(sample("main",true,.35)));p.sync.receive(p.port,wrong);check("Exact dark threshold is not accepted as dark",!p.status().equals("confirmed"));
    p.sync.request(p.port,false);wrong=p.observed();put(wrong,"samples",new JSONArray().put(sample("main",true,.5)));p.sync.receive(p.port,wrong);check("Exact light threshold is not accepted as light",!p.status().equals("confirmed"));
    wrong=p.observed();put(wrong,"samples",new JSONArray().put(sample("main",true,.500001)));check("Light sample above threshold can confirm",p.sync.receive(p.port,wrong)&&p.status().equals("confirmed"));
    p=new Fixture();wrong=p.observed();put(wrong,"attributesApplied",false);p.sync.receive(p.port,wrong);check("Correct colours do not hide failed DOM attributes",p.status().equals("pending")&&!p.state().optBoolean("applied"));
  }
  static void unknownAndMalformedSamples(){
    Fixture f=new Fixture();JSONObject base=f.observed();
    for(String css:new String[]{"rgb(0,0,0);url(https://private.example/secret)","var(--private)","rgb(0,0,0)\nsecret","private webpage text","#000"}){
      JSONObject r=clone(base);JSONArray a=r.optJSONArray("samples");put(a.optJSONObject(0),"background",css);check("Non-allowlisted CSS is ignored without echo: "+checks.length(),!f.sync.receive(f.port,r)&&!f.state().toString().contains(css));
    }
    JSONObject r=clone(base);put(r,"samples",new JSONArray().put(sample("main",true,.02)).put(sample("main",true,.9)));check("Duplicate region cannot conceal conflicting samples",!f.sync.receive(f.port,r));
    r=clone(base);JSONArray tooMany=new JSONArray();for(int i=0;i<5;i++)tooMany.put(sample("main",true,.01));put(r,"samples",tooMany);check("Oversized sample set rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r.optJSONArray("samples").optJSONObject(0),"visible",1);check("Visibility must be a boolean",!f.sync.receive(f.port,r));
    r=clone(base);put(r.optJSONArray("samples").optJSONObject(0),"backgroundLuminance",true);check("Luminance boolean rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r.optJSONArray("samples").optJSONObject(0),"backgroundLuminance",-.1);check("Out-of-range luminance rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r,"colorStatus","VERIFIED");check("Unknown enum rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r,"reason","https://private.example/token");check("Arbitrary diagnostic text rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r,"samples",new JSONArray());check("Empty claimed verified observation rejected",!f.sync.receive(f.port,r));
    r=clone(base);put(r,"colorStatus","unavailable");put(r,"attributesApplied",false);put(r,"reason","root-unavailable");put(r,"samples",new JSONArray());check("Document-start missing root is a received diagnostic, not fabricated success",f.sync.receive(f.port,r)&&f.state().optString("reason").equals("root-unavailable")&&!f.status().equals("confirmed"));
    r=f.observed();JSONObject unknown=sample("main",true,.02);put(unknown,"background","");put(unknown,"backgroundLuminance",JSONObject.NULL);put(r,"samples",new JSONArray().put(unknown));put(r,"colorStatus","unavailable");check("Unknown transparent-chain measurement remains unknown",f.sync.receive(f.port,r)&&!f.status().equals("confirmed")&&f.state().optJSONArray("samples").optJSONObject(0).isNull("backgroundLuminance"));
    r=f.observed();unknown=sample("main",true,.02);put(unknown,"background","");put(r,"samples",new JSONArray().put(unknown));check("Numeric luminance cannot rescue missing raw colour",f.sync.receive(f.port,r)&&!f.status().equals("confirmed"));
    r=f.observed();JSONObject root=sample("root",false,.02);put(root,"backgroundLuminance",JSONObject.NULL);put(root,"foregroundLuminance",JSONObject.NULL);put(r,"samples",new JSONArray().put(root).put(sample("main",true,.02)));check("Unknown root colours do not reject known visible chat colours",f.sync.receive(f.port,r)&&f.status().equals("confirmed"));
    Fixture rootOnly=new Fixture();r=rootOnly.observed();put(r,"samples",new JSONArray().put(sample("root",true,.02)).put(sample("body",true,.02)));rootOnly.sync.receive(rootOnly.port,r);check("Root/body darkness alone cannot stand in for a chat region",!rootOnly.status().equals("confirmed"));
    r=rootOnly.observed();put(r,"samples",new JSONArray().put(sample("main",false,.02)));rootOnly.sync.receive(rootOnly.port,r);check("Hidden chat sample cannot provide visible coverage",!rootOnly.status().equals("confirmed"));
  }
  static void lifecycleAndDrift(){
    Fixture f=new Fixture();Runnable cancelled=f.clock.scheduled.get(0);JSONObject old=f.observed();f.sync.receive(f.port,old);
    JSONObject drift=f.observed();put(drift,"samples",new JSONArray().put(sample("main",true,.99)));f.sync.receive(f.port,drift);check("Current-document drift revokes the confirmation",f.status().equals("pending")&&f.state().optInt("attempt")==1);
    cancelled.run();check("A previously queued canceled timer cannot consume drift budget",f.sent.size()==1);
    f.clock.advance(1500);check("Drift consumes only next remaining attempt",f.sent.size()==2&&f.state().optInt("attempt")==2);
    check("Old version after drift retry ignored",!f.sync.receive(f.port,old));f.sync.receive(f.port,f.observed());
    drift=f.observed();put(drift,"samples",new JSONArray().put(sample("main",true,.99)));f.sync.receive(f.port,drift);f.clock.advance(1500);check("Second drift reaches the third total attempt",f.sent.size()==3&&f.state().optInt("attempt")==3);
    drift=f.observed();put(drift,"samples",new JSONArray().put(sample("main",true,.99)));f.sync.receive(f.port,drift);f.clock.advance(10000);check("Continued drift never opens an infinite retry budget",f.sent.size()==3&&f.status().equals("failed"));
    f=new Fixture();old=f.observed();cancelled=f.clock.scheduled.get(0);f.sync.connect(f.port,OTHER,true);check("A new document resets budget with a new version",f.sent.size()==2&&f.state().optInt("attempt")==1);
    check("Prior document cannot acknowledge the replacement",!f.sync.receive(f.port,old));cancelled.run();check("Prior document queued timer cannot retry replacement",f.sent.size()==2);
    Object peer=new Port();f.sync.connect(peer,"peer-document-123456789",false);f.sync.disconnect(f.port);check("Disconnect retires only exact port identity",f.sync.snapshot(f.port).optString("status").equals("unavailable")&&f.sync.snapshot(peer).optString("status").equals("pending"));
    int sent=f.sent.size();f.sync.clear();f.clock.advance(100000);check("Clear cancels every remaining port timer",f.sent.size()==sent&&f.clock.active.isEmpty());
    f=new Fixture();f.throwing=true;f.sync.request(f.port,true);f.clock.advance(4500);check("Sender exceptions are bounded and cannot escape UI callbacks",f.status().equals("failed")&&f.state().optString("reason").equals("send-failed")&&f.state().optInt("attempt")==3);
    String snapshot=f.state().toString();check("Snapshot contains neither document token nor raw sender exception",!snapshot.contains(DOC)&&!snapshot.contains("credentials")&&!snapshot.contains("private exception"));
    f=new Fixture();JSONObject receipt=f.observed();put(receipt,"url","https://chatgpt.com/c/private-id");put(receipt,"text","private chat body");put(receipt.optJSONArray("samples").optJSONObject(0),"secret","login-token");f.sync.receive(f.port,receipt);snapshot=f.state().toString();check("Snapshot strips unknown page fields and sample fields",!snapshot.contains("private-id")&&!snapshot.contains("private chat")&&!snapshot.contains("login-token")&&!snapshot.contains(DOC));
  }
  static void colorSyntaxBoundary(){
    JSONArray observations=new JSONArray();boolean rejected=true;
    for(String css:new String[]{"rgb(.)","rgb(---)","rgb(1111111111111111)"}){
      Fixture f=new Fixture();f.sync.connect(f.port,"1111111111111111",true);JSONObject r=f.observed();put(r.optJSONArray("samples").optJSONObject(0),"background",css);
      boolean accepted=f.sync.receive(f.port,r);String snapshot=f.state().toString();observations.put(o("input",css,"accepted",accepted,"status",f.status(),"documentTokenReflected",snapshot.contains("1111111111111111")));rejected&=!accepted;
    }
    if(!rejected)System.err.println(o("productionColorBoundary",observations));
    check("Invalid numeric CSS cannot confirm or reflect the document token",rejected);
    for(String css:new String[]{"rgb(20, 20, 20)","rgba(20, 20, 20, 0.9)","rgb(20 20 20 / 90%)","color(srgb 0.1 0.1 0.1)","oklab(0.2 0.01 -0.01)","oklch(20% 0.1 180)"}){
      Fixture f=new Fixture();JSONObject r=f.observed();put(r.optJSONArray("samples").optJSONObject(0),"background",css);check("Supported computed colour syntax preserved: "+css,f.sync.receive(f.port,r)&&f.status().equals("confirmed"));
    }
    Fixture f=new Fixture();f.sync.connect(f.port,"0000000000000020",true);JSONObject r=f.observed();put(r.optJSONArray("samples").optJSONObject(0),"background","rgb(0000000000000020,20,20)");check("Valid numeric colours are normalized before snapshots",f.sync.receive(f.port,r)&&f.status().equals("confirmed")&&!f.state().toString().contains("0000000000000020"));
    f=new Fixture();f.sync.connect(f.port,"1111111111111111",true);r=f.observed();put(r.optJSONArray("samples").optJSONObject(0),"backgroundLuminance",.1111111111111111);check("Luminance measurements cannot reflect an arbitrary long numeric token",f.sync.receive(f.port,r)&&f.status().equals("confirmed")&&!f.state().toString().contains("1111111111111111"));
  }
  public static void main(String[] args){boundedAndStages();strictBinding();coloursAndStorage();unknownAndMalformedSamples();lifecycleAndDrift();colorSyntaxBoundary();System.out.println(o("status","passed","hostScopeOnly",true,"actualAndroidExecution",false,"actualGeckoExecution",false,"checks",checks.length(),"results",checks));}
}
