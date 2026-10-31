package android.database.sqlite;
/** The real Android exception type is modeled only for startup-gate failure dispatch. */
public final class SQLiteDatabaseLockedException extends RuntimeException {
  public SQLiteDatabaseLockedException(String message){super(message);}
}
