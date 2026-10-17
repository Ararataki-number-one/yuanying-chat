package local.pocketchat;
import org.json.*;
/** Host-only JSON helper; production J also depends on Android file/network APIs. */
final class J{static JSONObject obj(Object... pairs){JSONObject value=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);}catch(JSONException error){throw new IllegalArgumentException(error);}return value;}}
