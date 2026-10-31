package local.pocketchat;

import java.util.*;
import java.util.regex.*;

/** Bounded semantic Markdown subset. No HTML, remote resources or inferred release claims. */
final class ReleaseNotes {
  static final int MAX_TEXT=12000,MAX_BLOCKS=512;
  static final int PARAGRAPH=0,HEADING=1,BULLET=2,CODE=3,ORDERED=4;
  static final class Block {final int kind;final String text;Block(int k,String t){kind=k;text=t;}}
  final List<Block> user,technical;
  ReleaseNotes(List<Block> user,List<Block> technical){this.user=Collections.unmodifiableList(user);this.technical=Collections.unmodifiableList(technical);}
  static final Set<String> USER=new HashSet<>(Arrays.asList("本次更新","这次更新","更新内容","用户可见变化","主要变化","用户更新说明","用户更新内容"));
  static final Pattern HEADING_LINE=Pattern.compile("^(#{1,6})[ \\t]+(.+?)\\s*#*\\s*$"),LIST=Pattern.compile("^(?:[-+*]|[0-9]{1,6}[.)])[ \\t]+(.+)$");
  static final Pattern ORDERED_LINE=Pattern.compile("^([0-9]{1,6})[.)][ \\t]+(.+)$");
  static String field(String text){return text==null?"":text;}
  static ReleaseNotes parse(String notes,String details,boolean explicit){
    List<Block> user=new ArrayList<>(),technical=new ArrayList<>();
    parseInto(field(notes),explicit,false,user,technical);parseInto(field(details),false,true,user,technical);
    return new ReleaseNotes(user,technical);
  }
  static ReleaseNotes legacy(String body){return parse(body,"",false);}
  static void parseInto(String text,boolean explicit,boolean forceTechnical,List<Block> user,List<Block> technical){
    if(text.length()>MAX_TEXT){technical.add(new Block(PARAGRAPH,"发布说明较长，请查看此版本的官方发布页。"));return;}
    boolean code=false;int technicalParent=0;boolean userSection=explicit;int count=0;
    for(String original:text.replace("\r\n","\n").replace('\r','\n').split("\n",-1)){
      String line=code?original:original.trim();if(line.isEmpty()&&!code)continue;
      if(++count>MAX_BLOCKS){technical.add(new Block(PARAGRAPH,"其余说明请查看此版本的官方发布页。"));break;}
      if(line.trim().startsWith("```")||line.trim().startsWith("~~~")){code=!code;continue;}
      Matcher heading=HEADING_LINE.matcher(line);int kind=code?CODE:PARAGRAPH;
      if(!code&&heading.matches()){
        int level=heading.group(1).length();String title=inline(heading.group(2)).replaceFirst("[：:]$","").trim();
        if(!explicit&&level==1&&title.matches("(?:元婴期院士\\s*)?v?[0-9]+[.][0-9]+[.][0-9]+(?:[\\s（(:：].*)?")){technicalParent=0;userSection=false;if(!title.matches("(?:元婴期院士\\s*)?v?[0-9]+[.][0-9]+[.][0-9]+(?:[（(][0-9]+[）)])?"))technical.add(new Block(HEADING,title));continue;}
        // A technical ancestor cannot be escaped by a nested user-looking heading.
        if(technicalParent>0&&level<=technicalParent)technicalParent=0;
        if(explicit){userSection=!technicalTitle(title);if(!userSection)technicalParent=level;}
        else {userSection=technicalParent==0&&USER.contains(title);if(!userSection)technicalParent=technicalParent==0?level:technicalParent;}
        // A version-only document title is redundant, but never discard a substantive title.
        if(title.matches("(?:元婴期院士\\s*)?[0-9]+[.][0-9]+[.][0-9]+(?:[（(][0-9]+[）)])?")){if(!explicit)technicalParent=0;continue;}
        line=title;kind=HEADING;
      }else if(!code){Matcher ordered=ORDERED_LINE.matcher(line),list=LIST.matcher(line);if(ordered.matches()){kind=ORDERED;line=ordered.group(1)+". "+ordered.group(2);}else if(list.matches()){kind=BULLET;line=list.group(1);}else if(line.startsWith("> "))line=line.substring(2);line=inline(line);}
      (!forceTechnical&&userSection&&technicalParent==0?user:technical).add(new Block(kind,line));
    }
  }
  static boolean technicalTitle(String title){return title.matches(".*(?:技术|开发|实现|工程|AES.GCM|提交|源码|构建|验证|测试|限制|边界|门禁|证据|交付|发布记录).*");}
  /** Preserve destination as text. No URLSpan can silently invoke an external browser. */
  static String inline(String line){
    StringBuilder out=new StringBuilder();
    for(int i=0;i<line.length();){char c=line.charAt(i);
      if(c=='\\'&&i+1<line.length()&&"\\`*_{}[]()#+-.!>".indexOf(line.charAt(i+1))>=0){out.append(line.charAt(i+1));i+=2;continue;}
      int start=c=='!'&&i+1<line.length()&&line.charAt(i+1)=='['?i+1:i;
      if(line.charAt(start)=='['){int end=line.indexOf("](",start+1);if(end>start&&end-start<=2048){int close=linkEnd(line,end+2);if(close>end){if(start!=i)out.append("图片：");out.append(line,start+1,end).append('（').append(line,end+2,close).append('）');i=close+1;continue;}}}
      if(c=='`'){int end=line.indexOf('`',i+1);if(end>i+1){out.append(line,i+1,end);i=end+1;continue;}}
      if((c=='*'||c=='_')&&i+1<line.length()){String mark=line.startsWith(""+c+c,i)?""+c+c:""+c;int end=line.indexOf(mark,i+mark.length());boolean word=c=='_'&&i>0&&Character.isLetterOrDigit(line.charAt(i-1));if(!word&&end>i+mark.length()){out.append(line,i+mark.length(),end);i=end+mark.length();continue;}}
      out.append(c);i++;
    }return out.toString();
  }
  static int linkEnd(String text,int start){int depth=0;for(int i=start;i<text.length()&&i-start<=2048;i++){char c=text.charAt(i);if(c=='\\'){i++;continue;}if(c=='('){if(++depth>8)return -1;}else if(c==')'){if(depth==0)return i;depth--;}}return -1;}
}
