package local.pocketchat;

/** An honest waiting hint, never a network timeout or permission to reload. */
final class PageLoadingWait {
  static final long SLOW_MS=20000;
  private long since=-1;
  boolean update(boolean empty,long now){
    if(!empty){since=-1;return false;}
    if(since<0||now<since)since=now;
    return now-since>=SLOW_MS;
  }
}
