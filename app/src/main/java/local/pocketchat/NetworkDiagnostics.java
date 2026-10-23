package local.pocketchat;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

/** Bounded local events. Arbitrary text, exceptions and core output never enter the journal. */
final class NetworkDiagnostics {
  enum Source { CONTROL, SERVICE, PREVIEW }
  enum Event { CORE_START, CORE_STARTED, CORE_EXIT, CORE_OUTPUT, STOP_REQUEST, STOP_FORCED,
    RECONNECT_ATTEMPT, CANDIDATE_FAILURE, ROLLBACK, FAILURE, SERVICE_AVAILABLE, SERVICE_DESTROY,
    IPC_CONNECTED, IPC_DISCONNECTED, IPC_BINDING_DIED, IPC_NULL_BINDING, IPC_BIND_REJECTED,
    IPC_BIND_EXCEPTION, IPC_BIND_TIMEOUT, IPC_BIND_INTERRUPTED, IPC_FOREGROUND_REJECTED, IPC_SEND_FAILED,
    IPC_REPLY_TIMEOUT, IPC_REPLY_FAILED, IPC_REPLY_INTERRUPTED, IPC_REMOTE_REJECTED, IPC_REPLY_SEND_FAILED,
    IPC_EVENT_SEND_FAILED, IPC_DETACH, DROPPED }
  enum Reason { UNKNOWN, REQUESTED, REPLACE, HEALTH_FAILED, EXIT_MISMATCH, ROLLBACK_FAILED,
    SERVICE_DESTROY, START_FAILED, CORE_EXITED, CANCELLED, DETECTOR_UNAVAILABLE,
    CANDIDATE_UNAVAILABLE, CONTROL_UNAVAILABLE, PREVIEW_FINISHED }
  enum Stage { CORE, IPC, VERIFY, PROBE, SELECT, RECOVER, START, STOP, BIND, SEND, REPLY, OUTPUT }
  static final int MAX_EVENTS=128,MAX_BYTES=65536,MAX_PENDING=64;
  static final String UNKNOWN="unknown",HEADER="PocketChat network events v1\n";
  static final AtomicLong dropped=new AtomicLong();
  private static final ThreadPoolExecutor writer=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,
      new ArrayBlockingQueue<Runnable>(MAX_PENDING),r->{Thread t=new Thread(r,"network-diagnostics");t.setDaemon(true);return t;},
      (r,e)->dropped.incrementAndGet());
  private static final LinkedHashMap<String,Journal> journals=new LinkedHashMap<String,Journal>(32,.75f,true){
    protected boolean removeEldestEntry(Map.Entry<String,Journal> entry){return size()>32;}
  };
  static final class Identity {
    final String id;final long generation;
    Identity(String id,long generation){this.id=safeUuid(id);this.generation=generation;
      if(UNKNOWN.equals(this.id)||generation<0)throw new IllegalArgumentException("Invalid diagnostic identity");}
  }
  static final class Scope {final File directory;final Identity identity;Scope(File directory,Identity identity){this.directory=directory;this.identity=identity;}}
  final int slot;final Source source;final String owner=UUID.randomUUID().toString();private volatile Scope scope;
  private NetworkDiagnostics(int slot,Source source){
    if(slot<0||slot>=8||source==null)throw new IllegalArgumentException("Invalid diagnostic scope");
    this.slot=slot;this.source=source;
  }
  static NetworkDiagnostics forRoot(File directory,int slot,Source source,String environmentId,long environmentGeneration){
    NetworkDiagnostics result=new NetworkDiagnostics(slot,source);result.bind(directory,environmentId,environmentGeneration);return result;
  }
  static NetworkDiagnostics unbound(int slot,Source source){return new NetworkDiagnostics(slot,source);}
  boolean bound(){return scope!=null;}
  synchronized boolean bind(File directory,String environmentId,long environmentGeneration){
    if(directory==null)return false;Identity identity=new Identity(environmentId,environmentGeneration);
    if(scope!=null)return scope.identity.id.equals(identity.id)&&scope.identity.generation==identity.generation;
    scope=new Scope(directory,identity);return true;
  }
  static String safeUuid(String value){
    if(value==null||value.length()!=36)return UNKNOWN;
    try{String normalized=UUID.fromString(value).toString();return normalized.equals(value)?normalized:UNKNOWN;}
    catch(IllegalArgumentException invalid){return UNKNOWN;}
  }
  static Reason reason(String value){try{return Reason.valueOf(value);}catch(Exception invalid){return Reason.UNKNOWN;}}
  void record(Event event,String coreGeneration,Reason reason,Stage stage,long value){
    Scope captured=scope;if(captured==null||event==null||reason==null||stage==null)return;
    // Capture only validated fields before crossing the bounded queue.
    final String core=safeUuid(coreGeneration);final long wall=System.currentTimeMillis(),mono=System.nanoTime()/1000000L;
    writer.execute(()->{
      try{
        File file=new File(captured.directory,source.name().toLowerCase(Locale.ROOT)+".events");
        String key=file.getAbsolutePath();Journal journal=journals.get(key);
        if(journal==null){journal=new Journal(file,slot,source);journals.put(key,journal);}
        long omitted=dropped.getAndSet(0);
        if(omitted>0)journal.add(row(captured,wall,mono,core,Event.DROPPED,Reason.UNKNOWN,Stage.IPC,omitted));
        journal.add(row(captured,wall,mono,core,event,reason,stage,value));journal.write();
      }catch(Exception unavailable){/* Diagnostics never change network behavior or expose an exception. */}
    });
  }
  private String row(Scope captured,long wall,long mono,String core,Event event,Reason reason,Stage stage,long value){
    return wall+"\t"+mono+"\t"+slot+"\t"+source+"\t"+owner+"\t"+captured.identity.id+"\t"+captured.identity.generation
      +"\t"+core+"\t"+event+"\t"+reason+"\t"+stage+"\t"+value;
  }
  /** A drain thread counts output without passing even a single byte of its contents. */
  Output output(String coreGeneration){return new Output(this,safeUuid(coreGeneration));}
  static final class Output implements AutoCloseable {
    final NetworkDiagnostics diagnostics;final String generation;long bytes;boolean closed;
    Output(NetworkDiagnostics diagnostics,String generation){this.diagnostics=diagnostics;this.generation=generation;}
    void add(int count){if(count>0&&!closed)bytes=bytes>Long.MAX_VALUE-count?Long.MAX_VALUE:bytes+count;}
    public void close(){if(!closed){closed=true;diagnostics.record(Event.CORE_OUTPUT,generation,Reason.UNKNOWN,Stage.OUTPUT,bytes);}}
  }
  private static boolean valid(String line,int slot,Source source){
    if(line.length()>512)return false;String[] p=line.split("\t",-1);if(p.length!=12)return false;
    try{return Long.parseLong(p[0])>=0&&Long.toString(Long.parseLong(p[1])).equals(p[1])&&Integer.parseInt(p[2])==slot
      &&Source.valueOf(p[3])==source&&!UNKNOWN.equals(safeUuid(p[4]))&&!UNKNOWN.equals(safeUuid(p[5]))
      &&Long.parseLong(p[6])>=0&&(UNKNOWN.equals(p[7])||!UNKNOWN.equals(safeUuid(p[7])))
      &&Event.valueOf(p[8])!=null&&Reason.valueOf(p[9])!=null&&Stage.valueOf(p[10])!=null
      &&Long.toString(Long.parseLong(p[11])).equals(p[11]);}catch(Exception invalid){return false;}
  }
  private static List<String> read(File file,int slot,Source source)throws IOException{
    if(!file.isFile())return Collections.emptyList();
    try(InputStream in=new FileInputStream(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
      byte[] buffer=new byte[4096];int count,total=0;
      while((count=in.read(buffer))!=-1){total+=count;if(total>MAX_BYTES)return Collections.emptyList();bytes.write(buffer,0,count);}
      String text=new String(bytes.toByteArray(),StandardCharsets.UTF_8);if(!text.startsWith(HEADER))return Collections.emptyList();
      List<String> result=new ArrayList<>();for(String line:text.substring(HEADER.length()).split("\n"))if(valid(line,slot,source))result.add(line);
      return result.size()<=MAX_EVENTS?result:result.subList(result.size()-MAX_EVENTS,result.size());
    }
  }
  private static final class Journal {
    final File file;final ArrayDeque<String> rows=new ArrayDeque<>();int bytes=HEADER.length();
    Journal(File file,int slot,Source source)throws IOException{this.file=file;for(String line:read(file,slot,source))add(line);}
    void add(String line){rows.addLast(line);bytes+=line.length()+1;while(rows.size()>MAX_EVENTS||bytes>MAX_BYTES){bytes-=rows.removeFirst().length()+1;}}
    void write()throws IOException{
      File directory=file.getParentFile();if(!directory.isDirectory()&&!directory.mkdirs())return;
      File temporary=new File(directory,file.getName()+".new");
      try(OutputStream out=new FileOutputStream(temporary)){out.write(HEADER.getBytes(StandardCharsets.US_ASCII));for(String row:rows){out.write(row.getBytes(StandardCharsets.US_ASCII));out.write('\n');}}
      try{Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
      catch(AtomicMoveNotSupportedException unsupported){Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING);}
    }
  }
  /** Call off the Android main thread. Revalidates stored data and filters reused slots. */
  static String readSummary(File directory,int slot,String environmentId,long environmentGeneration){
    final Identity wanted;try{wanted=new Identity(environmentId,environmentGeneration);}catch(Exception invalid){return "网络事件：环境身份暂不可用";}
    List<String> rows=new ArrayList<>();for(Source source:Source.values())try{
      for(String row:read(new File(directory,source.name().toLowerCase(Locale.ROOT)+".events"),slot,source)){
        String[] p=row.split("\t",-1);if(wanted.id.equals(p[5])&&wanted.generation==Long.parseLong(p[6]))rows.add(row);
      }
    }catch(IOException unavailable){}
    rows.sort(Comparator.comparingLong(row->Long.parseLong(row.substring(0,row.indexOf('\t')))));
    StringBuilder out=new StringBuilder("网络事件 · 环境编号：").append(slot+1).append("\n环境 ID：").append(wanted.id)
      .append(" · 环境代次：").append(wanted.generation).append("\n仅固定事件与数值；不包含核心输出原文。\n")
      .append("字段：时间毫秒 / 单调时间 / 内部槽位 / 来源 / 记录器代次 / 环境 ID / 环境代次 / 核心代次 / 事件 / 原因 / 阶段 / 数值\n");
    int first=Math.max(0,rows.size()-MAX_EVENTS);for(int i=first;i<rows.size();i++)out.append(rows.get(i)).append('\n');
    if(rows.isEmpty())out.append("暂无事件记录\n");return out.toString();
  }
  static boolean flushForTest(long timeoutMillis)throws InterruptedException{
    long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMillis);CountDownLatch done=new CountDownLatch(1);writer.prestartCoreThread();
    if(!writer.getQueue().offer(done::countDown,timeoutMillis,TimeUnit.MILLISECONDS))return false;
    return done.await(Math.max(0,deadline-System.nanoTime()),TimeUnit.NANOSECONDS);
  }
}
