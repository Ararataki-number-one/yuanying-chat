package android.net;
public final class ConnectivityManager {public Network active;public NetworkCapabilities caps=new NetworkCapabilities();public Network getActiveNetwork(){return active;}public NetworkCapabilities getNetworkCapabilities(Network value){return value!=null&&value.equals(active)?caps:null;}}
