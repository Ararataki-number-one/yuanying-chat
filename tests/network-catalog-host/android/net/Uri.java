package android.net;
public final class Uri {
  final java.net.URI value;private Uri(String text){value=java.net.URI.create(text);}
  public static Uri parse(String value){return new Uri(value);}
  public String getHost(){return value.getHost();}
}
