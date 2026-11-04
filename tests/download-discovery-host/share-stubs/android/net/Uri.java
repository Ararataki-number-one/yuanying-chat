package android.net;
public final class Uri{final String value;Uri(String value){this.value=value;}public static Uri parse(String value){return new Uri(value);}public String toString(){return value;}}
