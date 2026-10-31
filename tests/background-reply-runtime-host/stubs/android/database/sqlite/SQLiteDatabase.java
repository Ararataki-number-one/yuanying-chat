package android.database.sqlite;
import java.util.concurrent.locks.ReentrantLock;
/** Writer-gate call recorder only. Authority and rollback have a separate host suite. */
public final class SQLiteDatabase {
  private final ReentrantLock writer=new ReentrantLock(true);private int depth;
  public int begins,ends,successful;public boolean failBeginLocked;
  public void beginTransaction(){if(failBeginLocked)throw new SQLiteDatabaseLockedException("Synthetic startup gate locked");writer.lock();depth++;begins++;}
  public void setTransactionSuccessful(){if(!writer.isHeldByCurrentThread()||depth==0)throw new AssertionError("No writer transaction");successful++;}
  public void endTransaction(){if(!writer.isHeldByCurrentThread()||depth==0)throw new AssertionError("No writer transaction");depth--;ends++;writer.unlock();}
  public boolean balanced(){return depth==0&&begins==ends;}
}
