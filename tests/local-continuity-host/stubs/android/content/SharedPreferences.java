package android.content;
import java.util.*;
public class SharedPreferences {
  final Map<String,Object> values;SharedPreferences(Map<String,Object> values){this.values=values;}
  public String getString(String key,String fallback){Object value=values.get(key);return value instanceof String?(String)value:fallback;}
  public Map<String,?> getAll(){return new HashMap<>(values);}
}
