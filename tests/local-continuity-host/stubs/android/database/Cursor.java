package android.database;
import java.util.*;
public class Cursor implements AutoCloseable {
  final List<Map<String,Object>> rows;final String[] columns;int position=-1;
  public Cursor(List<Map<String,Object>> rows,String[] columns){this.rows=rows;this.columns=columns;}
  public boolean moveToNext(){return ++position<rows.size();}
  public String getString(int index){Object value=rows.get(position).get(columns[index]);return value==null?"":value.toString();}
  public long getLong(int index){Object value=rows.get(position).get(columns[index]);return value instanceof Number?((Number)value).longValue():0;}
  public void close(){}
}
