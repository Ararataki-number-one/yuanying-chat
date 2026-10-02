package local.pocketchat;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
final class J {
  static JSONObject obj(Object... values){JSONObject o=new JSONObject();try{for(int i=0;i<values.length;i+=2)o.put((String)values[i],values[i+1]);}catch(JSONException e){throw new IllegalArgumentException(e);}return o;}
  static JSONArray arr(Object... values){JSONArray a=new JSONArray();for(Object v:values)a.put(v);return a;}
  static JSONObject parse(String s){try{return new JSONObject(s);}catch(Exception e){return new JSONObject();}}
  static byte[] read(InputStream in,int max)throws IOException{ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] buf=new byte[8192];int n;while((n=in.read(buf))>0){if(b.size()+n>max)throw new IOException("文件过大");b.write(buf,0,n);}return b.toByteArray();}
  static String text(InputStream in,int max)throws IOException{return new String(read(in,max),StandardCharsets.UTF_8);}
  static void write(File file,String text)throws IOException{try(FileOutputStream out=new FileOutputStream(file)){out.write(text.getBytes(StandardCharsets.UTF_8));out.getFD().sync();}}
}
