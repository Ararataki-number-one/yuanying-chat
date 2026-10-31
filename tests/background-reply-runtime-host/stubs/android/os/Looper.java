package android.os;
public final class Looper {
  static final Thread mainThread=Thread.currentThread();static final Looper MAIN=new Looper();
  public static Looper getMainLooper(){return MAIN;}
  public static Looper myLooper(){return Thread.currentThread()==mainThread?MAIN:null;}
}
