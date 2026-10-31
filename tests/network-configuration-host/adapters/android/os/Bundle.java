package android.os;
import java.util.*;
public final class Bundle {
 final Map<String,Object> fields=new HashMap<>();
 public void putString(String key,String value){fields.put(key,value);}public String getString(String key,String fallback){Object value=fields.get(key);return value instanceof String?(String)value:fallback;}
 public void putBoolean(String key,boolean value){fields.put(key,value);}public boolean getBoolean(String key,boolean fallback){Object value=fields.get(key);return value instanceof Boolean?(Boolean)value:fallback;}
}
