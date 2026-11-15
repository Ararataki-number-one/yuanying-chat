package android.database;

import java.util.*;

/** Read snapshots make delivery recovery iteration independent of subsequent writes. */
public final class Cursor implements AutoCloseable {
  final List<Map<String,Object>> rows;final List<String> columns;int position=-1;
  public Cursor(List<Map<String,Object>> rows,List<String> columns){this.rows=rows;this.columns=columns;}
  public boolean moveToFirst(){position=0;return !rows.isEmpty();}
  public boolean moveToNext(){return ++position<rows.size();}
  public int getColumnCount(){return columns.size();}
  public String getColumnName(int index){return columns.get(index);}
  public int getColumnIndexOrThrow(String name){int index=columns.indexOf(name);if(index<0)throw new IllegalArgumentException(name);return index;}
  public String getString(int index){Object value=rows.get(position).get(columns.get(index));return value==null?null:String.valueOf(value);}
  public long getLong(int index){return ((Number)rows.get(position).get(columns.get(index))).longValue();}
  public void close(){}
}
