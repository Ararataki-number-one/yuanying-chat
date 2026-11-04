package local.pocketchat;

import org.json.*;
import java.util.*;

/** Executes production query/collection policies; no Android layout or device claims. */
public final class DiscoveryCases {
  static int checks;static final Map<Integer,DownloadOwnerLabels.Owner> owners=new LinkedHashMap<>();
  static void check(String name,boolean value){checks++;if(!value)throw new AssertionError(name);}
  static JSONObject row(int n,String name,String mime,String owner,int generation)throws Exception{return new JSONObject().put("id","file"+n).put("slot",0).put("state","saved").put("time",n+1).put("uri","content://fixture/"+n).put("name",name).put("mime",mime).put("environmentId",owner).put("environmentGeneration",generation);}
  static JSONObject row(int n)throws Exception{return row(n,"文件-"+n+".pdf","application/pdf","current",2);}
  public static void main(String[] args)throws Exception{
    owners.put(0,new DownloadOwnerLabels.Owner(0,"研究工作","current",2,true,false,false));
    JSONArray all=new JSONArray();for(int i=0;i<103;i++)all.put(row(i));
    JSONArray searched=new DownloadQuery("文件-102","",0,0).select(all,0,owners);DownloadPageWindow found=new DownloadPageWindow(searched,0,"");
    check("Search finds the final record beyond first 40 rows",found.total==1&&found.rows.getJSONObject(0).getString("id").equals("file102"));
    check("Search ANDs normalized tokens across filename and owner",new DownloadQuery("文件-102 研究","",0,0).select(all,0,owners).length()==1);
    check("Unmatched token returns empty",new DownloadQuery("文件-102 missing","",0,0).select(all,0,owners).length()==0);
    JSONObject wide=row(200,"ＦＩＮＡＬ Ｒｅｐｏｒｔ.PDF","application/pdf","current",2);
    check("Search normalizes fullwidth/case",new DownloadQuery("final report","",0,0).select(new JSONArray().put(wide),0,owners).length()==1);
    check("Search is bounded",new DownloadQuery(String.join("",Collections.nCopies(201,"x")),"",0,0).text.length()==200);
    JSONObject old=row(201,"old.pdf","application/pdf","old",1),unknown=row(202);unknown.remove("environmentId");JSONObject reset=row(203,"reset.pdf","application/pdf","current",1);
    JSONArray lineage=new JSONArray().put(row(1)).put(old).put(unknown).put(reset);
    String exact=DownloadQuery.identity(0,"current",2);
    check("Owner filter binds slot/id/generation",new DownloadQuery("",exact,0,0).select(lineage,0,owners).length()==1);
    check("Reused slots remain historical",new DownloadQuery("","historical",0,0).select(lineage,0,owners).length()==2);
    check("Legacy records remain separately unconfirmed",new DownloadQuery("","unknown",0,0).select(lineage,0,owners).length()==1);
    owners.put(0,new DownloadOwnerLabels.Owner(0,"新主人","replacement",3,true,false,false));
    check("Stored owner filter never changes owner on slot reuse",new DownloadQuery("",exact,0,0).select(lineage,0,owners).length()==1);
    check("Historical records include prior current owner after reuse",new DownloadQuery("","historical",0,0).select(lineage,0,owners).length()==3);
    owners.put(0,new DownloadOwnerLabels.Owner(0,"研究工作","current",2,true,false,false));
    check("Document extension works for generic MIME",DownloadQuery.kind(row(3,"research.DOCX","application/octet-stream","current",2))==1);
    check("Image MIME works without extension",DownloadQuery.kind(row(3,"asset","image/png","current",2))==2);
    JSONObject discoveredMime=row(4,"asset","application/octet-stream","current",2).put("actualMime","application/pdf");check("Type keyword search follows actual provider MIME",new DownloadQuery("pdf","",0,0).select(new JSONArray().put(discoveredMime),0,owners).length()==1);
    check("Media extension works for generic MIME",DownloadQuery.kind(row(3,"recording.m4a","application/octet-stream","current",2))==3);
    check("Archive classification",DownloadQuery.kind(row(3,"files.7z","application/octet-stream","current",2))==4);
    check("Android package classification precedes archive",DownloadQuery.kind(row(3,"client.apk","application/zip","current",2))==5);
    check("Unknown binary classification",DownloadQuery.kind(row(3,"artifact.bin","application/octet-stream","current",2))==6);
    JSONArray mixed=new JSONArray().put(row(1)).put(row(2,"photo.png","image/png","current",2)).put(old);
    check("Search owner and kind predicates combine",new DownloadQuery("photo",exact,2,0).select(mixed,2,owners).length()==1);
    check("State filter is applied before pagination",new DownloadQuery("",exact,2,0).select(mixed,1,owners).length()==0);
    JSONObject a=row(8),b=row(9);a.put("savedBytes",Long.MAX_VALUE);b.put("savedBytes",200);JSONObject missing=row(10);
    JSONArray sizes=new DownloadQuery("","",0,3).select(new JSONArray().put(missing).put(b).put(a),0,owners);
    check("Largest sort handles long sizes without overflow",sizes.getJSONObject(0).getString("id").equals("file8"));
    check("Unknown sizes remain after known sizes",sizes.getJSONObject(2).getString("id").equals("file10"));
    JSONArray newest=new DownloadQuery("","",0,1).select(all,0,owners);check("Newest sort reverses old insertion order",newest.getJSONObject(0).getString("id").equals("file102"));
    JSONArray oldest=new DownloadQuery("","",0,2).select(all,0,owners);check("Oldest sort is stable",oldest.getJSONObject(0).getString("id").equals("file0"));
    JSONObject z=row(1,"z.txt","text/plain","current",2),alpha=row(2,"Ａlpha.txt","text/plain","current",2);
    check("Filename sort uses normalized names",new DownloadQuery("","",0,4).select(new JSONArray().put(z).put(alpha),0,owners).getJSONObject(0).getString("id").equals("file2"));
    Set<String> seen=new HashSet<>();String anchor="";int pages=0;do{DownloadPageWindow page=new DownloadPageWindow(newest,0,anchor);check("Each discovered page remains bounded",page.rows.length()<=40);for(int i=0;i<page.rows.length();i++)check("No duplicate across discovered pages",seen.add(page.rows.getJSONObject(i).getString("id")));anchor=page.next;pages++;}while(!anchor.isEmpty());check("All discovered rows accessible through paging",seen.size()==103&&pages==3);
    DownloadCollection collection=new DownloadCollection();JSONObject picked=row(500);check("Saved content file can be collected",collection.toggle(picked));picked.put("name","mutated");check("Collection snapshots the explicit choice",!collection.snapshot().getJSONObject(0).getString("name").equals("mutated"));
    JSONObject sameUri=row(501);sameUri.put("uri",picked.getString("uri"));check("Same URI cannot enter basket twice",!collection.toggle(sameUri)&&collection.size()==1);
    JSONObject newer=new JSONObject(picked.toString()).put("time",9999);check("Republication is a distinct identity",!collection.contains(newer));
    check("A replaced URI publication is not silently swapped",!collection.toggle(newer)&&collection.snapshot().getJSONObject(0).getLong("time")==501);
    check("Selecting same publication removes it",collection.toggle(collection.snapshot().getJSONObject(0))&&collection.size()==0);
    for(int i=0;i<DownloadCollection.LIMIT;i++)check("Collect choices across pages",collection.toggle(row(i)));
    check("Collection has bounded capacity",!collection.toggle(row(90))&&collection.size()==DownloadCollection.LIMIT);
    JSONArray snapshot=collection.snapshot();DownloadCollection restored=new DownloadCollection();restored.restore(snapshot);check("Rotation restore retains exact chosen publications",restored.size()==DownloadCollection.LIMIT&&restored.contains(snapshot.getJSONObject(25)));
    JSONObject live=row(900).put("state","downloading"),unsafe=row(901).put("uri","file:///private/secret");check("Live tasks cannot become files",!collection.toggle(live));check("Raw file path cannot be shared",!collection.toggle(unsafe));
    check("Identical MIME collection is specific",DownloadCollection.mime(new JSONArray().put(row(5)).put(row(6))).equals("application/pdf"));check("Mixed MIME collection stays generic",DownloadCollection.mime(new JSONArray().put(row(5)).put(row(6,"pic.jpg","image/jpeg","current",2))).equals("*/*"));
    Object activity=new Object();DownloadCollectionSession.State first=DownloadCollectionSession.get(activity);first.files.toggle(row(2));first.collecting=true;check("Native tab controller retains basket",DownloadCollectionSession.get(activity).files.size()==1&&DownloadCollectionSession.get(activity).collecting);check("Other activities get separate choices",DownloadCollectionSession.get(new Object()).files.size()==0);
    System.out.println(new JSONObject().put("status","passed").put("checks",checks).put("scope","production query, pagination, collection identity and session policies; host Java, no Android layout").toString());
  }
}
