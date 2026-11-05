package local.pocketchat;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;
import org.json.*;

/** A native BC setting readback is neither a page observation nor worker proof. */
final class GeckoTimeZonePolicy {
  static final int ACK_BYTES=16*1024;
  static JSONObject object(byte[] raw,int limit)throws IOException{
    if(raw==null||raw.length==0||raw.length>limit)throw new IOException("时区记录为空或超出限制，原文件保留");
    try{
      String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
      Object value=NetworkShareJson.decode(text,limit);
      if(!(value instanceof JSONObject))throw new IOException("时区记录必须是 JSON 对象");return (JSONObject)value;
    }catch(IOException invalid){throw invalid;}catch(Exception invalid){throw new IOException("时区记录无法读取，原文件保留",invalid);}
  }
  static JSONObject nativeReadback(String raw,GeckoTimeZoneSpec desired,String requestToken,String sessionId,String contextId)throws IOException{
    if(desired==null||!validContext(contextId))throw new IOException("缺少时区确认目标");
    JSONObject value=contextReadback(raw,requestToken,sessionId);
    if(!desired.zoneId.equals(value.opt("requestedZoneId"))||!desired.zoneId.equals(value.opt("nativeZoneId"))||!contextId.equals(value.opt("contextId")))throw new IOException("原生时区尚未确认，或网页上下文已变化");
    return value;
  }
  /** Bootstrap read identifies the actual native context only. It does not
   * confirm that the desired timezone has been applied. */
  static JSONObject contextReadback(String raw,String requestToken,String sessionId)throws IOException{
    if(raw==null||raw.length()>ACK_BYTES||requestToken==null||!requestToken.matches("[0-9a-f]{64}")||!validSession(sessionId))throw new IOException("尚未收到有效的原生时区确认");
    JSONObject value=object(raw.getBytes(StandardCharsets.UTF_8),ACK_BYTES);
    Set<String> required=new HashSet<>(Arrays.asList("schema","status","requestToken","requestedZoneId","nativeZoneId","sessionId","contextId","nativeSettingReadback","scope","workerCoverageVerified","serviceWorkerCoverageVerified"));
    Set<String> actual=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)actual.add(i.next());
    if(!actual.containsAll(required)||!required.containsAll(actual))throw new IOException("原生时区确认结构不受支持");
    if(integer(value,"schema")!=1||!("applied".equals(value.opt("status"))||"read".equals(value.opt("status")))
        ||!requestToken.equals(value.opt("requestToken"))||!sessionId.equals(value.opt("sessionId"))
        ||!(value.opt("requestedZoneId") instanceof String)||!(value.opt("nativeZoneId") instanceof String)
        ||!validContext(value.opt("contextId") instanceof String?(String)value.opt("contextId"):null)
        ||!Boolean.TRUE.equals(value.opt("nativeSettingReadback"))||!"top-browsing-context".equals(value.opt("scope"))
        ||!Boolean.FALSE.equals(value.opt("workerCoverageVerified"))||!Boolean.FALSE.equals(value.opt("serviceWorkerCoverageVerified")))
      throw new IOException("原生时区尚未确认，或网页上下文已变化");
    return value;
  }
  static boolean validContext(String value){return value!=null&&value.matches("[1-9][0-9]{0,23}");}
  static boolean validSession(String value){return value!=null&&value.matches("[A-Za-z0-9_.:-]{1,160}");}
  static boolean legacySystemMayContinue(GeckoTimeZoneSpec desired){return desired!=null&&desired.followsSystem();}
  static boolean protectionConflict(int protectionLevel,GeckoTimeZoneSpec desired){return protectionLevel>=2&&desired!=null&&!desired.followsSystem();}
  static String nativeScope(){return "原生上下文设置回读；页面、Worker 与 Service Worker 的实际时区需分别观测，强化保护可能采用自己的时区策略。";}
  static long integer(JSONObject value,String key)throws IOException{
    Object raw=value.opt(key);if(!(raw instanceof Integer||raw instanceof Long||raw instanceof Short||raw instanceof Byte))throw new IOException("时区记录整数无效");return ((Number)raw).longValue();
  }
  static void keys(JSONObject value,String... names)throws IOException{
    Set<String> actual=new HashSet<>();for(Iterator<String> i=value.keys();i.hasNext();)actual.add(i.next());
    if(!actual.equals(new HashSet<>(Arrays.asList(names))))throw new IOException("时区记录结构不受支持，原文件保留");
  }
}
