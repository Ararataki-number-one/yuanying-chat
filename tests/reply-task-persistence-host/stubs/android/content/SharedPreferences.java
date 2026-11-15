package android.content;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Separate cached/durable values. commit(false) can still change memory and notify. */
public final class SharedPreferences {
  public enum Failure { NONE, BEFORE_MEMORY, AFTER_MEMORY, THROW_AFTER_MEMORY }
  public Failure nextFailure=Failure.NONE;
  public Runnable onCommit;
  public int commits;
  public final Map<String,String> memory=new LinkedHashMap<>(),disk=new LinkedHashMap<>();
  final Path file;
  SharedPreferences(Path file)throws IOException{
    this.file=file;
    if(Files.exists(file))try{JSONObject saved=new JSONObject(Files.readString(file));for(Iterator<String> keys=saved.keys();keys.hasNext();){String key=keys.next();disk.put(key,saved.getString(key));}}catch(JSONException error){throw new IOException(error);}
    memory.putAll(disk);
  }
  public String getString(String key,String fallback){return memory.getOrDefault(key,fallback);}
  public String diskString(String key,String fallback){return disk.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor();}
  public final class Editor {
    final Map<String,String> writes=new LinkedHashMap<>();final Set<String> removes=new HashSet<>();
    public Editor putString(String key,String value){writes.put(key,value);removes.remove(key);return this;}
    public Editor remove(String key){removes.add(key);writes.remove(key);return this;}
    public boolean commit(){
      commits++;Failure failure=nextFailure;nextFailure=Failure.NONE;
      if(failure==Failure.BEFORE_MEMORY)return false;
      for(String key:removes)memory.remove(key);memory.putAll(writes);
      if(failure==Failure.NONE){try{Files.writeString(file,new JSONObject(memory).toString());disk.clear();disk.putAll(memory);}catch(IOException error){throw new IllegalStateException(error);}}
      Runnable listener=onCommit;onCommit=null;if(listener!=null)listener.run();
      if(failure==Failure.THROW_AFTER_MEMORY)throw new IllegalStateException("Controlled preferences storage exception");
      return failure==Failure.NONE;
    }
    public void apply(){commit();}
  }
}
