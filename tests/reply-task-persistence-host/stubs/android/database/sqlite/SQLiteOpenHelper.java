package android.database.sqlite;

import android.content.Context;

/** Storage adapter only, not Android SQLiteOpenHelper or WAL execution. */
public abstract class SQLiteOpenHelper implements AutoCloseable {
  final Context context;final String name;
  protected SQLiteOpenHelper(Context context,String name,Object factory,int version){if(version!=1)throw new AssertionError("Unexpected schema migration");this.context=context;this.name=name;}
  public abstract void onCreate(SQLiteDatabase db);
  public abstract void onUpgrade(SQLiteDatabase db,int before,int after);
  public SQLiteDatabase getReadableDatabase(){return getWritableDatabase();}
  public SQLiteDatabase getWritableDatabase(){
    SQLiteDatabase db=context.databases.get(name);
    if(db==null){db=new SQLiteDatabase(context.root.resolve(name));context.databases.put(name,db);if(db.fresh)onCreate(db);}
    return db;
  }
  public void close(){}
}
