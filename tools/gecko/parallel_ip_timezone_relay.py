"""Test-only TLS passthrough for PocketChat's single IP time-zone service."""

import http.client
import ipaddress
import json
import re
import select
import socket
import ssl
import threading
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


HOST = "ipwho.is"
PORT = 443
AUTHORITY = "ipwho.is:443"
QUERY = "/?fields=success,ip,timezone.id"
MAX_BODY = 8192
MAX_TUNNEL_BYTES = 256 * 1024
TUNNELS = threading.BoundedSemaphore(4)


def _public_address(text):
    if not isinstance(text, str) or "%" in text:
        return False
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    if not ip.is_global or ip.is_multicast or ip.is_reserved:
        return False
    if ip.version == 6:
        # Exclude scoped, translated and embedded addresses from remote DNS answers.
        return (ip.packed[0] & 0xe0) == 0x20 and ip.sixtofour is None and ip.teredo is None
    return True


def _connect_service():
    # Resolve just the fixed host once and connect to the validated numeric address.
    deadline = time.monotonic() + 5
    for family, kind, proto, _, address in socket.getaddrinfo(HOST, PORT, type=socket.SOCK_STREAM,
                                                               proto=socket.IPPROTO_TCP):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if family not in (socket.AF_INET, socket.AF_INET6) or address[1] != PORT or not _public_address(address[0]):
            continue
        if family == socket.AF_INET6 and address[3] != 0:
            continue
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(min(2.5, remaining))
            sock.connect(address)
            return sock
        except OSError:
            sock.close()
    raise OSError("fixed service unavailable")


def _relay(client, upstream):
    # The app negotiates its own TLS session directly with the fixed service.
    client.settimeout(2)
    upstream.settimeout(2)
    deadline = time.monotonic() + 15
    transferred = 0
    while time.monotonic() < deadline:
        ready, _, _ = select.select((client, upstream), (), (), max(0, min(5, deadline - time.monotonic())))
        if not ready:
            return
        for source in ready:
            data = source.recv(16384)
            if not data:
                return
            transferred += len(data)
            if transferred > MAX_TUNNEL_BYTES:
                raise OverflowError("fixture byte limit")
            destination = upstream if source is client else client
            destination.sendall(data)


def handle_external_connect(handler, allowed):
    """Handle a non-fixture CONNECT request on the comparison's loopback proxy."""
    handler.close_connection = True
    host_headers = handler.headers.get_all("Host") or []
    if handler.path != AUTHORITY or (host_headers and
            (len(host_headers) != 1 or host_headers[0].lower() not in (HOST, AUTHORITY))):
        handler.server.record("elseConnectDenied")
        handler.answer(403)
        return
    if not allowed:
        handler.server.record("geoDenied")
        handler.answer(403)
        return
    if not TUNNELS.acquire(blocking=False):
        handler.server.record("geoRelayLimited")
        handler.answer(503)
        return
    try:
        try:
            upstream = _connect_service()
        except OSError:
            handler.server.record("geoUpstreamError")
            handler.answer(502)
            return
        with upstream:
            handler.server.record("geoOpened")
            try:
                handler.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                handler.wfile.flush()
                _relay(handler.connection, upstream)
            except OverflowError:
                handler.server.record("geoRelayLimited")
            except OSError:
                handler.server.record("geoRelayError")
    finally:
        TUNNELS.release()


def _unique(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate field")
    return result


def _valid_observation(body):
    if not 0 < len(body) <= MAX_BODY:
        return False
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
        if not isinstance(value, dict) or set(value) != {"success", "ip", "timezone"} or value["success"] is not True:
            return False
        timezone = value["timezone"]
        if not _public_address(value["ip"]) or not isinstance(timezone, dict) or set(timezone) != {"id"}:
            return False
        zone = timezone["id"]
        if (not isinstance(zone, str) or not re.fullmatch(r"[A-Za-z0-9_+./-]{1,80}", zone)
                or zone.startswith(("posix/", "right/"))):
            return False
        ZoneInfo(zone)
        return True
    except (UnicodeError, ValueError, ZoneInfoNotFoundError, RecursionError):
        return False


def preflight(proxy_port):
    """Return categorical health through the same proxy, without retaining its response."""
    connection = http.client.HTTPSConnection("127.0.0.1", proxy_port, timeout=5,
                                             context=ssl.create_default_context())
    connection.set_tunnel(HOST, PORT)
    try:
        connection.request("GET", QUERY, headers={"Host": HOST, "Accept": "application/json",
                                                 "Cache-Control": "no-store", "Connection": "close"})
        response = connection.getresponse()
        status = response.status
        if status != 200:
            return {"status": "unavailable", "reason": "http_status", "httpStatus": status}
        if not _valid_observation(response.read(MAX_BODY + 1)):
            return {"status": "unavailable", "reason": "invalid_observation", "httpStatus": status}
        return {"status": "passed", "reason": "valid_observation", "httpStatus": status}
    except ssl.SSLCertVerificationError:
        return {"status": "unavailable", "reason": "certificate"}
    except ssl.SSLError:
        return {"status": "unavailable", "reason": "tls"}
    except TimeoutError:
        return {"status": "unavailable", "reason": "timeout"}
    except (OSError, http.client.HTTPException):
        return {"status": "unavailable", "reason": "transport"}
    finally:
        connection.close()
