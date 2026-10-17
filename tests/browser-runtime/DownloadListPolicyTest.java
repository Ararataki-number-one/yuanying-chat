package local.pocketchat;

import org.json.*;

public final class DownloadListPolicyTest {
  static int checks;
  static void check(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
  static JSONObject row(String id,int slot,String state,long time){return new JSONObject().put("id",id).put("slot",slot).put("state",state).put("time",time).put("uri","content://downloads/"+id);}
  public static void main(String[] args){
    JSONObject old=row("old",0,"saved",100),recent=row("recent",1,"saved",500),busy=row("active",7,"downloading",50);
    JSONArray all=DownloadListPolicy.ordered(new JSONArray().put(old).put(recent),new JSONArray().put(busy));
    check(all.getJSONObject(0)==busy,"A real active task comes before even the newest completed file");
    check(all.getJSONObject(1)==recent&&all.getJSONObject(2)==old,"Completed files use descending saved timestamp across environments");
    JSONObject newerBusy=row("next",1,"preparing",75);
    all=DownloadListPolicy.ordered(new JSONArray().put(old),new JSONArray().put(busy).put(newerBusy));
    check(all.getJSONObject(0)==newerBusy&&all.getJSONObject(1)==busy,"Active tasks also keep deterministic newest-first order");
    check(DownloadListPolicy.ordered(new JSONArray().put(recent),new JSONArray().put(row("recent",1,"saved",500))).length()==1,"Saved task and shared file index appear only once");
    String before=DownloadListPolicy.key(busy);busy.put("received",123).put("name","renamed.txt").put("updated",1000);
    check(before.equals(DownloadListPolicy.key(busy)),"Bytes, name and heartbeat do not replace a row identity");
    JSONObject other=row("active",0,"downloading",50);check(!before.equals(DownloadListPolicy.key(other)),"Same task id in different environments remains separate");
    JSONObject legacy=new JSONObject().put("slot",0).put("state","saved").put("uri","content://downloads/legacy");String legacyKey=DownloadListPolicy.key(legacy);
    check(!legacyKey.isEmpty()&&legacyKey.equals(DownloadListPolicy.key(new JSONObject(legacy.toString()))),"Legacy URI identity survives reload");
    check(DownloadListPolicy.preservedTime(legacy,null)==0,"Unknown legacy download time is never replaced with the current scan time");
    JSONObject original=new JSONObject(legacy.toString()).put("time",123456);
    check(DownloadListPolicy.preservedTime(legacy,original)==123456,"Repeated legacy indexing preserves an existing recorded timestamp");
    check(DownloadListPolicy.preservedTime(new JSONObject(legacy.toString()).put("id","new-download"),original)==0,"A different identity cannot inherit an old file time");
    check(DownloadListPolicy.preservedTime(new JSONObject(legacy.toString()).put("time",222222),original)==222222,"New real publication time remains authoritative");
    JSONArray tied=DownloadListPolicy.ordered(new JSONArray().put(row("z",0,"saved",100)).put(row("a",0,"saved",100)),new JSONArray());
    check(tied.getJSONObject(0).getString("id").equals("a"),"Equal times have a repeatable identity tie-breaker");
    for(String state:new String[]{"preparing","downloading","saving","choosing"})check(DownloadListPolicy.matches(row("active",0,state,1),1),"Live filter includes "+state);
    for(String state:new String[]{"paused","failed","cancelled","saved"})check(!DownloadListPolicy.matches(row("done",0,state,1),1),"Live filter excludes "+state);
    check(DownloadListPolicy.matches(old,2)&&!DownloadListPolicy.matches(busy,2),"Completed filter uses actual state");
    check(DownloadListPolicy.matches(row("error",0,"failed",1),3)&&!DownloadListPolicy.matches(row("paused",0,"paused",1),3),"Failed filter does not mislabel paused tasks");
    JSONObject changing=row("changing",2,"downloading",1),done=row("done",2,"saved",10);
    check(DownloadListPolicy.ordered(new JSONArray().put(done),new JSONArray().put(changing)).getJSONObject(0)==changing,"Active row sorts first before completion");
    changing.put("state","saved");
    check(DownloadListPolicy.ordered(new JSONArray().put(done),new JSONArray().put(changing)).getJSONObject(0)==done,"A later refresh reads the changed state rather than reusing stale sort fields");
    changing.put("time",20);
    check(DownloadListPolicy.ordered(new JSONArray().put(done),new JSONArray().put(changing)).getJSONObject(0)==changing,"A later refresh also reads the real completion timestamp");
    check(!DownloadListPolicy.busy(null),"Null state remains inactive");
    System.out.println("DownloadListPolicyTest: "+checks+" checks passed (JVM policy only)");
  }
}
