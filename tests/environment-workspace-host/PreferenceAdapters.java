package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.*;

/** In-memory adapter models only the SharedPreferences calls the real store uses. */
final class PreferenceAdapters {
  static final class MemoryContext extends Context {
    final MemoryContext global;
    final Map<String,MemoryPreferences> files=new HashMap<>();
    MemoryContext(){global=this;}
    MemoryContext(MemoryContext global){this.global=global;}
    @Override public MemoryPreferences getSharedPreferences(String name,int mode){
      if(mode!=0)throw new AssertionError("private preference mode required");
      return files.computeIfAbsent(name,key->new MemoryPreferences());
    }
  }
  static final class MemoryPreferences implements SharedPreferences {
    final Map<String,String> values=new HashMap<>();boolean failNextCommit;
    @Override public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}
    @Override public Editor edit(){return new Editor(){
      final Map<String,String> staged=new HashMap<>();
      public Editor putString(String key,String value){staged.put(key,value);return this;}
      public boolean commit(){
        if(failNextCommit){failNextCommit=false;return false;}
        values.putAll(staged);return true;
      }
      public void apply(){values.putAll(staged);}
    };}
  }
}
final class Profiles {
  static final int MAX=8;
  static final Class<?>[] TARGETS={Target0.class,Target1.class,Target2.class,Target3.class,Target4.class,Target5.class,Target6.class,Target7.class};
  static Context global(Context context){return ((PreferenceAdapters.MemoryContext)context).global;}
  static Class<?> activity(int slot){return TARGETS[slot];}
  static final class Target0{}static final class Target1{}static final class Target2{}static final class Target3{}
  static final class Target4{}static final class Target5{}static final class Target6{}static final class Target7{}
}
