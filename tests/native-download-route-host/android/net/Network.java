package android.net;
import java.io.*;import java.net.*;
/** Controlled binding observer, never opens a socket. */
public final class Network {public final String name;public int opens;public HttpURLConnection connection;public Runnable onOpen;public boolean unavailable;public Network(String name){this.name=name;}public URLConnection openConnection(URL target,Proxy proxy)throws IOException {opens++;if(unavailable)throw new IOException("controlled network lost");if(onOpen!=null)onOpen.run();return connection;}public String toString(){return name;}public boolean equals(Object v){return v instanceof Network&&name.equals(((Network)v).name);}public int hashCode(){return name.hashCode();}}
