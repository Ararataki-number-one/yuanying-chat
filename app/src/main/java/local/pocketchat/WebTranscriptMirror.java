package local.pocketchat;

import java.util.*;
import org.json.*;

/** UI-thread mirror of incremental website observations; published arrays are immutable. */
final class WebTranscriptMirror {
  String documentId="",url="";int revision=-1;
  final Map<String,JSONObject> rows=new HashMap<>();
  final List<String> order=new ArrayList<>();
  JSONObject arguments(){return J.obj("documentId",documentId,"revision",revision);}
  void reset(){documentId="";revision=-1;url="";rows.clear();order.clear();}
  JSONArray accept(JSONObject data,JSONArray previous,String previousUrl){
    if(!data.optBoolean("ok")||!data.optBoolean("changed"))return null;
    if(data.optBoolean("reset")||!documentId.equals(data.optString("documentId"))){rows.clear();order.clear();}
    JSONArray changed=data.optJSONArray("changes");
    for(int i=0;changed!=null&&i<changed.length();i++){JSONObject row=changed.optJSONObject(i);if(row!=null)rows.put(row.optString("id"),row);}
    JSONArray incomingOrder=data.optJSONArray("order");
    if(incomingOrder!=null){order.clear();for(int i=0;i<incomingOrder.length();i++)order.add(incomingOrder.optString(i));rows.keySet().retainAll(new HashSet<>(order));}
    JSONArray current=new JSONArray();for(String id:order){JSONObject row=rows.get(id);if(row==null){reset();return null;}current.put(row);}
    String nextUrl=data.optString("url");
    JSONArray merged=same(previousUrl,nextUrl)?earlier(previous,current):current;
    documentId=data.optString("documentId");revision=data.optInt("revision");url=nextUrl;
    return merged;
  }
  static boolean same(String a,String b){return WebReplyObserver.same(a,b);}
  static JSONArray earlier(JSONArray previous,JSONArray incoming){
    if(incoming.length()==0)return incoming;
    String first=incoming.optJSONObject(0).optString("id");int anchor=-1;
    for(int i=0;i<previous.length();i++)if(first.equals(previous.optJSONObject(i).optString("id"))){anchor=i;break;}
    if(anchor<=0)return incoming;
    JSONArray out=new JSONArray();for(int i=0;i<anchor;i++)out.put(previous.optJSONObject(i));for(int i=0;i<incoming.length();i++)out.put(incoming.optJSONObject(i));return out;
  }
}
