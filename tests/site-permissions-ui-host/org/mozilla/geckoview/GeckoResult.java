package org.mozilla.geckoview;
import android.os.Handler;
public class GeckoResult<T> {
  public interface Consumer<V>{void accept(V value);}
  public GeckoResult<T> withHandler(Handler handler){return this;}
  public GeckoResult<Void> accept(Consumer<T> success,Consumer<Throwable> failure){return null;}
}
