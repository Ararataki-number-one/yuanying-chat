package local.pocketchat;

import java.text.Normalizer;
import java.util.*;

/** Pure search/presentation rules shared by the profile-local recovery workspaces. */
final class LocalContinuityPolicy {
  private LocalContinuityPolicy(){}
  static String normalized(String value){return Normalizer.normalize(value==null?"":value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT);}
  static boolean matches(String query,String... fields){
    String value=normalized(String.join("\n",fields));
    for(String word:normalized(query).trim().split("\\s+"))if(!word.isEmpty()&&!value.contains(word))return false;
    return true;
  }
  static String preview(String value,int limit){
    return LocalMessageIndex.preview(value,limit,null);
  }
  static String role(String value){return "user".equals(value)?"我":"assistant".equals(value)?"ChatGPT":"system".equals(value)?"系统":"消息";}
  static final class Draft {
    final String body,origin,url;final long created;
    Draft(String body,String origin,String url,long created){this.body=body==null?"":body;this.origin=origin==null||origin.isEmpty()?"暂存草稿":origin;this.url=url==null?"":url;this.created=created;}
  }
  static List<Draft> drafts(Collection<Draft> records,String query,int limit){
    List<Draft> ordered=new ArrayList<>(records);ordered.sort((a,b)->Long.compare(b.created,a.created));
    Set<String> bodies=new HashSet<>();List<Draft> result=new ArrayList<>();
    for(Draft row:ordered)if(!row.body.trim().isEmpty()&&matches(query,row.origin,row.body)&&bodies.add(row.body)){result.add(row);if(result.size()>=limit)break;}
    return result;
  }
  static final class Message {
    final String role,text;final int position;
    Message(String role,String text,int position){this.role=role==null?"":role;this.text=text==null?"":text;this.position=position;}
  }
  static List<Message> messages(Collection<Message> records,String query){
    List<Message> result=new ArrayList<>();for(Message row:records)if(!row.text.trim().isEmpty()&&matches(query,row.text))result.add(row);return result;
  }
  static String transcript(String title,List<Message> messages){
    StringBuilder result=new StringBuilder(title==null?"":title);for(Message row:messages)result.append("\n\n").append(role(row.role)).append("\n").append(row.text);return result.toString();
  }
  static boolean copyFits(String title,List<Message> messages,int maximum){long length=title==null?0:title.length();for(Message row:messages){length+=row.text.length()+role(row.role).length()+3;if(length>maximum)return false;}return length<=maximum;}
}
