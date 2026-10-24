package android.os;
public final class Messenger {
 public interface Endpoint extends IBinder {void send(Message message)throws RemoteException;}
 private final IBinder binder;
 public Messenger(Handler handler){binder=new Endpoint(){public void send(Message message){Message copy=Message.obtain(message);handler.post(()->handler.dispatchMessage(copy));}};}
 public Messenger(IBinder binder){if(binder==null)throw new NullPointerException("binder");this.binder=binder;}
 public IBinder getBinder(){return binder;}public void send(Message message)throws RemoteException{if(!(binder instanceof Endpoint))throw new RemoteException("Host endpoint unavailable");((Endpoint)binder).send(Message.obtain(message));}
}
