package local.pocketchat;

import java.util.Objects;
import java.util.UUID;

/** Connection pools follow the verified data route, not asynchronous UI operations. */
final class NetworkPoolIdentity {
  /** Each default-network event is retained even when the UI refresh is coalesced. */
  static final class DefaultNetwork {
    private String identity="";
    private boolean known,internet,vpn;
    private long revision;
    private NetworkSnapshot current=new NetworkSnapshot("",false,false,false,0);
    synchronized void available(String value){
      if(value==null||value.isEmpty()){unknown();return;}
      if(value.equals(identity))return;
      change(value,false,false,false);
    }
    synchronized void capabilities(String value,boolean hasInternet,boolean isVpn){
      if(value==null||value.isEmpty()||!value.equals(identity))return;
      change(value,true,hasInternet,isVpn);
    }
    synchronized void initial(String value,boolean hasInternet,boolean isVpn){
      if(value==null||value.isEmpty()){unknown();return;}
      change(value,true,hasInternet,isVpn);
    }
    synchronized void lost(String value){if(identity.equals(value))unknown();}
    synchronized void unknown(){change("",false,false,false);}
    private void change(String value,boolean nextKnown,boolean nextInternet,boolean nextVpn){
      if(identity.equals(value)&&known==nextKnown&&internet==nextInternet&&vpn==nextVpn)return;
      identity=value;known=nextKnown;internet=nextInternet;vpn=nextVpn;revision++;current=new NetworkSnapshot(identity,known,internet,vpn,revision);
    }
    synchronized NetworkSnapshot snapshot(){return current;}
  }
  static final class NetworkSnapshot {
    final String identity;
    final boolean known,internet,vpn;
    final long revision;
    NetworkSnapshot(String identity,boolean known,boolean internet,boolean vpn,long revision){this.identity=identity;this.known=known;this.internet=internet;this.vpn=vpn;this.revision=revision;}
    boolean usable(){return known&&internet&&!identity.isEmpty();}
    @Override public boolean equals(Object other){
      if(!(other instanceof NetworkSnapshot))return false;NetworkSnapshot n=(NetworkSnapshot)other;
      return revision==n.revision&&known==n.known&&internet==n.internet&&vpn==n.vpn&&identity.equals(n.identity);
    }
    @Override public int hashCode(){return Objects.hash(identity,known,internet,vpn,revision);}
  }
  /** Admission uses the existing verified receipt before constructing this value. */
  static final class Route {
    final int slot,corePid,servicePid,controllerPort,proxyPort;
    final String generation,configuration,entry,fixedExit;
    // Compared only in memory; the public pool key contains none of this value.
    private final String controlIdentity;
    final long serial;
    Route(int slot,String generation,int corePid,int servicePid,String configuration,String entry,String fixedExit,long serial,int controllerPort,int proxyPort,String controlIdentity){
      this.slot=slot;this.generation=generation;this.corePid=corePid;this.servicePid=servicePid;this.configuration=configuration;this.entry=entry;this.fixedExit=fixedExit;this.serial=serial;this.controllerPort=controllerPort;this.proxyPort=proxyPort;this.controlIdentity=controlIdentity;
    }
    boolean usable(){return slot>=0&&present(generation)&&corePid>1&&servicePid>1&&present(configuration)&&present(entry)&&present(fixedExit)&&present(controlIdentity)&&serial>0&&port(controllerPort)&&port(proxyPort);}
    private static boolean present(String value){return value!=null&&!value.isEmpty();}
    private static boolean port(int value){return value>0&&value<=65535;}
    @Override public boolean equals(Object other){
      if(!(other instanceof Route))return false;Route r=(Route)other;
      return slot==r.slot&&corePid==r.corePid&&servicePid==r.servicePid&&serial==r.serial&&controllerPort==r.controllerPort&&proxyPort==r.proxyPort&&Objects.equals(generation,r.generation)&&Objects.equals(configuration,r.configuration)&&Objects.equals(entry,r.entry)&&Objects.equals(fixedExit,r.fixedExit)&&Objects.equals(controlIdentity,r.controlIdentity);
    }
    @Override public int hashCode(){return Objects.hash(slot,generation,corePid,servicePid,configuration,entry,fixedExit,serial,controllerPort,proxyPort,controlIdentity);}
  }
  private final String instance=UUID.randomUUID().toString();
  private long revision;
  private Route previous;
  private NetworkSnapshot network;
  private String key;
  synchronized String key(Route route,NetworkSnapshot current){
    if(route==null||!route.usable()||current==null||!current.usable()){
      previous=null;network=null;key=null;return null;
    }
    if(key==null||!route.equals(previous)||!current.equals(network)){
      previous=route;network=current;key="environment-pool-"+instance+"-"+(++revision);
    }
    return key;
  }
}
