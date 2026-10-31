package android.database.sqlite;

import android.content.ContentValues;
import android.database.Cursor;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/** Synthetic in-memory transaction adapter. This is not Android or real SQLite. */
public final class SQLiteDatabase {
  public static final int CONFLICT_REPLACE=5;
  private final ReentrantLock writer=new ReentrantLock(true);
  private final ArrayDeque<Boolean> successful=new ArrayDeque<>();
  private LinkedHashMap<String,String> settings=new LinkedHashMap<>(),before;
  private boolean nestedFailed;
  public volatile String failWriteKey;
  public volatile boolean failQuery;
  public volatile Runnable beforeBegin,beforeWrite;
  public int begins,ends,writeAttempts,queries;

  public void beginTransaction(){
    Runnable hook=beforeBegin;if(hook!=null)hook.run();writer.lock();
    begins++;
    if(successful.isEmpty()){before=new LinkedHashMap<>(settings);nestedFailed=false;}
    successful.push(false);
  }
  public void setTransactionSuccessful(){
    if(!writer.isHeldByCurrentThread()||successful.isEmpty()||successful.peek())throw new IllegalStateException("Invalid transaction state");
    successful.pop();successful.push(true);
  }
  public void endTransaction(){
    if(!writer.isHeldByCurrentThread()||successful.isEmpty())throw new IllegalStateException("No owned transaction");
    if(!successful.pop())nestedFailed=true;
    if(successful.isEmpty()){if(nestedFailed)settings=before;before=null;}
    ends++;writer.unlock();
  }
  public long insertWithOnConflict(String table,String nullColumn,ContentValues values,int conflict){
    writer.lock();try{
      if(!"app_settings".equals(table)||conflict!=CONFLICT_REPLACE)throw new AssertionError("Unexpected write shape");
      writeAttempts++;Runnable hook=beforeWrite;if(hook!=null)hook.run();
      String key=(String)values.get("name");if(key.equals(failWriteKey))return -1;
      settings.put(key,(String)values.get("value"));return 1;
    }finally{writer.unlock();}
  }
  public Cursor query(String table,String[] columns,String selection,String[] arguments,String groupBy,String having,String orderBy){
    writer.lock();try{
      queries++;if(failQuery)throw new IllegalStateException("Injected synthetic query failure");
      if(!"app_settings".equals(table)||!("name=?".equals(selection)||"name IN (?,?,?,?)".equals(selection)))throw new AssertionError("Unexpected query shape");
      List<String[]> rows=new ArrayList<>();
      for(String key:arguments)if(settings.containsKey(key)){
        String[] row=new String[columns.length];
        for(int column=0;column<columns.length;column++)row[column]="name".equals(columns[column])?key:"value".equals(columns[column])?settings.get(key):null;
        rows.add(row);
      }
      return new Rows(rows);
    }finally{writer.unlock();}
  }
  public Map<String,String> snapshot(){writer.lock();try{return new LinkedHashMap<>(settings);}finally{writer.unlock();}}
  public void seed(Map<String,String> values){writer.lock();try{if(!successful.isEmpty())throw new AssertionError("Seed inside transaction");settings=new LinkedHashMap<>(values);}finally{writer.unlock();}}
  public boolean balanced(){writer.lock();try{return begins==ends&&successful.isEmpty();}finally{writer.unlock();}}
  private static final class Rows implements Cursor {
    private final List<String[]> rows;private int position=-1;private boolean closed;
    Rows(List<String[]> rows){this.rows=rows;}
    public boolean moveToFirst(){position=0;return !rows.isEmpty();}
    public boolean moveToNext(){return ++position<rows.size();}
    public String getString(int column){if(closed)throw new IllegalStateException("Closed cursor");return rows.get(position)[column];}
    public void close(){closed=true;}
  }
}
