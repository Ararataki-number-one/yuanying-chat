package local.pocketchat;
import android.content.*;import org.json.*;import java.util.*;

/** Recent complete-chain samples; a healthy route is not replaced for one fast probe. */
final class RouteQuality {
 static final long WINDOW=30*60*1000L,COOLDOWN=2*60*1000L;
 final SharedPreferences prefs;JSONObject data;String scope="",selected="",candidate="";long switched=0;int wins=0;
 RouteQuality(Context c){this(c,"route-quality");}
 RouteQuality(Context c,String store){prefs=c.getSharedPreferences(store,0);data=J.parse(prefs.getString("samples","{}"));scope=prefs.getString("scope","");selected=prefs.getString("selected","");candidate=prefs.getString("candidate","");switched=prefs.getLong("switched",0);wins=prefs.getInt("wins",0);}
 synchronized List<String> ranked(List<String> names,long now){List<String> sorted=new ArrayList<>(names);sorted.sort(Comparator.comparingDouble(name->{JSONObject s=stats(name,now);return LatencyProbePolicy.comparable(s.optString("kind"),s.optInt("latest"))&&s.optInt("warmLatest")>0?s.optDouble("score"):Double.MAX_VALUE;}));return sorted;}
 synchronized void configure(String value){if(value.equals(scope))return;scope=value;data=new JSONObject();selected="";candidate="";switched=0;wins=0;save();}
 // The website-quality store supplies its own comparable response measurements.
 synchronized void record(String name,int delay,long now){record(name,delay,now,"warm",new JSONObject());}
 synchronized void record(String name,int delay,long now,String kind,JSONObject probe){record(name,delay,now,kind,probe,new JSONObject());}
 synchronized void record(String name,int delay,long now,String kind,JSONObject probe,JSONObject binding){if(name==null||name.isEmpty())return;JSONArray old=data.optJSONArray(name),next=new JSONArray();if(old!=null)for(int i=Math.max(0,old.length()-19);i<old.length();i++){JSONObject x=old.optJSONObject(i);if(x!=null&&now-x.optLong("t")<=WINDOW&&x.optLong("t")<=now+60000)next.put(x);}next.put(J.obj("t",now,"d",delay,"kind",kind,"probe",probe,"binding",binding));try{data.put(name,next);}catch(Exception ignored){}save();}
 synchronized JSONObject stats(String name,long now){
  JSONArray a=data.optJSONArray(name);int count=0,ok=0,failures=0,warm=0;double sum=0,squares=0;int latest=-1,warmLatest=-1;long lastAt=0;String kind="unknown";JSONObject probe=new JSONObject(),binding=new JSONObject();
  if(a!=null)for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x==null||now-x.optLong("t")>WINDOW||x.optLong("t")>now+60000)continue;int d=x.optInt("d",-1);count++;latest=d;lastAt=x.optLong("t");kind=x.optString("kind","unknown");probe=x.optJSONObject("probe");if(probe==null)probe=new JSONObject();binding=x.optJSONObject("binding");if(binding==null)binding=new JSONObject();if(d>0){ok++;failures=0;if("warm".equals(kind)){warm++;warmLatest=d;sum+=d;squares+=(double)d*d;}}else failures++;}
  double mean=warm==0?0:sum/warm,jitter=warm==0?0:Math.sqrt(Math.max(0,squares/warm-mean*mean)),rate=count==0?0:(double)ok/count;double score=warm==0?1000000:mean+1.5*jitter+3000*(1-rate)+failures*1000+Math.max(0,3-warm)*180;
  return J.obj("samples",count,"successes",ok,"warmSamples",warm,"warmLatest",warmLatest,"rate",rate,"mean",Math.round(mean),"jitter",Math.round(jitter),"score",score,"latest",latest,"lastAt",lastAt,"failures",failures,"kind",kind,"probe",probe,"binding",binding);
 }
 /** Candidate measurements never become the current window's displayed trace or health. */
 synchronized JSONObject currentSample(String name,long now,String route){
  JSONArray samples=data.optJSONArray(name);JSONObject result=new JSONObject();if(samples==null)return result;
  for(int i=0;i<samples.length();i++){JSONObject x=samples.optJSONObject(i);if(x==null||now-x.optLong("t")>WINDOW||x.optLong("t")>now+60000)continue;JSONObject b=x.optJSONObject("binding");String origin=b==null?"":b.optString("origin");if(!LatencyProbePolicy.currentSample(origin,b==null?"":b.optString("route"),route))continue;
   result=J.obj("delay",x.optInt("d",-1),"at",x.optLong("t"),"kind",origin.isEmpty()?"unknown":x.optString("kind","unknown"),"probe",origin.isEmpty()?new JSONObject():x.optJSONObject("probe"),"measurement",b==null?0:b.optLong("measurement"));
  }return result;
 }
 synchronized String choose(List<String> names,String current,boolean force,boolean busy,long now){String best="";double score=Double.MAX_VALUE;for(String name:names){JSONObject x=stats(name,now);if(LatencyProbePolicy.comparable(x.optString("kind"),x.optInt("latest"))&&x.optInt("warmLatest")>0&&x.optDouble("score")<score){best=name;score=x.optDouble("score");}}if(best.isEmpty())return current;if(best.equals(candidate))wins++;else{candidate=best;wins=1;}save();if(force||current.isEmpty())return best;JSONObject health=stats(current,now);if(health.optInt("latest")<=0)return health.optInt("failures")>=2?best:current;if(health.optInt("warmLatest")<=0||!"warm".equals(health.optString("kind"))||best.equals(current)||busy||cooldown(now)>0||wins<2)return current;JSONObject c=stats(current,now),n=stats(best,now);if(n.optInt("warmSamples")<3||n.optDouble("rate")<.8)return current;double previous=c.optDouble("score");return score<=previous*.75&&previous-score>=100?best:current;}
 synchronized long cooldown(long now){if(switched>now+60000){switched=now;save();}return Math.max(0,Math.min(COOLDOWN,COOLDOWN-(now-switched)));}
 String chooseWithWebsite(RouteQuality website,Map<String,JSONObject> observations,List<String> names,String current,boolean force,boolean busy,long now){
  // A mature current route alone is not a comparison. Missing or challenged
  // challenger evidence must not lock out a proven faster complete chain.
  List<String> comparable=new ArrayList<>(),reachable=new ArrayList<>();
  for(String name:names){JSONObject observed=observations.get(name),stats=website.stats(name,now);
   if(observed!=null&&NetworkOptimizationPolicy.websiteComparable(observed.optString("status"),observed.optLong("at"),now,stats.optInt("warmSamples"),stats.optInt("latest")))comparable.add(name);
   boolean failed=observed!=null&&"unreachable".equals(observed.optString("status"))&&observed.optLong("at")>0&&now>=observed.optLong("at")&&now-observed.optLong("at")<=300000;
   if(force||name.equals(current)||!failed)reachable.add(name);
  }
  boolean paired=!force&&comparable.contains(current)&&comparable.size()>1;
  return (paired?website:this).choose(paired?comparable:reachable,current,force,busy,now);
 }
 synchronized void selected(String name,long now){if(!name.equals(selected)){selected=name;switched=now;candidate="";wins=0;save();}}
 void save(){prefs.edit().putString("scope",scope).putString("samples",data.toString()).putString("selected",selected).putString("candidate",candidate).putLong("switched",switched).putInt("wins",wins).apply();}
}
