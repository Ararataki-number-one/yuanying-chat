package android.content;
import java.util.*;
public final class Intent {
  public String action,packageName;public Class<?> target;public final Map<String,Long> extras=new LinkedHashMap<>();
  public Intent(String action){this.action=action;}
  public Intent(Context context,Class<?> target){this.target=target;}
  public String getAction(){return action;}
  public Intent setPackage(String value){packageName=value;return this;}
  public Intent putExtra(String name,long value){extras.put(name,value);return this;}
  public long getLongExtra(String name,long fallback){return extras.getOrDefault(name,fallback);}
}
