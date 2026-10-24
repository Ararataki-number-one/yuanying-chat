package android.content;
/** Immediate in-memory adapter used only by exact AppPrefs and LocalDraftPolicy. */
public class SharedPreferences {
  private final java.util.Map<String,Object> values=new java.util.HashMap<>();
  public boolean getBoolean(String key,boolean fallback){Object value=values.get(key);return value instanceof Boolean?(Boolean)value:fallback;}
  public long getLong(String key,long fallback){Object value=values.get(key);return value instanceof Number?((Number)value).longValue():fallback;}
  public String getString(String key,String fallback){Object value=values.get(key);return value instanceof String?(String)value:fallback;}
  public Editor edit(){return new Editor();}
  public final class Editor {
    private final java.util.Map<String,Object> pending=new java.util.HashMap<>();
    public Editor putBoolean(String key,boolean value){pending.put(key,value);return this;}
    public Editor putLong(String key,long value){pending.put(key,value);return this;}
    public Editor putString(String key,String value){pending.put(key,value);return this;}
    public boolean commit(){values.putAll(pending);return true;}
  }
}
