package android.content;

/** Minimal host adapter: no Android runtime or storage is executed. */
public abstract class Context {
  public abstract SharedPreferences getSharedPreferences(String name,int mode);
}
