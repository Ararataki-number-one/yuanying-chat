package android.content;
import java.io.*;import java.util.*;
/** Explicit host model: commit may change memory and still fail before disk. */
public final class SharedPreferences {
 public volatile boolean failNextCommit,failAfterMemoryBeforeDisk;
 public volatile int commitAttempts;
 final File file;final Map<String,String> memory=new HashMap<>(),disk=new HashMap<>();
 public SharedPreferences(File file){this.file=file;Properties values=new Properties();if(file.isFile())try(InputStream in=new FileInputStream(file)){values.load(in);}catch(IOException error){throw new IllegalStateException(error);}for(String key:values.stringPropertyNames())disk.put(key,values.getProperty(key));memory.putAll(disk);}
 public synchronized String getString(String key,String fallback){return memory.getOrDefault(key,fallback);}
 public synchronized String diskString(String key,String fallback){return disk.getOrDefault(key,fallback);}
 public Editor edit(){return new Editor();}
 public final class Editor {
  final Map<String,String> changes=new HashMap<>();public Editor putString(String key,String value){changes.put(key,value);return this;}
  public boolean commit(){synchronized(SharedPreferences.this){commitAttempts++;if(failNextCommit){failNextCommit=false;return false;}memory.putAll(changes);if(failAfterMemoryBeforeDisk){failAfterMemoryBeforeDisk=false;return false;}Properties values=new Properties();values.putAll(memory);try(OutputStream out=new FileOutputStream(file)){values.store(out,"host preferences model");}catch(IOException error){return false;}disk.clear();disk.putAll(memory);return true;}}
  public void apply(){commit();}
 }
}
