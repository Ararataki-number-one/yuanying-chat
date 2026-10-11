package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import java.util.*;

/** Profile-local, indexed receipt history; completing a reply never rewrites all IDs. */
final class ReplyNoticeLedger extends SQLiteOpenHelper {
  static final String DATABASE="reply-notices.db";
  ReplyNoticeLedger(Context c){super(c.getApplicationContext(),DATABASE,null,1);}
  @Override public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE noticed_replies(id TEXT PRIMARY KEY, noticed INTEGER NOT NULL)");}
  @Override public void onUpgrade(SQLiteDatabase db,int previous,int current){}
  boolean contains(String id){try(Cursor row=getReadableDatabase().query("noticed_replies",new String[]{"id"},"id=?",new String[]{id},null,null,null,"1")){return row.moveToFirst();}}
  void record(String id){if(id==null||id.isEmpty())return;ContentValues value=new ContentValues();value.put("id",id);value.put("noticed",System.currentTimeMillis());getWritableDatabase().insertWithOnConflict("noticed_replies",null,value,SQLiteDatabase.CONFLICT_IGNORE);}
  void migrate(SharedPreferences prefs){
    String old=prefs.getString("notifiedJob","");Set<String> ids=prefs.getStringSet("notifiedJobs",Collections.emptySet());
    if(ids.isEmpty()&&(old.isEmpty()||contains(old))){if(prefs.contains("notifiedJobs"))prefs.edit().remove("notifiedJobs").commit();return;}
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{record(old);for(String id:ids)record(id);db.setTransactionSuccessful();}finally{db.endTransaction();}
    // Clear a legacy aggregate only after all receipts are committed. Keep the
    // old single-job key readable for an upgrade from an earlier installation.
    if(prefs.contains("notifiedJobs"))prefs.edit().remove("notifiedJobs").commit();
  }
  static boolean notified(Context c,String id){try(ReplyNoticeLedger ledger=new ReplyNoticeLedger(c)){ledger.migrate(c.getSharedPreferences("chat",0));return ledger.contains(id);}}
}
