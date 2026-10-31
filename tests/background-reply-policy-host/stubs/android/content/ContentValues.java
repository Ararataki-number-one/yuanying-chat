package android.content;
public class ContentValues extends java.util.LinkedHashMap<String,Object> {
  public void put(String key,String value){super.put(key,value);}
  public void put(String key,Integer value){super.put(key,value);}
  public void put(String key,Long value){super.put(key,value);}
}
