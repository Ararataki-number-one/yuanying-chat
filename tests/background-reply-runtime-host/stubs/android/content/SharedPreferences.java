package android.content;
import java.util.*;
public interface SharedPreferences {
  Editor edit();
  interface Editor {Editor putBoolean(String name,boolean value);boolean commit();}
  final class Memory implements SharedPreferences {
    public final Map<String,Object> values=new LinkedHashMap<>();
    public boolean commitSucceeds=true;public int edits,commits;
    public Editor edit(){edits++;return new Editor(){final Map<String,Object> pending=new LinkedHashMap<>();public Editor putBoolean(String name,boolean value){pending.put(name,value);return this;}public boolean commit(){commits++;if(!commitSucceeds)return false;values.putAll(pending);return true;}};}
  }
}
