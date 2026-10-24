package android.content;
/** Profile-local, in-memory preference lookup; no Android storage claim. */
public class Context {
  private final java.util.Map<String,SharedPreferences> values=new java.util.HashMap<>();
  public SharedPreferences getSharedPreferences(String name,int mode){return values.computeIfAbsent(name,key->new SharedPreferences());}
}
