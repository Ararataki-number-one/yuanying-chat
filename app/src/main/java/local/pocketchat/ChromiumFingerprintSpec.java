package local.pocketchat;

import java.util.*;
import org.json.*;

/** Requested Chromium controls; never an acknowledgement of page or worker coverage. */
final class ChromiumFingerprintSpec {
  static final int SCHEMA=1;
  static final Set<String> FIELDS=Collections.unmodifiableSet(new HashSet<>(Arrays.asList("schema","engine","display","protection","canvas","webgl","audio","webrtc","workers")));
  final String display,protection,workers;
  final boolean canvas,webgl,audio,webrtc;
  private ChromiumFingerprintSpec(String display,String protection,boolean canvas,boolean webgl,boolean audio,boolean webrtc,String workers){this.display=display;this.protection=protection;this.canvas=canvas;this.webgl=webgl;this.audio=audio;this.webrtc=webrtc;this.workers=workers;}
  static ChromiumFingerprintSpec defaults(){return from(new JSONObject());}
  static ChromiumFingerprintSpec fromJSONObject(JSONObject value){return from(value);}
  static ChromiumFingerprintSpec from(JSONObject value){
    if(value==null)throw new IllegalArgumentException("Chromium 指纹配置不能为空");
    for(Iterator<String> keys=value.keys();keys.hasNext();)if(!FIELDS.contains(keys.next()))throw new IllegalArgumentException("当前 Chromium 不支持此指纹字段；不提供语言、时区、硬件或字体伪装");
    Object schema=value.opt("schema");if(schema!=null&&(!(schema instanceof Integer||schema instanceof Long)||((Number)schema).longValue()!=SCHEMA))throw new IllegalArgumentException("不支持此 Chromium 指纹配置版本");
    String engine=string(value,"engine","chromium"),display=string(value,"display","mobile"),protection=string(value,"protection","protected");
    if(!"chromium".equals(engine))throw new IllegalArgumentException("此配置仅用于 Chromium 内核");
    if(!"mobile".equals(display)&&!"desktop".equals(display))throw new IllegalArgumentException("请选择 Chromium 手机版或请求桌面版");
    if(!"protected".equals(protection)&&!"compatibility".equals(protection))throw new IllegalArgumentException("请选择 Chromium 页面保护或兼容模式");
    String workers=string(value,"workers","allow");if(!"allow".equals(workers)&&!"restrict".equals(workers))throw new IllegalArgumentException("请选择允许 Worker 或限制新建与后台联网");
    boolean enabled="protected".equals(protection);
    return new ChromiumFingerprintSpec(display,protection,bool(value,"canvas",enabled),bool(value,"webgl",enabled),bool(value,"audio",enabled),bool(value,"webrtc",enabled),workers);
  }
  static String string(JSONObject value,String name,String fallback){Object selected=value.opt(name);if(selected==null&&!value.has(name))return fallback;if(!(selected instanceof String))throw new IllegalArgumentException("Chromium "+name+" 必须是文字");return (String)selected;}
  static boolean bool(JSONObject value,String name,boolean fallback){Object selected=value.opt(name);if(selected==null&&!value.has(name))return fallback;if(!(selected instanceof Boolean))throw new IllegalArgumentException("Chromium "+name+" 必须是开关");return (Boolean)selected;}
  boolean desktop(){return "desktop".equals(display);}
  boolean protectedMode(){return "protected".equals(protection);}
  boolean restrictWorkers(){return "restrict".equals(workers);}
  boolean scriptsRequired(){return protectedMode()||canvas||webgl||audio||webrtc||restrictWorkers();}
  JSONObject json(){return J.obj("schema",SCHEMA,"engine","chromium","display",display,"protection",protection,"canvas",canvas,"webgl",webgl,"audio",audio,"webrtc",webrtc,"workers",workers);}
}
