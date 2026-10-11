package local.pocketchat;

import java.io.File;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import java.util.concurrent.Executor;
import java.util.function.Supplier;

/** File-backed metadata snapshots. UI reads never stat, decrypt, or wait for a reader. */
final class FileSnapshotCache<T> {
  interface Loader<T>{T load()throws Exception;}
  final Executor worker;final Supplier<T> empty;final Map<String,Entry<T>> entries=new HashMap<>();
  static final long CHECK_INTERVAL=1000;
  static final class Entry<T>{
    volatile T value;volatile boolean initialized,queued;volatile long checkedAt;long version;
    final Object loadLock=new Object();Signature signature;
    Entry(T value){this.value=value;}
  }
  static final class Signature {
    final Object key;final java.nio.file.attribute.FileTime modified;final long size;
    Signature(BasicFileAttributes a){key=a.fileKey();modified=a.lastModifiedTime();size=a.size();}
    @Override public boolean equals(Object value){if(!(value instanceof Signature))return false;Signature s=(Signature)value;return size==s.size&&Objects.equals(key,s.key)&&modified.equals(s.modified);}
    @Override public int hashCode(){return Objects.hash(key,modified,size);}
  }
  FileSnapshotCache(Executor worker,Supplier<T> empty){this.worker=worker;this.empty=empty;}
  synchronized Entry<T> entry(File file){return entries.computeIfAbsent(file.getAbsolutePath(),key->new Entry<>(empty.get()));}
  boolean ready(File file){return entry(file).initialized;}
  T read(File file,boolean asynchronous,Loader<T> loader,Runnable changed){
    Entry<T> entry=entry(file);
    if(!asynchronous){load(file,entry,loader,changed);return entry.value;}
    long now=System.nanoTime()/1000000;
    synchronized(entry){if(!entry.queued&&(!entry.initialized||now-entry.checkedAt>=CHECK_INTERVAL)){entry.queued=true;worker.execute(()->{try{load(file,entry,loader,changed);}finally{synchronized(entry){entry.queued=false;}}});}}
    return entry.value;
  }
  static Signature signature(File file)throws Exception{try{return new Signature(Files.readAttributes(file.toPath(),BasicFileAttributes.class));}catch(NoSuchFileException absent){return null;}}
  void load(File file,Entry<T> entry,Loader<T> loader,Runnable changed){
    synchronized(entry.loadLock){
      final long version; synchronized(entry){version=entry.version;}
      try{
        Signature before=signature(file);
        if(entry.initialized&&Objects.equals(before,entry.signature)){entry.checkedAt=System.nanoTime()/1000000;return;}
        T next=before==null?empty.get():loader.load();Signature after=signature(file);
        // Atomic replacement during decryption is retried on the next read; never publish mixed evidence.
        if(!Objects.equals(before,after))return;
        boolean notify;
        synchronized(entry){if(version!=entry.version)return;notify=!entry.initialized||!Objects.equals(after,entry.signature);entry.value=next==null?empty.get():next;entry.signature=after;entry.initialized=true;entry.checkedAt=System.nanoTime()/1000000;}
        if(notify&&changed!=null)changed.run();
      }catch(Exception unavailable){
        // An unreadable replacement must not keep presenting an old file's region or response time.
        Signature unreadable=null;try{unreadable=signature(file);}catch(Exception ignored){}
        synchronized(entry){if(version!=entry.version)return;entry.value=empty.get();entry.signature=unreadable;entry.initialized=true;entry.checkedAt=System.nanoTime()/1000000;}
        if(changed!=null)changed.run();
      }
    }
  }
  /** Called after a successful background write, so an older queued read cannot overwrite it. */
  void publish(File file,T value){
    Entry<T> entry=entry(file);Signature signature=null;try{signature=signature(file);}catch(Exception ignored){}
    synchronized(entry){entry.version++;entry.value=value;entry.signature=signature;entry.initialized=true;entry.checkedAt=System.nanoTime()/1000000;}
  }
}
