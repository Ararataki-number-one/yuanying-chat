package android.content;
import java.util.concurrent.ConcurrentHashMap;
public final class SharedPreferences {
  public final ConcurrentHashMap<String,Object> values=new ConcurrentHashMap<>();
  public String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}
  public boolean getBoolean(String key,boolean fallback){return (Boolean)values.getOrDefault(key,fallback);}
}
