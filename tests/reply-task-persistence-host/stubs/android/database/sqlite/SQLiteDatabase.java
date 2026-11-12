package android.database.sqlite;

import android.content.ContentValues;
import android.database.Cursor;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Narrow file-backed storage boundary for the complete production DeliveryStore.
 * Unknown SQL shapes fail. These bytes are a host model, not an SQLite database. */
public final class SQLiteDatabase {
  public int failWrites;public boolean zeroNextUpdate;
  public final boolean fresh;
  final Path file;
  final LinkedHashMap<String,Map<String,Object>> rows=new LinkedHashMap<>();
  final List<String> columns=Arrays.asList("id","url","body","state","detail","user_key","files","kind","attempted","created","updated");
  SQLiteDatabase(Path file){
    this.file=file;fresh=!Files.exists(file);
    if(!fresh)try{JSONArray values=new JSONArray(Files.readString(file));for(int i=0;i<values.length();i++){JSONObject value=values.getJSONObject(i);Map<String,Object> row=new LinkedHashMap<>();for(String column:columns)row.put(column,value.get(column));rows.put(value.getString("id"),row);}}catch(Exception error){throw new IllegalStateException(error);}
  }
  public void execSQL(String sql){if(!sql.startsWith("CREATE TABLE deliveries(")&&!sql.equals("CREATE INDEX by_conversation ON deliveries(url,created)"))throw new AssertionError("Unsupported DDL");}
  void failWrite(){if(failWrites>0){failWrites--;throw new IllegalStateException("Controlled SQLite write failure");}}
  void persist(){try{JSONArray values=new JSONArray();for(Map<String,Object> row:rows.values())values.put(new JSONObject(row));Files.writeString(file,values.toString());}catch(Exception error){throw new IllegalStateException(error);}}
  public long insertOrThrow(String table,String nullColumn,ContentValues values){
    if(!table.equals("deliveries"))throw new AssertionError("Unsupported table");failWrite();String id=(String)values.get("id");if(rows.containsKey(id))throw new IllegalStateException("Duplicate id");
    Map<String,Object> row=new LinkedHashMap<>();for(String column:columns)row.put(column,"");row.put("detail","");row.put("user_key","");row.put("attempted",0);row.putAll(values);rows.put(id,row);persist();return rows.size();
  }
  public int update(String table,ContentValues values,String where,String[] args){
    if(!table.equals("deliveries")||!where.equals("id=?")||args.length!=1)throw new AssertionError("Unsupported update");failWrite();if(zeroNextUpdate){zeroNextUpdate=false;return 0;}
    Map<String,Object> row=rows.get(args[0]);if(row==null)return 0;row.putAll(values);persist();return 1;
  }
  public void removeForTest(String id){if(rows.remove(id)==null)throw new AssertionError("No fixture row to remove");persist();}
  public Cursor query(String table,String[] projection,String selection,String[] args,String group,String having,String order){return query(table,projection,selection,args,group,having,order,null);}
  public Cursor query(String table,String[] projection,String selection,String[] args,String group,String having,String order,String limit){
    if(!table.equals("deliveries")||projection!=null||group!=null||having!=null)throw new AssertionError("Unsupported query boundary");
    List<Map<String,Object>> selected=new ArrayList<>();
    for(Map<String,Object> row:rows.values()){
      boolean match;
      if(selection.equals("id=?"))match=row.get("id").equals(args[0]);
      else if(selection.equals("url=?"))match=row.get("url").equals(args[0]);
      else if(selection.equals("state IN ('queued','sending','confirmed','awaiting')"))match=Arrays.asList("queued","sending","confirmed","awaiting").contains(row.get("state"));
      else if(selection.equals("url=? AND body=? AND files=? AND kind='send' AND attempted=0 AND state IN ('queued','failed','draft')"))match=row.get("url").equals(args[0])&&row.get("body").equals(args[1])&&row.get("files").equals(args[2])&&row.get("kind").equals("send")&&((Number)row.get("attempted")).intValue()==0&&Arrays.asList("queued","failed","draft").contains(row.get("state"));
      else throw new AssertionError("Unsupported selection: "+selection);
      if(match)selected.add(new LinkedHashMap<>(row));
    }
    if(order!=null&&!order.equals("rowid ASC")&&!order.equals("created DESC"))throw new AssertionError("Unsupported order");
    if("created DESC".equals(order))Collections.reverse(selected);
    if(limit!=null){if(!limit.equals("1"))throw new AssertionError("Unsupported limit");if(selected.size()>1)selected=new ArrayList<>(selected.subList(0,1));}
    return new Cursor(selected,columns);
  }
}
