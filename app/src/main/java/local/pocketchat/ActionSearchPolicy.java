package local.pocketchat;

import java.text.Normalizer;
import java.util.*;

/** Searches only app-owned action labels; no page content or credentials enter the index. */
final class ActionSearchPolicy {
  static final int RECENT_LIMIT=6;
  static final class Item {
    final String id,label,detail,aliases;
    Item(String id,String label,String detail,String aliases){this.id=id;this.label=label;this.detail=detail;this.aliases=aliases;}
  }
  static String normalize(String value){return Normalizer.normalize(value==null?"":value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT).trim().replaceAll("\\s+"," ");}
  static int score(Item item,String query){
    String q=normalize(query),label=normalize(item.label),all=label+" "+normalize(item.detail)+" "+normalize(item.aliases);
    if(q.isEmpty())return 0;
    for(String term:q.split(" "))if(!all.contains(term))return -1;
    return label.equals(q)?400:label.startsWith(q)?300:label.contains(q)?200:100;
  }
  static List<Item> search(List<Item> items,String query,List<String> recent){
    List<Item> result=new ArrayList<>();for(Item item:items)if(score(item,query)>=0)result.add(item);
    boolean empty=normalize(query).isEmpty();
    result.sort((left,right)->{int a=score(left,query),b=score(right,query);if(a!=b)return Integer.compare(b,a);if(empty){int l=recent.indexOf(left.id),r=recent.indexOf(right.id);return Integer.compare(l<0?Integer.MAX_VALUE:l,r<0?Integer.MAX_VALUE:r);}return 0;});
    return result;
  }
  static List<String> recent(String stored,List<Item> available){
    Set<String> valid=new HashSet<>();for(Item item:available)valid.add(item.id);
    List<String> ids=new ArrayList<>();for(String id:(stored==null?"":stored).split(","))if(valid.contains(id)&&!ids.contains(id)&&ids.size()<RECENT_LIMIT)ids.add(id);return ids;
  }
  static String remember(String id,List<String> previous){
    List<String> next=new ArrayList<>();next.add(id);for(String old:previous)if(!old.equals(id)&&next.size()<RECENT_LIMIT)next.add(old);return String.join(",",next);
  }
}
