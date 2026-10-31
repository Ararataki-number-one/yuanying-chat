package android.content;
import java.util.*;
public final class Context {
 public Object identity,model;public String pending="{}",hash="active",mode="internal",storeFailure="";public boolean cacheValid=true;public int pendingReads;
 public final Map<String,byte[]> records=new LinkedHashMap<>();public final Object monitor=new Object();
 public Prefs getSharedPreferences(String ignored,int mode){return new Prefs();}
 public final class Prefs{public String getString(String key,String fallback){return "networkMode".equals(key)?Context.this.mode:fallback;}}
}
