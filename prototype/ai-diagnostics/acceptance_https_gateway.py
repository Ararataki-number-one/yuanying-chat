#!/usr/bin/env python3
"""Loopback HTTPS acceptance fixture. No model, paid client or outbound transport.

Use an operator-owned trusted certificate behind an existing controlled reverse
proxy. The only response is bounded version-2 enum guidance derived locally.
No request bodies, authorization values, IDs or provider output are logged.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from socketserver import TCPServer
from urllib.parse import urlsplit

# These two modules contain only protocol/local validation code. In particular,
# do not import provider_gateway, responses_transport or responses_ledger here.
from diagnostic_gateway import AuthenticatedGateway, DEMO_TOKEN, Handler, Result, error
from responses_diagnosis import FAULTS, InvalidDiagnosis, render_reply

MAX_DELAY_MS = 3000
MAX_CONNECTIONS = 8


def authority(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?", value):
        raise ValueError("invalid_authority")
    parsed = urlsplit("//" + value)
    if not parsed.hostname or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in parsed.hostname.split(".")):
        raise ValueError("invalid_authority")
    port = parsed.port if parsed.port is not None else 443
    if not 1 <= port <= 65535:
        raise ValueError("invalid_authority")
    return parsed.hostname, port


def approved_authority(endpoint):
    match = re.fullmatch(r"https://([A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?)/v1/diagnose", endpoint) if type(endpoint) is str else None
    if match is None:
        raise ValueError("invalid_endpoint")
    selected = authority(match.group(1))
    if selected[0] in ("api.openai.com", "api.deepseek.com"):
        raise ValueError("invalid_endpoint")
    return selected


def read_test_token(path):
    # No defaults or provider environment variables. Refuse symlinks, special
    # files and group/world-readable files before reading the small test token.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("invalid_token_file")
        value = os.read(descriptor, 258)
        if len(value) > 257:
            raise ValueError("invalid_token_file")
        token = value.decode("ascii").rstrip("\n")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token) or token == DEMO_TOKEN:
            raise ValueError("invalid_token_file")
        return token
    finally:
        os.close(descriptor)


def tls_context(cert, key, hostname):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    def encrypted_key_unsupported():
        raise ValueError("encrypted_key_requires_operator_setup")
    context.load_cert_chain(certfile=cert, keyfile=key, password=encrypted_key_unsupported)
    try:
        ipaddress.ip_address(hostname)
        expected_sni = None  # TLS clients do not send SNI for IP literals.
    except ValueError:
        expected_sni = hostname
    def check_sni(connection, supplied, selected_context):
        if (supplied.lower() if type(supplied) is str else supplied) != expected_sni:
            return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
        return None
    context.set_servername_callback(check_sni)
    return context


class AcceptanceGateway(AuthenticatedGateway):
    """Synthetic local responses with bounded, process-lifetime replay storage."""
    def __init__(self, token, endpoint, response_delay_ms=0, capacity=128, count_sink=None):
        if token == DEMO_TOKEN:
            raise ValueError("dedicated_test_token_required")
        super().__init__(token)
        self.approved = approved_authority(endpoint)
        if type(response_delay_ms) is not int or not 0 <= response_delay_ms <= MAX_DELAY_MS:
            raise ValueError("invalid_delay")
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError("invalid_capacity")
        self.delay = response_delay_ms / 1000
        self.capacity = capacity
        self.entries = {}
        self.lock = threading.Lock()
        self.count_sink = count_sink
        self._counts = {"received": 0, "completed": 0, "replayed": 0, "rejected": 0}

    def counts(self):
        with self.lock:
            return dict(self._counts)

    def publish_counts(self):
        if self.count_sink is not None:
            try:
                self.count_sink(self.counts())
            except Exception:
                pass  # A closed operator output pipe cannot affect a response.

    def host_allowed(self, host):
        try:
            return authority(host) == self.approved
        except (TypeError, ValueError):
            return False

    def dispatch(self, method, path, headers, raw):
        result = super().dispatch(method, path, headers, raw)
        if result.status >= 400:
            with self.lock:
                self._counts["rejected"] += 1
            self.publish_counts()
        return result

    def diagnose(self, key, raw, value):
        digest = hashlib.sha256(raw).digest()
        with self.lock:
            previous = self.entries.get(key)
            if previous is not None:
                if previous[0] != digest:
                    return error(409, "idempotency_conflict")
                if previous[1] is None:
                    return error(409, "request_in_progress")
                self._counts["replayed"] += 1
                cached = previous[1]
            else:
                if len(self.entries) >= self.capacity:
                    return error(503, "capacity_reached")
                self.entries[key] = (digest, None)
                self._counts["received"] += 1
                cached = None
        self.publish_counts()
        if cached is not None:
            return Result(cached[0], json.loads(cached[1]))
        # Deliberately choose only "insufficient evidence" and a local read-only
        # review. This is an acceptance fixture, not an inferred model diagnosis.
        choices = []
        for entry in value["evidence"]:
            event = next((item for item in entry["events"] if item["kind"] in FAULTS), None)
            if event is not None:
                choices.append({"hypothesis": "INSUFFICIENT_EVIDENCE", "tabEvidenceId": entry["tabEvidenceId"],
                    "evidence": [{"eventId": event["id"], "signal": event["signal"]}],
                    "steps": ["REVIEW_LOCAL_DIAGNOSTICS"]})
        diagnosis = {"hypotheses": choices}
        try:
            render_reply(value, diagnosis)  # Reuse the real strict local join/whitelist.
            result = Result(200, {"version": 2, "diagnosis": diagnosis})
        except InvalidDiagnosis:
            result = error(400, "invalid_request")
        if result.status == 200 and self.delay:
            time.sleep(self.delay)
        encoded = json.dumps(result.body, ensure_ascii=True, separators=(",", ":"))
        with self.lock:
            self.entries[key] = (digest, (result.status, encoded))
            self._counts["completed"] += 1
        self.publish_counts()
        return Result(result.status, json.loads(encoded))


class AcceptanceHandler(Handler):
    server_version = "PocketChatSyntheticAcceptance"
    sys_version = ""

    def parse_request(self):
        if not super().parse_request():
            return False
        # BaseHTTPRequestHandler normalizes //path. Inspect the original target
        # so a proxy/path mismatch cannot silently pass the exact-path check.
        parts = self.raw_requestline.rstrip(b"\r\n").split()
        if len(parts) != 3 or parts[1] != b"/v1/diagnose":
            self.send_result(error(404, "not_found"))
            return False
        if self.command != "POST":
            self.send_result(error(405, "method_not_allowed"))
            return False
        return True

    def send_error(self, code, message=None, explain=None):
        self.send_result(error(code if type(code) is int and 400 <= code <= 599 else 400, "invalid_http"))

    def send_result(self, result):
        data = json.dumps(result.body, ensure_ascii=False).encode("utf-8")
        self.send_response(result.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-PocketChat-Acceptance", "synthetic-no-provider")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)


class AcceptanceServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = MAX_CONNECTIONS

    def __init__(self, port, gateway, context, max_connections=MAX_CONNECTIONS):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid_port")
        if type(max_connections) is not int or not 1 <= max_connections <= MAX_CONNECTIONS:
            raise ValueError("invalid_connections")
        self.gateway = gateway
        self.tls = context
        self.connections = threading.BoundedSemaphore(max_connections)
        # Never expose a bind argument; a controlled existing ingress must own
        # every non-loopback/public listener and its certificate trust policy.
        super().__init__(("127.0.0.1", port), AcceptanceHandler)

    def server_bind(self):
        # HTTPServer.server_bind normally calls getfqdn(), which may ask NSS/DNS
        # even for loopback on an unusual host. No resolver belongs in this fixture.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.connections.release()
            self.shutdown_request(request)

    def process_request_thread(self, request, client_address):
        secured = None
        try:
            # Handshake in a bounded worker, never in the accepting thread.
            request.settimeout(3)
            secured = self.tls.wrap_socket(request, server_side=True, do_handshake_on_connect=False)
            secured.settimeout(3)
            secured.do_handshake()
            self.finish_request(secured, client_address)
        except Exception:
            pass  # Never let a worker exception print request-related details.
        finally:
            self.shutdown_request(secured if secured is not None else request)
            self.connections.release()

    def handle_error(self, request, client_address):
        pass  # Do not print request lines, authorization, bodies or exceptions.


def print_counts(counts):
    print("ACCEPTANCE_COUNTS " + " ".join(f"{name}={counts[name]}" for name in
          ("received", "completed", "replayed", "rejected")), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Loopback HTTPS synthetic acceptance only; no provider clients or outbound requests.")
    parser.add_argument("--endpoint", required=True, help="Pinned HTTPS /v1/diagnose URL of an existing controlled ingress")
    parser.add_argument("--cert", required=True, help="Operator-owned TLS certificate/full chain")
    parser.add_argument("--key", required=True, help="Operator-owned private TLS key file")
    parser.add_argument("--token-file", required=True, help="Private 0600 file containing a dedicated synthetic gateway token")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--response-delay-ms", type=int, default=0, help="0..3000 ms; local cancellation/network-switch acceptance")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("invalid_port")
    try:
        selected = approved_authority(args.endpoint)
        token = read_test_token(args.token_file)
        gateway = AcceptanceGateway(token, args.endpoint, args.response_delay_ms, count_sink=print_counts)
        context = tls_context(args.cert, args.key, selected[0])
        server = AcceptanceServer(args.port, gateway, context)
    except (OSError, ValueError, UnicodeError):
        print("HTTPS_ACCEPTANCE configuration rejected", file=sys.stderr)
        return 2
    print(f"HTTPS_ACCEPTANCE synthetic_only=true bind=127.0.0.1 port={args.port} delay_ms={args.response_delay_ms}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
