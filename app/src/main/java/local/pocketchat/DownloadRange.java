package local.pocketchat;
import java.net.*;import java.io.*;import java.util.regex.*;

/** Append only after a matching resource validator and exact Content-Range. */
final class DownloadRange {
 static String resource(String url){try{return android.util.Base64.encodeToString(java.security.MessageDigest.getInstance("SHA-256").digest(url.getBytes(java.nio.charset.StandardCharsets.UTF_8)),android.util.Base64.NO_WRAP);}catch(Exception e){return "";}}
 static String validator(String etag,String modified){return etag!=null&&!etag.isEmpty()&&!etag.startsWith("W/")?etag:modified==null?"":modified;}
 static long total(HttpURLConnection c,long offset,String expected)throws IOException {
  int code=c.getResponseCode();if(code==200)return c.getContentLengthLong();
  if(code!=206)throw new IOException("下载响应不支持续传（HTTP "+code+"）");
  String current=validator(c.getHeaderField("ETag"),c.getHeaderField("Last-Modified"));
  if(offset<=0||expected.isEmpty()||!expected.equals(current))throw new IOException("文件版本已改变，需重新下载");
  Matcher m=Pattern.compile("bytes (\\d+)-(\\d+)/(\\d+)").matcher(String.valueOf(c.getHeaderField("Content-Range")));
  if(!m.matches())throw new IOException("续传范围无效，需重新下载");
  try{long start=Long.parseLong(m.group(1)),end=Long.parseLong(m.group(2)),total=Long.parseLong(m.group(3)),length=c.getContentLengthLong();if(start!=offset||end<start||end>=total||(length>=0&&length!=end-start+1))throw new IOException("续传范围不匹配，需重新下载");return total;}catch(NumberFormatException e){throw new IOException("续传范围无效");}
 }
}
