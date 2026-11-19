package local.pocketchat;

import java.io.IOException;
import java.net.Socket;

/** Owns every underlying socket before it can dial or perform a handshake. */
interface ChromiumRouteSocketOwner {
    void register(Socket socket) throws IOException;
    boolean current();
}
