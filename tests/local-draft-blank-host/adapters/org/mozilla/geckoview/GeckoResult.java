package org.mozilla.geckoview;
/** Opaque host token; no scheduling or result completion is simulated. */
public final class GeckoResult<T> {
  public final T value;
  public GeckoResult(T value){this.value=value;}
}
