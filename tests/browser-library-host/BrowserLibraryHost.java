package local.pocketchat;

import android.content.*;
import java.util.*;
import org.json.*;

/** The complete library runs with a controlled, environment-local preference store. */
public final class BrowserLibraryHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static String url(int index){return "https://example.com/page/"+index;}
  static JSONObject row(String address,String title){return J.obj("url",address,"title",title,"time",1234);}
  static String repeat(String value,int count){StringBuilder out=new StringBuilder();for(int i=0;i<count;i++)out.append(value);return out.toString();}
  static void bounds()throws Exception{
    MemoryContext context=new MemoryContext();BrowserLibrary library=new BrowserLibrary(context);
    check("The library uses only its environment-specific browser preference record",context.requested.equals("universal-browser")&&context.store.writes==0);
    check("A new environment starts with no browser history or bookmarks",library.list("history").length()==0&&library.list("bookmarks").length()==0);
    check("Actual hard limits remain history 200 and bookmarks 100",BrowserLibrary.limit("history")==200&&BrowserLibrary.limit("bookmarks")==100);
    for(int i=0;i<250;i++)library.remember("history",url(i),"Page "+i,200);
    JSONArray history=library.list("history");Set<String> unique=new HashSet<>();for(int i=0;i<history.length();i++)unique.add(history.getJSONObject(i).getString("url"));
    check("250 visits retain exactly the latest 200 unique entries",history.length()==200&&unique.size()==200&&history.getJSONObject(0).getString("url").equals(url(249))&&history.getJSONObject(199).getString("url").equals(url(50))&&!unique.contains(url(49)));
    check("Saved history contains URL/title/time only",history.getJSONObject(0).length()==3&&history.getJSONObject(0).getString("title").equals("Page 249")&&history.getJSONObject(0).getLong("time")>0);
    library.remember("history",url(125),"Revisited",200);history=library.list("history");int matches=0;for(int i=0;i<history.length();i++)if(history.getJSONObject(i).getString("url").equals(url(125)))matches++;
    check("Revisiting moves one URL to the front and updates its title",history.length()==200&&matches==1&&history.getJSONObject(0).getString("url").equals(url(125))&&history.getJSONObject(0).getString("title").equals("Revisited"));
    for(int i=0;i<130;i++)library.remember("bookmarks",url(i),"Bookmark "+i,Integer.MAX_VALUE);
    JSONArray bookmarks=library.list("bookmarks");
    check("Bookmark caller limits cannot exceed the actual 100-entry cap",bookmarks.length()==100&&bookmarks.getJSONObject(0).getString("url").equals(url(129))&&bookmarks.getJSONObject(99).getString("url").equals(url(30)));
    check("Bookmark writes preserve the independent history collection",library.list("history").length()==200&&library.list("history").getJSONObject(0).getString("title").equals("Revisited"));
    library.remember("history",url(999),"Tight limit",3);check("A smaller caller limit retains exactly its newest three entries",library.list("history").length()==3);
    library.remember("history",url(1000),null,0);history=library.list("history");check("A nonpositive caller limit still yields a bounded one-row record",history.length()==1&&history.getJSONObject(0).getString("title").equals(url(1000)));
    library.remember("history",url(1001),"",200);check("Missing or empty titles fall back to the URL",library.list("history").getJSONObject(0).getString("title").equals(url(1001)));
    int writes=context.store.writes;for(String address:new String[]{"javascript:alert(1)","https://user:pass@example.com/","https://127.0.0.1/","file:///tmp/page","search words"})library.remember("history",address,"Invalid",200);
    check("Invalid and credential-bearing addresses never enter persistence",context.store.writes==writes&&library.list("history").length()==2);
  }
  static void restore()throws Exception{
    MemoryContext context=new MemoryContext();BrowserLibrary library=new BrowserLibrary(context);
    for(String raw:new String[]{"not-json","{}","null","[broken"}){context.store.values.put("history",raw);check("Malformed preference recovers to an empty list: "+raw,library.list("history").length()==0);}
    JSONArray old=new JSONArray();old.put(3);old.put(JSONObject.NULL);old.put("text");old.put(new JSONObject());old.put(row("javascript:alert(1)","Bad"));old.put(row("https://user:pass@example.com/","Private"));old.put(row(url(1),"First"));old.put(row(url(1),"Duplicate"));old.put(row(url(2),"Second"));
    context.store.values.put("history",old.toString());JSONArray clean=library.list("history");
    check("Restoration drops nonobjects, missing/unsafe URLs and duplicate entries",clean.length()==2&&clean.getJSONObject(0).getString("title").equals("First")&&clean.getJSONObject(1).getString("title").equals("Second"));
    String raw=context.store.values.get("history");check("Read-only cleanup never rewrites old preference bytes",context.store.writes==0&&context.store.values.get("history").equals(raw));
    library.remember("history",url(3),"Newest",200);JSONArray persisted=new JSONArray(context.store.values.get("history"));check("The next actual visit persists only repaired valid rows",persisted.length()==3&&persisted.getJSONObject(0).getString("url").equals(url(3))&&persisted.getJSONObject(1).getString("url").equals(url(1)));
    old=new JSONArray();for(int i=0;i<300;i++)old.put(row(url(i),"Page"));context.store.values.put("history",old.toString());context.store.values.put("bookmarks",old.toString());
    check("Oversized restored arrays obey each collection's cap",library.list("history").length()==200&&library.list("bookmarks").length()==100);
    context.store.values.put("history",repeat(" ",2*1024*1024+1));check("Raw records beyond two MiB are rejected before JSON processing",library.list("history").length()==0);
    library.remember("history",url(7),"Recovered",200);check("A valid visit recovers from an oversized old record",library.list("history").length()==1&&library.list("history").getJSONObject(0).getString("title").equals("Recovered"));
    JSONArray fresh=library.list("history");fresh.getJSONObject(0).put("title","Only in caller");fresh.put(row(url(8),"Extra"));check("Mutating a returned list cannot mutate serialized preference storage",library.list("history").length()==1&&library.list("history").getJSONObject(0).getString("title").equals("Recovered"));
  }
  static void titles()throws Exception{
    MemoryContext context=new MemoryContext();BrowserLibrary library=new BrowserLibrary(context);
    library.remember("history",url(1),repeat("x",20000),200);check("Arbitrary website titles are bounded to 300 UTF-16 units",library.list("history").getJSONObject(0).getString("title").length()==300&&context.store.values.get("history").length()<1000);
    String crossing=repeat("a",299)+"\ud83d\ude00"+"after";library.remember("history",url(2),crossing,200);String trimmed=library.list("history").getJSONObject(0).getString("title");
    check("Truncation never cuts a surrogate pair at the boundary",trimmed.length()==299&&!Character.isHighSurrogate(trimmed.charAt(trimmed.length()-1)));
    String fitting=repeat("a",298)+"\ud83d\ude00";check("A complete surrogate pair fitting exactly at the limit is preserved",BrowserLibrary.title(fitting,url(1)).equals(fitting));
    context.store.values.put("bookmarks",new JSONArray().put(row(url(3),crossing)).toString());check("Restored old long titles receive the same bounded cleanup",library.list("bookmarks").getJSONObject(0).getString("title").length()==299);
  }
  static void removalAndScope()throws Exception{
    MemoryContext first=new MemoryContext(),second=new MemoryContext();BrowserLibrary library=new BrowserLibrary(first),other=new BrowserLibrary(second);
    library.remember("bookmarks",url(1),"Bookmark",100);library.remember("bookmarks",url(2),"Second",100);library.remember("history",url(1),"Visit",200);
    check("Bookmark membership reads actual saved records",library.bookmarked(url(1))&&library.bookmarked(url(2))&&!library.bookmarked(url(3)));
    library.remove("bookmarks",url(1));check("Removing a bookmark leaves other bookmarks and history intact",!library.bookmarked(url(1))&&library.bookmarked(url(2))&&library.list("history").length()==1);
    first.store.values.put("bookmarks",new JSONArray().put(row(url(1),"A")).put(row(url(1),"Duplicate")).put(row(url(2),"Keep")).toString());library.remove("bookmarks",url(1));check("Removal eliminates every restored duplicate of the selected URL",library.list("bookmarks").length()==1&&library.bookmarked(url(2))&&!library.bookmarked(url(1)));
    library.clearHistory();check("Clearing history removes only its storage key",!first.store.values.containsKey("history")&&library.list("history").length()==0&&library.bookmarked(url(2)));
    library.remove("bookmarks",url(99));check("Removing an absent URL preserves valid remaining records",library.list("bookmarks").length()==1);
    BrowserLibrary reopened=new BrowserLibrary(first);check("Reopening the same environment recalls the serialized bookmark collection",reopened.bookmarked(url(2)));
    check("Different supplied environment contexts cannot see each other's collections",other.list("bookmarks").length()==0&&other.list("history").length()==0&&!other.bookmarked(url(2)));
    other.remember("history",url(9),"Second environment",200);check("Writing or clearing one context does not change the other environment",other.list("history").length()==1&&library.list("history").length()==0&&library.bookmarked(url(2)));
    boolean rejected=false;try{library.list("passwords");}catch(IllegalArgumentException expected){rejected=true;}check("Unknown collection names cannot read arbitrary preference records",rejected);
  }
  public static void main(String[]args)throws Exception{bounds();restore();titles();removalAndScope();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}
class MemoryContext extends Context {
  final MemoryPreferences store=new MemoryPreferences();String requested="";
  @Override public SharedPreferences getSharedPreferences(String name,int mode){requested=name;if(!name.equals("universal-browser"))throw new AssertionError("Unexpected preference collection");return store;}
}
class MemoryPreferences implements SharedPreferences {
  final Map<String,String> values=new HashMap<>();int writes;
  public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor(){final Map<String,String> staged=new HashMap<>();final Set<String> removed=new HashSet<>();public Editor putString(String key,String value){staged.put(key,value);return this;}public Editor remove(String key){removed.add(key);return this;}public void apply(){writes++;for(String key:removed)values.remove(key);values.putAll(staged);}};}
}
