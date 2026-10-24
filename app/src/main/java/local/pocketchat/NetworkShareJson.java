package local.pocketchat;

import org.json.*;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.regex.Pattern;

/** Sharing-only JSON: retain unsigned integers and floating point scalar kinds.
 * Android JSONObject round trips can round uint64, clamp doubles to long, and
 * serialize integral doubles as integers. Raw plugin maps need the original
 * numeric value and kind for both native decoding and fingerprint verification. */
final class NetworkShareJson {
  static final int DEPTH=12,NODES=1048576;
  static final Pattern NUMBER=Pattern.compile("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?");
  static IOException invalid(){return new IOException("分享 JSON 格式不支持或超出限制");}
  static final class Budget {int remaining=NODES;void visit(int depth)throws IOException{if(depth>DEPTH||--remaining<0)throw invalid();}}
  /** A schema-1 Android receiver uses its lossy JSONObject number writer.
   * Other numbers (e.g. fractional doubles) remain compatible with that wire. */
  static boolean requiresExactNumbers(Object value){try{return requiresExactNumbers(value,new Budget(),0);}catch(IOException invalid){throw new IllegalArgumentException(invalid.getMessage());}}
  static boolean requiresExactNumbers(Object value,Budget budget,int depth)throws IOException{
    budget.visit(depth);
    if(value instanceof JSONObject){JSONObject object=(JSONObject)value;for(Iterator<String> i=object.keys();i.hasNext();)if(requiresExactNumbers(object.opt(i.next()),budget,depth+1))return true;}
    else if(value instanceof JSONArray){JSONArray array=(JSONArray)value;for(int i=0;i<array.length();i++)if(requiresExactNumbers(array.opt(i),budget,depth+1))return true;}
    else if(value instanceof BigInteger)return ((BigInteger)value).bitLength()>63;
    else if(value instanceof Double||value instanceof Float){double number=((Number)value).doubleValue();return number==(double)((Number)value).longValue();}
    return false;
  }
  static Object copy(Object value)throws Exception{return copy(value,new Budget(),0);}
  static Object copy(Object value,Budget budget,int depth)throws Exception{
    budget.visit(depth);
    if(value instanceof JSONObject){JSONObject out=new JSONObject(),in=(JSONObject)value;for(Iterator<String> i=in.keys();i.hasNext();){String key=i.next();out.put(key,copy(in.opt(key),budget,depth+1));}return out;}
    if(value instanceof JSONArray){JSONArray out=new JSONArray(),in=(JSONArray)value;for(int i=0;i<in.length();i++)out.put(copy(in.opt(i),budget,depth+1));return out;}
    if(value==null||value==JSONObject.NULL||value instanceof String||value instanceof Boolean||value instanceof Number)return value;
    throw invalid();
  }
  static String encode(Object value,int limit)throws Exception{StringBuilder out=new StringBuilder();write(value,out,new Budget(),0,limit);String text=out.toString();if(text.getBytes(StandardCharsets.UTF_8).length>limit)throw invalid();return text;}
  static void write(Object value,StringBuilder out,Budget budget,int depth,int limit)throws Exception{
    budget.visit(depth);
    if(value==null||value==JSONObject.NULL)out.append("null");
    else if(value instanceof JSONObject){out.append('{');JSONObject object=(JSONObject)value;boolean comma=false;for(Iterator<String> i=object.keys();i.hasNext();){String key=i.next();if(comma)out.append(',');comma=true;out.append(JSONObject.quote(key)).append(':');write(object.opt(key),out,budget,depth+1,limit);}out.append('}');}
    else if(value instanceof JSONArray){out.append('[');JSONArray array=(JSONArray)value;for(int i=0;i<array.length();i++){if(i>0)out.append(',');write(array.opt(i),out,budget,depth+1,limit);}out.append(']');}
    else if(value instanceof String)out.append(JSONObject.quote((String)value));
    else if(value instanceof Boolean)out.append(value);
    else if(value instanceof Number){String number=value.toString();if(!NUMBER.matcher(number).matches())throw invalid();out.append(number);}
    else throw invalid();
    if(out.length()>limit)throw invalid();
  }
  static Object decode(String text,int limit)throws Exception{
    if(text==null||text.length()>limit||text.getBytes(StandardCharsets.UTF_8).length>limit)throw invalid();Reader reader=new Reader(text);Object value=reader.value(0);reader.space();if(reader.at!=text.length())throw invalid();return value;
  }
  static final class Reader {
    final String text;final Budget budget=new Budget();int at;
    Reader(String text){this.text=text;}
    void space(){while(at<text.length()&&" \t\r\n".indexOf(text.charAt(at))>=0)at++;}
    boolean take(char expected){space();if(at<text.length()&&text.charAt(at)==expected){at++;return true;}return false;}
    void require(char expected)throws IOException{if(!take(expected))throw invalid();}
    String string()throws Exception{
      space();int start=at;require('"');boolean ended=false;
      while(at<text.length()){
        char ch=text.charAt(at++);if(ch=='"'){ended=true;break;}if(ch<32)throw invalid();
        if(ch=='\\'){if(at==text.length())throw invalid();char escaped=text.charAt(at++);if(escaped=='u'){for(int i=0;i<4;i++){if(at==text.length()||"0123456789abcdefABCDEF".indexOf(text.charAt(at++))<0)throw invalid();}}else if("\"\\/bfnrt".indexOf(escaped)<0)throw invalid();}
      }
      if(!ended)throw invalid();Object value=new JSONTokener(text.substring(start,at)).nextValue();if(!(value instanceof String))throw invalid();return (String)value;
    }
    Object value(int depth)throws Exception{
      budget.visit(depth);space();if(at==text.length())throw invalid();char ch=text.charAt(at);
      if(ch=='"')return string();
      if(ch=='{'){at++;JSONObject out=new JSONObject();if(take('}'))return out;do{String key=string();if(out.has(key))throw invalid();require(':');out.put(key,value(depth+1));if(take('}'))return out;require(',');}while(true);}
      if(ch=='['){at++;JSONArray out=new JSONArray();if(take(']'))return out;do{out.put(value(depth+1));if(take(']'))return out;require(',');}while(true);}
      int start=at;while(at<text.length()&&",]} \t\r\n".indexOf(text.charAt(at))<0)at++;String token=text.substring(start,at);
      if(token.equals("null"))return JSONObject.NULL;if(token.equals("true"))return true;if(token.equals("false"))return false;
      if(token.length()>1024||!NUMBER.matcher(token).matches())throw invalid();
      if(token.indexOf('.')>=0||token.indexOf('e')>=0||token.indexOf('E')>=0){double number=Double.parseDouble(token);if(!Double.isFinite(number))throw invalid();return number;}
      BigInteger number=new BigInteger(token);return number.bitLength()<64?number.longValue():number;
    }
  }
}
