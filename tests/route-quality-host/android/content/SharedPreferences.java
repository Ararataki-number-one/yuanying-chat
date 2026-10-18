package android.content;
import java.util.*;
public final class SharedPreferences {
  private final Map<String,Object> data=new HashMap<>();
  public String getString(String k,String fallback){return (String)data.getOrDefault(k,fallback);}
  public int getInt(String k,int fallback){return (Integer)data.getOrDefault(k,fallback);}
  public long getLong(String k,long fallback){return (Long)data.getOrDefault(k,fallback);}
  public Editor edit(){return new Editor();}
  public final class Editor {
    private final Map<String,Object> pending=new HashMap<>();
    public Editor putString(String k,String v){pending.put(k,v);return this;}
    public Editor putLong(String k,long v){pending.put(k,v);return this;}
    public Editor putInt(String k,int v){pending.put(k,v);return this;}
    public void apply(){data.putAll(pending);}
  }
}
