package local.pocketchat;

import java.util.*;
import java.util.concurrent.CancellationException;

/** A bounded, dialog-owned index. Repeated message pages reuse the last search. */
final class LocalMessageIndex {
  static final int NORMALIZED_LIMIT=1024*1024;
  static final class Stats {long visits,normalizations,normalizedCharacters,resultHits,previewCodePoints;int retainedCharacters;}
  final List<LocalContinuityPolicy.Message> messages;
  final IdentityHashMap<LocalContinuityPolicy.Message,String> normalized=new IdentityHashMap<>();
  final Stats stats=new Stats();
  Query previous;List<LocalContinuityPolicy.Message> result;
  LocalMessageIndex(List<LocalContinuityPolicy.Message> messages){List<LocalContinuityPolicy.Message> selected=new ArrayList<>();for(LocalContinuityPolicy.Message row:messages)if(!row.text.trim().isEmpty())selected.add(row);this.messages=Collections.unmodifiableList(selected);}
  static void interrupted(){if(Thread.currentThread().isInterrupted())throw new CancellationException();}
  static final class Query {
    final String key;final String[] words;
    Query(String value){String text=LocalContinuityPolicy.normalized(value).trim();words=text.isEmpty()?new String[0]:text.split("\\s+");key=String.join(" ",words);}
    boolean matches(String value){for(String word:words)if(!value.contains(word))return false;return true;}
    boolean refines(Query earlier){for(String old:earlier.words){boolean covered=false;for(String word:words)if(word.contains(old)){covered=true;break;}if(!covered)return false;}return true;}
  }
  String text(LocalContinuityPolicy.Message row){
    String value=normalized.get(row);if(value!=null)return value;
    interrupted();value=LocalContinuityPolicy.normalized(row.text);stats.normalizations++;stats.normalizedCharacters+=row.text.length();
    if(value.length()<=NORMALIZED_LIMIT-stats.retainedCharacters){normalized.put(row,value);stats.retainedCharacters+=value.length();}return value;
  }
  synchronized List<LocalContinuityPolicy.Message> search(String value){
    interrupted();Query query=new Query(value);if(previous!=null&&previous.key.equals(query.key)){stats.resultHits++;return result;}
    Collection<LocalContinuityPolicy.Message> candidates=previous!=null&&query.refines(previous)?result:messages;
    List<LocalContinuityPolicy.Message> selected=new ArrayList<>();
    for(LocalContinuityPolicy.Message row:candidates){interrupted();stats.visits++;if(query.words.length==0||query.matches(text(row)))selected.add(row);}
    interrupted();previous=query;result=Collections.unmodifiableList(selected);return result;
  }
  static final class Match {
    final boolean matched,messageMatch;final LocalContinuityPolicy.Message first;
    Match(boolean matched,boolean messageMatch,LocalContinuityPolicy.Message first){this.matched=matched;this.messageMatch=messageMatch;this.first=first;}
  }
  synchronized Match document(String title,String value){
    interrupted();Query query=new Query(value);LocalContinuityPolicy.Message first=messages.isEmpty()?null:messages.get(0);
    if(first==null)return new Match(false,false,null);
    if(query.words.length==0)return new Match(true,false,first);
    String heading=LocalContinuityPolicy.normalized(title);if(query.matches(heading))return new Match(true,false,first);
    boolean[] found=new boolean[query.words.length];for(int i=0;i<found.length;i++)found[i]=heading.contains(query.words[i]);
    for(LocalContinuityPolicy.Message row:messages){interrupted();stats.visits++;String body=text(row);boolean all=true;for(int i=0;i<found.length;i++){boolean has=body.contains(query.words[i]);found[i]|=has;all&=has;}if(all)return new Match(true,true,row);}
    for(boolean present:found)if(!present)return new Match(false,false,first);return new Match(true,false,first);
  }
  /** Stops after a complete visible prefix; never regex-copies an entire reply. */
  static String preview(String source,int limit,Stats stats){
    if(source==null||source.isEmpty())return "";limit=Math.max(0,limit);
    StringBuilder text=new StringBuilder(Math.min(limit+2,512)),pending=new StringBuilder();int count=0,pendingCount=0;boolean whitespace=false;
    for(int offset=0;offset<source.length();){int cp=source.codePointAt(offset);offset+=Character.charCount(cp);if(stats!=null)stats.previewCodePoints++;
      if(cp<=32){
        if(count==0)continue;boolean fold=cp==' '||cp=='\t'||cp=='\n'||cp=='\r'||cp=='\f'||cp==11;
        if(!fold||!whitespace){if(pendingCount<=limit){pending.appendCodePoint(fold?' ':cp);pendingCount++;}}whitespace=fold;continue;
      }
      if(pendingCount>0){for(int at=0;at<pending.length();){int gap=pending.codePointAt(at);at+=Character.charCount(gap);if(count>=limit)return text+"…";text.appendCodePoint(gap);count++;}pending.setLength(0);pendingCount=0;}
      whitespace=false;if(count>=limit)return text+"…";text.appendCodePoint(cp);count++;
    }
    return text.toString();
  }
}
