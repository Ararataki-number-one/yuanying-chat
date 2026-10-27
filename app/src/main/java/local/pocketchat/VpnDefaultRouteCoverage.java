package local.pocketchat;

import java.util.List;

/** Conservative admission from an Android route snapshot, not a tunnel/DNS test. */
final class VpnDefaultRouteCoverage {
  // Android public route kinds. The adapter reads them only on API 33+.
  static final int UNICAST=1,UNREACHABLE=7,THROW=9;
  static final class Route {
    final int addressBytes,prefixLength,type;
    final String networkInterface;
    Route(int addressBytes,int prefixLength,int type,String networkInterface){
      this.addressBytes=addressBytes;this.prefixLength=prefixLength;
      this.type=type;this.networkInterface=networkInterface;
    }
  }
  static String issue(String networkInterface,List<Route> routes){
    if(networkInterface==null||networkInterface.isEmpty())return "vpn-interface-unavailable";
    if(routes==null||routes.isEmpty())return "vpn-routes-unavailable";
    boolean ipv4=false,ipv6=false;
    for(Route route:routes){
      if(route==null||(route.addressBytes!=4&&route.addressBytes!=16)||route.prefixLength<0||route.prefixLength>route.addressBytes*8)return "vpn-route-unavailable";
      if(route.type==THROW)return "vpn-route-exclusion";
      // A known unreachable route blocks; it does not authorize another table.
      // It also cannot establish either required default unicast route.
      if(route.type==UNREACHABLE)continue;
      if(route.type!=UNICAST)return "vpn-route-type-unavailable";
      if(!networkInterface.equals(route.networkInterface))return "vpn-route-interface-mismatch";
      if(route.prefixLength==0){if(route.addressBytes==4)ipv4=true;else ipv6=true;}
    }
    if(!ipv4)return "vpn-ipv4-default-unconfirmed";
    if(!ipv6)return "vpn-ipv6-default-unconfirmed";
    return "";
  }
  private VpnDefaultRouteCoverage(){}
}
