package android.content;

import android.app.ActivityManager;

/** Only the typed ActivityManager service API used by production is represented. */
public final class Context {
  public ActivityManager manager;
  public int lookups;
  public Class<?> lastRequestedClass;
  public RuntimeException failure;
  public Context(ActivityManager manager) { this.manager = manager; }
  public <T> T getSystemService(Class<T> requested) {
    lookups++;
    lastRequestedClass = requested;
    if (failure != null) throw failure;
    if (requested != ActivityManager.class) throw new AssertionError("Unexpected service API");
    return manager == null ? null : requested.cast(manager);
  }
}
