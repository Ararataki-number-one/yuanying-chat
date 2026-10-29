package android.database.sqlite;
import java.util.*;import org.json.*;import android.database.Cursor;
/** Counted deterministic database boundary; not Android SQLite. */
public final class SQLiteDatabase {
 public final Map<String,List<Map<String,Object>>> tables=new LinkedHashMap<>();Map<String,List<Map<String,Object>>> snapshot;
 public int queries,jsonReads,begins,successes,ends,failQuery,closed,failRead=-1;public boolean failBegin;public Runnable mutateAfterFirstQuery,mutateAfterFirstRead;
 public SQLiteDatabase(){for(String table:new String[]{"files","tasks","deleted_files"})tables.put(table,new ArrayList<>());}
 public void add(String table,JSONObject row){Map<String,Object> value=new LinkedHashMap<>();value.put("row",row.toString());value.put("uri",row.optString("uri"));value.put("time",row.optLong("time"));tables.get(table).add(value);}
 public void addDelete(String uri,long time){Map<String,Object> value=new LinkedHashMap<>();value.put("uri",uri);value.put("time",time);tables.get("deleted_files").add(value);}
 public void clear(String table){tables.get(table).clear();}
 public void beginTransactionNonExclusive(){if(failBegin)throw new IllegalStateException("begin");if(snapshot!=null)throw new AssertionError("nested");begins++;snapshot=new LinkedHashMap<>();for(Map.Entry<String,List<Map<String,Object>>> e:tables.entrySet())snapshot.put(e.getKey(),new ArrayList<>(e.getValue()));}
 public void setTransactionSuccessful(){if(snapshot==null)throw new AssertionError("no transaction");successes++;}
 public void endTransaction(){if(snapshot==null)throw new AssertionError("no transaction");ends++;snapshot=null;}
 public boolean inTransaction(){return snapshot!=null;}
 public Cursor query(String table,String[] columns,String selection,String[] args,String group,String having,String order){
  queries++;if(queries==failQuery)throw new IllegalStateException("query"+queries);if(selection!=null||group!=null||having!=null)throw new AssertionError("unexpected SQL filter");List<Map<String,Object>> rows=new ArrayList<>((snapshot==null?tables:snapshot).get(table));
  if(order!=null){if(!order.equals("time ASC")&&!order.equals("time DESC"))throw new AssertionError(order);Collections.reverse(rows);rows.sort(Comparator.comparingLong(r->((Number)r.get("time")).longValue()));if(order.endsWith("DESC"))Collections.reverse(rows);}
  if(queries==1&&mutateAfterFirstQuery!=null)mutateAfterFirstQuery.run();
  return new Cursor(){int at=-1;public boolean moveToNext(){return ++at<rows.size();}public int getInt(int column){return ((Number)rows.get(at).get(columns[column])).intValue();}public String getString(int column){if(columns[column].equals("row"))jsonReads++;Object value=rows.get(at).get(columns[column]);return value==null?null:String.valueOf(value);}public long getLong(int column){return ((Number)rows.get(at).get(columns[column])).longValue();}public void close(){}};
 }

 public Cursor rawQuery(String sql,String[] args){
  if(!sql.equals("SELECT 0 AS kind,row,NULL AS uri,time,rowid AS position FROM files UNION ALL SELECT 1,NULL,uri,time,rowid FROM deleted_files UNION ALL SELECT 2,row,NULL,time,rowid FROM tasks ORDER BY kind,time ASC,position DESC")||args!=null)throw new AssertionError("Unexpected display SQL");
  queries++;if(queries==failQuery)throw new IllegalStateException("statement");List<Object[]> combined=new ArrayList<>();int kind=0;for(String table:new String[]{"files","deleted_files","tasks"}){long position=0;for(Map<String,Object> row:tables.get(table))combined.add(new Object[]{kind,row.get("row"),kind==1?row.get("uri"):null,row.get("time"),++position});kind++;}
  combined.sort(Comparator.<Object[]>comparingInt(r->((Number)r[0]).intValue()).thenComparingLong(r->((Number)r[3]).longValue()).thenComparing((a,b)->Long.compare(((Number)b[4]).longValue(),((Number)a[4]).longValue())));
  return new Cursor(){int at=-1;public boolean moveToNext(){if(at+1==failRead)throw new IllegalStateException("cursor");boolean result=++at<combined.size();if(at==0&&mutateAfterFirstRead!=null)mutateAfterFirstRead.run();return result;}public int getInt(int column){return ((Number)combined.get(at)[column]).intValue();}public String getString(int column){if(column==1)jsonReads++;Object value=combined.get(at)[column];return value==null?null:String.valueOf(value);}public long getLong(int column){return ((Number)combined.get(at)[column]).longValue();}public void close(){closed++;}};
 }
}
