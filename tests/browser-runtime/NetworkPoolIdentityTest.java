package local.pocketchat;

import java.util.Objects;

/** Reconnects reuse only the same admitted route; transient route/network changes stay monotonic. */
public final class NetworkPoolIdentityTest {
  static int checks;
  static void check(String message,boolean value){if(!value)throw new AssertionError(message);checks++;}
  static NetworkPoolIdentity.Route route(int slot,String generation,int corePid,int servicePid,String configuration,String entry,String exit,long serial,int controller,int proxy){return new NetworkPoolIdentity.Route(slot,generation,corePid,servicePid,configuration,entry,exit,serial,controller,proxy,"secret-control-token-A");}
  static NetworkPoolIdentity.Route original(){return route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4040);}
  static NetworkPoolIdentity.DefaultNetwork internet(){NetworkPoolIdentity.DefaultNetwork n=new NetworkPoolIdentity.DefaultNetwork();n.initial("network-100",true,false);return n;}
  static void changed(String message,NetworkPoolIdentity.Route next){NetworkPoolIdentity p=new NetworkPoolIdentity();NetworkPoolIdentity.DefaultNetwork n=internet();check(message,!p.key(original(),n.snapshot()).equals(p.key(next,n.snapshot())));}
  public static void main(String[] args){
    NetworkPoolIdentity p=new NetworkPoolIdentity();NetworkPoolIdentity.DefaultNetwork n=internet();String first=p.key(original(),n.snapshot());
    check("A fully known, verified route obtains an opaque key",first!=null&&first.startsWith("environment-pool-"));
    for(int i=0;i<1000;i++)if(!first.equals(p.key(original(),n.snapshot())))throw new AssertionError("Healthy recovery changed the connection pool");
    check("1000 same-route recoveries and fresh receipt objects preserve the pool",first.equals(p.key(original(),n.snapshot())));
    check("The key exposes neither control token, network, route names, config nor exit identity",!first.contains("secret-control-token-A")&&!first.contains("network-100")&&!first.contains("configuration-A")&&!first.contains("entry-A")&&!first.contains("fixed-exit-A")&&!first.contains("core-generation-A"));
    check("A separate browser instance cannot share the prior instance pool",!first.equals(new NetworkPoolIdentity().key(original(),n.snapshot())));
    changed("Different environments isolate pools",route(3,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4040));
    changed("Different core generation isolates pools",route(2,"core-generation-B",101,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4040));
    changed("Different core process isolates pools",route(2,"core-generation-A",111,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4040));
    changed("Different owning service process isolates pools",route(2,"core-generation-A",101,222,"configuration-A","entry-A","fixed-exit-A",1,3030,4040));
    changed("Changed network configuration isolates pools",route(2,"core-generation-A",101,202,"configuration-B","entry-A","fixed-exit-A",1,3030,4040));
    changed("Changed entry isolates pools",route(2,"core-generation-A",101,202,"configuration-A","entry-B","fixed-exit-A",1,3030,4040));
    changed("Changed fixed exit isolates pools",route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-B",1,3030,4040));
    changed("Changed route serial isolates pools even when endpoints match",route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",3,3030,4040));
    changed("Changed controller listener isolates pools",route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",1,3333,4040));
    changed("Changed proxy listener isolates pools",route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4444));
    changed("Changed control token isolates pools even with identical generation, PIDs and serial",new NetworkPoolIdentity.Route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",1,3030,4040,"secret-control-token-B"));
    NetworkPoolIdentity.Route b=route(2,"core-generation-A",101,202,"configuration-A","entry-B","fixed-exit-A",2,3030,4040),back=route(2,"core-generation-A",101,202,"configuration-A","entry-A","fixed-exit-A",3,3030,4040);
    String middle=p.key(b,n.snapshot()),again=p.key(back,n.snapshot());
    check("Route A to B to A never revives the old A pool",!first.equals(middle)&&!first.equals(again)&&!middle.equals(again));
    p=new NetworkPoolIdentity();first=p.key(original(),n.snapshot());
    check("A to B to A while no page requested B still retires A via serial",!first.equals(p.key(back,n.snapshot())));
    first=p.key(back,n.snapshot());n.available("network-100");n.capabilities("network-100",true,false);
    check("Duplicate available/capability notifications preserve healthy pools",first.equals(p.key(back,n.snapshot())));
    n.lost("stale-network");n.capabilities("stale-network",true,true);
    check("Late old-network callbacks cannot poison the current default pool",first.equals(p.key(back,n.snapshot())));
    n.available("network-200");
    check("A newly available network without capabilities is not admitted",p.key(back,n.snapshot())==null);
    n.capabilities("network-200",true,false);middle=p.key(back,n.snapshot());
    check("A confirmed new default network obtains a different pool",middle!=null&&!first.equals(middle));
    n.available("network-100");n.capabilities("network-100",true,false);again=p.key(back,n.snapshot());
    check("Network A to B to A does not reuse old A connections",!first.equals(again)&&!middle.equals(again));
    first=again;n.available("network-200");n.capabilities("network-200",true,false);n.available("network-100");n.capabilities("network-100",true,false);
    check("Coalesced UI refresh cannot hide network A to B to A events",!first.equals(p.key(back,n.snapshot())));
    first=p.key(back,n.snapshot());n.capabilities("network-100",true,true);middle=p.key(back,n.snapshot());
    check("VPN transport added on the same network ID isolates its pool",!first.equals(middle));
    n.capabilities("network-100",true,false);again=p.key(back,n.snapshot());
    check("VPN transport removal cannot revive pre-VPN connections",!first.equals(again)&&!middle.equals(again));
    first=again;n.capabilities("network-100",false,false);
    check("A network without INTERNET capabilities is not admitted",p.key(back,n.snapshot())==null);
    n.capabilities("network-100",true,false);
    check("Restoring INTERNET capabilities retires the pre-loss pool",!first.equals(p.key(back,n.snapshot())));
    first=p.key(back,n.snapshot());n.lost("network-100");
    check("Losing the current default network blocks pool admission",p.key(back,n.snapshot())==null);
    n.available("network-100");n.capabilities("network-100",true,false);
    check("Even the same network ID after loss receives a fresh pool",!first.equals(p.key(back,n.snapshot())));
    first=p.key(back,n.snapshot());check("Unknown receipt cannot obtain a reusable pool",p.key(null,n.snapshot())==null);
    check("Returning after unknown receipt cannot revive the old pool",!first.equals(p.key(back,n.snapshot())));
    first=p.key(back,n.snapshot());check("Unknown default-network snapshot cannot obtain a pool",p.key(back,null)==null);
    check("Returning after missing network snapshot gets a fresh pool",!first.equals(p.key(back,n.snapshot())));
    NetworkPoolIdentity.Route[] invalid={route(-1,"g",101,202,"c","e","x",1,3030,4040),route(2,"",101,202,"c","e","x",1,3030,4040),route(2,"g",1,202,"c","e","x",1,3030,4040),route(2,"g",101,1,"c","e","x",1,3030,4040),route(2,"g",101,202,"","e","x",1,3030,4040),route(2,"g",101,202,"c","","x",1,3030,4040),route(2,"g",101,202,"c","e","",1,3030,4040),route(2,"g",101,202,"c","e","x",0,3030,4040),route(2,"g",101,202,"c","e","x",1,0,4040),route(2,"g",101,202,"c","e","x",1,3030,65536)};
    for(int i=0;i<invalid.length;i++){first=p.key(back,n.snapshot());check("Incomplete route field "+i+" blocks admission",p.key(invalid[i],n.snapshot())==null);check("Invalid route field "+i+" retires the previous valid key",!Objects.equals(first,p.key(back,n.snapshot())));}
    n.unknown();n.capabilities("network-100",true,false);
    check("Late capabilities cannot restore a lost default network",p.key(back,n.snapshot())==null);
    System.out.println("{\"passed\":"+checks+",\"scope\":\"production pool identity and default network events on JVM; no Android or HTTP2 renderer\"}");
  }
}
