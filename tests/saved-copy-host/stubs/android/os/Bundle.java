package android.os;

public final class Bundle {
  private final java.util.Map<String,Object> values=new java.util.HashMap<>();
  public void putBundle(String key,Bundle value){values.put(key,value);}
  public Bundle getBundle(String key){return (Bundle)values.get(key);}
  public void putString(String key,String value){values.put(key,value);}
  public String getString(String key){return (String)values.get(key);}
  public void putInt(String key,int value){values.put(key,value);}
  public int getInt(String key,int fallback){return ((Integer)values.getOrDefault(key,fallback)).intValue();}
  public void putLong(String key,long value){values.put(key,value);}
  public long getLong(String key,long fallback){return ((Long)values.getOrDefault(key,fallback)).longValue();}
}
