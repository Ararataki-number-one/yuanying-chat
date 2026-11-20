package android.content;

import java.util.LinkedHashMap;
import java.util.Map;

public final class SharedPreferences {
  private final Map<String,Object> values=new LinkedHashMap<>();
  public synchronized boolean contains(String key){return values.containsKey(key);}
  public synchronized boolean getBoolean(String key,boolean fallback){return (Boolean)values.getOrDefault(key,fallback);}
  public synchronized String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}
  public synchronized float getFloat(String key,float fallback){return (Float)values.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor();}
  public final class Editor {
    private final Map<String,Object> pending=new LinkedHashMap<>();
    private boolean reset;
    public Editor clear(){reset=true;return this;}
    public Editor putString(String key,String value){pending.put(key,value);return this;}
    public Editor putBoolean(String key,boolean value){pending.put(key,value);return this;}
    public Editor putInt(String key,int value){pending.put(key,value);return this;}
    public Editor putFloat(String key,float value){pending.put(key,value);return this;}
    public boolean commit(){
      synchronized(SharedPreferences.this){if(reset)values.clear();values.putAll(pending);}
      return true;
    }
  }
}
