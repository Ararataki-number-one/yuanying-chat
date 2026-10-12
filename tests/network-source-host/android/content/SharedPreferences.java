package android.content;
import java.util.*;
public final class SharedPreferences {final Map<String,Object> values=new HashMap<>();public String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}public boolean getBoolean(String key,boolean fallback){return (Boolean)values.getOrDefault(key,fallback);}}
