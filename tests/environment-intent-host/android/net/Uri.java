package android.net;

/** Syntax adapter only. MainActivity.validProxy is extracted from production. */
public final class Uri {
  final java.net.URI value;
  private Uri(String text){value=java.net.URI.create(text);}
  public static Uri parse(String value){return new Uri(value);}
  public String getScheme(){return value.getScheme();}
  public String getHost(){return value.getHost();}
  public int getPort(){return value.getPort();}
  public String getUserInfo(){return value.getUserInfo();}
  public String getPath(){return value.getPath();}
  public String getQuery(){return value.getQuery();}
  public String getFragment(){return value.getFragment();}
}
