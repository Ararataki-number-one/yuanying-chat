package android.content;
import java.util.*;
public class Context {
  public final Map<String,Object> preferences=new HashMap<>();
  public final List<Map<String,Object>> conversations=new ArrayList<>(),archives=new ArrayList<>();
  public int writeCalls;
  public SharedPreferences getSharedPreferences(String name,int mode){return new SharedPreferences(preferences);}
}
