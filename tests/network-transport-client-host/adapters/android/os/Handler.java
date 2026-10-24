package android.os;
public class Handler {final Looper looper;public Handler(Looper looper){this.looper=looper;}public boolean post(Runnable task){looper.enqueue(task);return true;}public void handleMessage(Message message){}public void dispatchMessage(Message message){handleMessage(message);}}
