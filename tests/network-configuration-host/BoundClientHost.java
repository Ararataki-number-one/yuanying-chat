package local.pocketchat;
import android.os.*;import org.json.*;
public final class BoundClientHost {
 static final JSONArray checks=new JSONArray();static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 public static void main(String[] args)throws Exception{
  EnvironmentSpec.Identity owner=new EnvironmentSpec.Identity(1,3,"11111111-1111-1111-1111-111111111111");
  for(String action:new String[]{"launch","stop"}){
   NetworkTransportClientHost.Fixture f=new NetworkTransportClientHost.Fixture();f.open();String expected=action.equals("launch")?"previous-core":"";Throwable[] error={null};JSONObject[] response={null};
   Thread call=new Thread(()->{try{response[0]=f.client.callBound(action,"configuration-fingerprint",NetworkDiagnostics.Reason.UNKNOWN,expected,owner);}catch(Throwable failure){error[0]=failure;}});call.start();
   NetworkTransportClientHost.waitFor(()->f.remote.received.size()==1,true,"bound command sent");Bundle data=f.remote.received.get(0).getData();
   check(action+" explicitly guards even an empty expected core generation",data.getBoolean("guardGeneration",false)&&data.getString("expectedGeneration").equals(expected));
   JSONObject identity=new JSONObject(data.getString("expectedOwner"));check(action+" carries exact stable owner and generation",identity.getInt("slot")==1&&identity.getInt("generation")==3&&identity.getString("environmentId").equals(owner.environmentId));
   f.remote.reply(0,NetworkTransportClientHost.state("new-core"),true);NetworkTransportClientHost.waitFor(()->!call.isAlive(),true,"bound reply complete");call.join();check(action+" uses the same correlated production IPC reply",error[0]==null&&response[0].optString("generation").equals("new-core"));
  }
  NetworkTransportClientHost.Fixture f=new NetworkTransportClientHost.Fixture();EnvironmentSpec.Identity wrong=new EnvironmentSpec.Identity(2,3,owner.environmentId);boolean denied=false;try{f.client.callBound("launch","fingerprint",NetworkDiagnostics.Reason.UNKNOWN,"",wrong);}catch(Exception expected){denied=true;}
  check("Wrong profile owner is rejected before any bind or foreground start",denied&&f.context.bindings.isEmpty()&&f.context.foreground==0);
  denied=false;try{f.client.callBound("stop","",NetworkDiagnostics.Reason.UNKNOWN,"",null);}catch(Exception expected){denied=true;}check("Missing owner cannot create an unqualified bound stop",denied&&f.context.bindings.isEmpty());
  System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualBinderExecution",false,"actualServiceExecution",false));
 }
}
