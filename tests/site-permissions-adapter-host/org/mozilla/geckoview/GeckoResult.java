package org.mozilla.geckoview;
public class GeckoResult<T> {
  public interface Consumer<V>{void accept(V value);}
  public Object handler;public Consumer<T> success;public Consumer<Throwable> failure;
  public GeckoResult<T> withHandler(Object handler){this.handler=handler;return this;}
  public GeckoResult<Void> accept(Consumer<T> success,Consumer<Throwable> failure){this.success=success;this.failure=failure;return null;}
  public void complete(T value){success.accept(value);}public void fail(){failure.accept(new IllegalStateException("controlled"));}
}
