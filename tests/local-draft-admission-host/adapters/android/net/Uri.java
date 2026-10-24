package android.net;
/** Limited host adapter for explicit absolute URL cases; not Android Uri parity. */
public final class Uri {
  private java.net.URI value;
  public static Uri parse(String text){Uri result=new Uri();result.value=java.net.URI.create(text);return result;}
  public String getScheme(){return value.getScheme();}
  public String getHost(){return value.getHost();}
  public String getPath(){return value.getPath();}
  public String getUserInfo(){return value.getUserInfo();}
  public int getPort(){return value.getPort();}
}
