package local.pocketchat;
import android.content.Context;
import java.util.*;
import org.json.*;

public final class RouteQualityComparisonTest {
  static int passed;static final long NOW=1000000;
  static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);passed++;}
  static void samples(RouteQuality q,String name,int ms){for(int i=0;i<5;i++)q.record(name,ms,NOW-100+i);}
  public static void main(String[] args){
    Context context=new Context();RouteQuality chain=new RouteQuality(context,"chain"),web=new RouteQuality(context,"web");
    List<String> names=Arrays.asList("current","fast");Map<String,JSONObject> observations=new HashMap<>();
    samples(chain,"current",410);samples(chain,"fast",180);samples(web,"current",3200);
    chain.selected("current",NOW-RouteQuality.COOLDOWN-1);web.selected("current",NOW-RouteQuality.COOLDOWN-1);
    observations.put("current",J.obj("status","ok","at",NOW));
    chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW);
    check(chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW).equals("fast"),"A mature incumbent website history cannot suppress proven faster chain evidence");
    check(chain.chooseWithWebsite(web,observations,names,"current",false,true,NOW).equals("current"),"Busy chat still defers switching");
    samples(web,"fast",9000);observations.put("fast",J.obj("status","ok","at",NOW));
    check(chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW).equals("current"),"Paired website evidence rejects a chain that is slower to the actual site");
    observations.put("fast",J.obj("status","restricted","at",NOW));
    check(chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW).equals("fast"),"A new challenge invalidates old website comparisons without marking the route failed");
    observations.put("fast",J.obj("status","unreachable","at",NOW));
    check(chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW).equals("current"),"A candidate known to fail website transport cannot win via a fast probe URL");
    observations.put("fast",J.obj("status","ok","at",NOW-300001));
    chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW);
    check(chain.chooseWithWebsite(web,observations,names,"current",false,false,NOW).equals("fast"),"Expired website evidence falls back to fresh chain quality");
    observations.put("fast",J.obj("status","ok","at",NOW));
    check(chain.chooseWithWebsite(web,observations,names,"current",true,false,NOW).equals("fast"),"Explicit forced chain selection retains existing behavior");
    check(chain.chooseWithWebsite(web,observations,Collections.singletonList("current"),"current",false,false,NOW).equals("current"),"Selection cannot escape the allowed node pool");
    chain.selected("other",NOW);chain.selected("current",NOW);
    check(chain.chooseWithWebsite(web,Collections.emptyMap(),names,"current",false,false,NOW).equals("current"),"Fallback preserves cooldown instead of flapping");
    check(new RouteQuality(context,"chain").stats("fast",NOW).optInt("warmSamples")==5,"Comparison retains persistent quality samples");
    System.out.println("{\"passed\":"+passed+",\"actualAndroidExecution\":false,\"scope\":\"production route choice with in-memory preferences\"}");
  }
}
