package android.content;

import java.util.*;

public final class Intent {
  public static final int FLAG_ACTIVITY_NEW_TASK=0x10000000,FLAG_ACTIVITY_REORDER_TO_FRONT=0x00020000;
  public final Context caller;public final Class<?> target;public int flags;
  public final Map<String,Object> extras=new HashMap<>();
  public Intent(Context caller,Class<?> target){this.caller=caller;this.target=target;}
  public Intent putExtra(String key,String value){extras.put(key,value);return this;}
  public Intent putExtra(String key,boolean value){extras.put(key,value);return this;}
  public Intent addFlags(int value){flags|=value;return this;}
}
