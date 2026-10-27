package local.pocketchat;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Exercises the real policy with controlled OS-route snapshots; no Android claim. */
public final class VpnDefaultRouteCoverageHost {
  static int checks;
  static final StringBuilder results=new StringBuilder();
  static VpnDefaultRouteCoverage.Route route(int bytes,int prefix,int type,String iface){return new VpnDefaultRouteCoverage.Route(bytes,prefix,type,iface);}
  static VpnDefaultRouteCoverage.Route v4(){return route(4,0,1,"tun0");}
  static VpnDefaultRouteCoverage.Route v6(){return route(16,0,1,"tun0");}
  static List<VpnDefaultRouteCoverage.Route> rows(VpnDefaultRouteCoverage.Route... routes){return Arrays.asList(routes);}
  static void expect(String name,String iface,List<VpnDefaultRouteCoverage.Route> routes,String expected){
    String actual=VpnDefaultRouteCoverage.issue(iface,routes);
    if(!expected.equals(actual))throw new AssertionError(name+": expected="+expected+", actual="+actual);
    if(checks++>0)results.append(',');
    results.append("{\"name\":\"").append(name).append("\",\"pass\":true,\"issue\":\"").append(actual).append("\"}");
  }
  public static void main(String[] args){
    expect("Actual full fixture dual defaults and host routes","tun0",rows(v4(),v6(),route(4,32,1,"tun0"),route(16,128,1,"tun0")),"");
    expect("Actual split fixture is not full IPv4 coverage","tun0",rows(route(4,15,1,"tun0"),route(16,0,7,null),route(4,32,1,"tun0")),"vpn-ipv4-default-unconfirmed");
    expect("IPv4 only with IPv6 blocked is conservatively unconfirmed","tun0",rows(v4(),route(16,0,7,null)),"vpn-ipv6-default-unconfirmed");
    expect("IPv6 only cannot authorize IPv4","tun0",rows(v6()),"vpn-ipv4-default-unconfirmed");
    expect("More specific THROW cannot escape the VPN table","tun0",rows(v4(),v6(),route(4,24,9,null)),"vpn-route-exclusion");
    expect("Default THROW cannot coexist with accepted defaults","tun0",rows(v4(),v6(),route(16,0,9,null)),"vpn-route-exclusion");
    expect("Unknown route kind remains unconfirmed","tun0",rows(v4(),v6(),route(4,24,255,"tun0")),"vpn-route-type-unavailable");
    expect("Default on another interface cannot count as VPN coverage","tun0",rows(route(4,0,1,"wlan0"),v6()),"vpn-route-interface-mismatch");
    expect("More specific unicast on another interface stays rejected","tun0",rows(v4(),v6(),route(4,24,1,"wlan0")),"vpn-route-interface-mismatch");
    expect("Null unicast interface is not inferred","tun0",rows(route(4,0,1,null),v6()),"vpn-route-interface-mismatch");
    expect("Missing VPN interface remains unconfirmed",null,rows(v4(),v6()),"vpn-interface-unavailable");
    expect("Empty VPN interface remains unconfirmed","",rows(v4(),v6()),"vpn-interface-unavailable");
    expect("Missing route snapshot remains unconfirmed","tun0",null,"vpn-routes-unavailable");
    expect("Empty route snapshot remains unconfirmed","tun0",Collections.emptyList(),"vpn-routes-unavailable");
    expect("Null route cannot disappear from the snapshot","tun0",rows(v4(),v6(),null),"vpn-route-unavailable");
    expect("Unknown address family is rejected","tun0",rows(v4(),v6(),route(0,0,1,"tun0")),"vpn-route-unavailable");
    expect("Out of range IPv4 prefix is rejected","tun0",rows(v4(),v6(),route(4,33,1,"tun0")),"vpn-route-unavailable");
    expect("Negative prefix is rejected","tun0",rows(v4(),v6(),route(16,-1,1,"tun0")),"vpn-route-unavailable");
    expect("Protected more specific unicast remains compatible","tun0",rows(v4(),v6(),route(4,24,1,"tun0")),"");
    expect("Unreachable more specific route is a block not a bypass","tun0",rows(v4(),v6(),route(4,24,7,null)),"");
    expect("Split default layout is not guessed into default coverage","tun0",rows(route(4,1,1,"tun0"),route(4,1,1,"tun0"),v6()),"vpn-ipv4-default-unconfirmed");
    expect("Duplicate protected defaults do not cause a false rejection","tun0",rows(v4(),v4(),v6()),"");
    expect("Malformed unreachable route is still unknown data","tun0",rows(v4(),v6(),route(3,0,7,null)),"vpn-route-unavailable");
    System.out.println("{\"schema\":1,\"status\":\"passed\",\"passed\":"+checks+",\"actualAndroidExecution\":false,\"actualNetworkExecution\":false,\"results\":["+results+"]}");
  }
}
