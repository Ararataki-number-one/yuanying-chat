package android.content;
import java.util.*;
/** In-memory persistence only; does not claim Android execution. */
public final class Context {
  private final Map<String,SharedPreferences> stores=new HashMap<>();
  public SharedPreferences getSharedPreferences(String name,int mode){return stores.computeIfAbsent(name,key->new SharedPreferences());}
}
