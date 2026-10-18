package local.pocketchat;
import java.util.*;
/** Production scheduler on host; measured WAN speed is explicitly outside this test. */
public final class NetworkOptimizationPolicyTest {
 static int passed;static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);passed++;}
 public static void main(String[] args){
  List<String> nodes=new ArrayList<>();for(int i=0;i<32;i++)nodes.add("node"+i);
  Map<String,Integer> counts=new HashMap<>(),delays=new HashMap<>();
  for(String n:nodes){counts.put(n,10);delays.put(n,410);}counts.put("node29",1);delays.put("node29",180);
  List<String> batch=NetworkOptimizationPolicy.adaptiveBatch(nodes,nodes,"node0",4,counts,delays);
  check(batch.contains("node29"),"New fast challenger earns confirmation despite mature slow history");
  check(batch.contains("node0")&&batch.contains("node1"),"Keep current and best established route");
  check(batch.contains("node4")&&batch.size()==4,"Exploration has a reserved bounded slot");
  Set<String> explored=new HashSet<>();for(int i=0;i<32;i++){List<String> r=NetworkOptimizationPolicy.adaptiveBatch(nodes,nodes,"node0",i,counts,delays);check(r.size()<=4&&nodes.containsAll(r)&&new HashSet<>(r).size()==r.size(),"Bounded allowed nodes without duplicates");explored.addAll(r);}
  check(explored.containsAll(nodes),"No node starvation across one rotation");
  delays.put("node29",-1);check(!NetworkOptimizationPolicy.adaptiveBatch(nodes,nodes,"node0",4,counts,delays).contains("node29"),"Cold or failed measurements cannot masquerade as fast comparable evidence");
  check(NetworkOptimizationPolicy.adaptiveBatch(Collections.emptyList(),nodes,"node0",0,counts,delays).isEmpty(),"Empty pool cannot invent a route");
  check(NetworkOptimizationPolicy.adaptiveBatch(Collections.singletonList("node0"),nodes,"node0",Integer.MIN_VALUE,counts,delays).equals(Collections.singletonList("node0")),"Singleton and cursor overflow remain bounded");
  List<String> selected=NetworkOptimizationPolicy.websiteBatch(nodes,Arrays.asList("node29","node1","node0"),"node0");
  check(selected.equals(Arrays.asList("node0","node29")),"Only active route and best challenger get anonymous website probes");
  check(NetworkOptimizationPolicy.websiteBatch(Collections.singletonList("node0"),nodes,"node0").size()==1,"Single route is not measured twice");
  check(!NetworkOptimizationPolicy.websiteDue("ok",1000,120999)&&NetworkOptimizationPolicy.websiteDue("ok",1000,121000),"Fresh success is reused and later renewed");
  check(!NetworkOptimizationPolicy.websiteDue("restricted",1000,300999)&&NetworkOptimizationPolicy.websiteDue("restricted",1000,301000),"Challenges back off instead of increasing request load");
  check(NetworkOptimizationPolicy.websiteDue("ok",0,1000)&&NetworkOptimizationPolicy.websiteDue("ok",100000,1),"Missing or clock-shifted evidence cannot suppress probing");
  check(NetworkOptimizationPolicy.scanInterval(0)==60000&&NetworkOptimizationPolicy.scanInterval(2)==60000&&NetworkOptimizationPolicy.scanInterval(3)==120000,"Three initial bounded discovery rounds then quieter steady state");
  check(NetworkOptimizationPolicy.websiteComparable("ok",1000,121000,3,180),"Recent repeated successful website measurements can be compared");
  check(!NetworkOptimizationPolicy.websiteComparable("restricted",1000,2000,5,180),"A challenge cannot reuse older website success to override chain evidence");
  check(!NetworkOptimizationPolicy.websiteComparable("ok",1000,2000,2,180),"An unconfirmed challenger does not enter website ranking");
  check(!NetworkOptimizationPolicy.websiteComparable("ok",1000,301001,5,180)&&!NetworkOptimizationPolicy.websiteComparable("ok",1000,999,5,180),"Stale and future website evidence cannot pin selection");
  System.out.println("{\"passed\":"+passed+",\"scope\":\"Production candidate scheduler only; not Android or public latency\"}");
 }
}
