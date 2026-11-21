"""Bounded standard-library HTTPS transport for server-injected Responses calls.

No environment or credential files are read. Construction does not contact a
provider. Only send() can make a request; tests inject offline connections.
"""
from __future__ import annotations

import http.client
import json
import math
import re
import socket
import ssl
import threading
import time
from types import MappingProxyType

ENDPOINTS = MappingProxyType({
    "openai": ("api.openai.com", 443, "/v1/responses"),
    "deepseek": ("api.deepseek.com", 443, "/responses"),
})
REASONS = frozenset({"deadline_exceeded", "capacity_reached", "invalid_request",
                     "credentials_unavailable", "upstream_rejected", "invalid_response", "network_failed"})
MAX_REQUEST_BYTES = 262144
MAX_HEADER_BYTES = 16384
MAX_HEADER_LINE = 8192


class TransportError(Exception):
    """Stable, non-secret reason; never wraps a provider message for callers."""
    def __init__(self, reason):
        self.reason = reason if reason in REASONS else "network_failed"
        super().__init__(self.reason)


def _abort(sock):
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


class _Call:
    def __init__(self, deadline):
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.sock = None

    def remaining(self):
        left = self.deadline - time.monotonic()
        if self.cancelled.is_set() or left <= 0:
            raise TransportError("deadline_exceeded")
        return left

    def register(self, sock):
        with self.lock:
            self.sock = sock
            cancelled = self.cancelled.is_set()
        if cancelled:
            _abort(sock)
            raise TransportError("deadline_exceeded")
        sock.settimeout(self.remaining())

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            sock = self.sock
        _abort(sock)

    def refresh(self):
        remaining = self.remaining()
        with self.lock:
            sock = self.sock
        if sock is not None:
            sock.settimeout(remaining)
        return remaining


class _LineBudget:
    """Bound status/header/chunk-framing lines before stdlib allocates them.

    The budget also covers chunk framing/trailers. JSON body bytes are counted
    independently by the caller; tiny excessive chunks are conservatively rejected.
    """
    def __init__(self, fp):
        self.fp = fp
        self.remaining = MAX_HEADER_BYTES

    def readline(self, limit=-1):
        cap = min(MAX_HEADER_LINE + 1, self.remaining + 1)
        if limit >= 0:
            cap = min(cap, limit)
        line = self.fp.readline(cap)
        if len(line) > MAX_HEADER_LINE or len(line) > self.remaining:
            raise TransportError("invalid_response")
        self.remaining -= len(line)
        return line

    def __getattr__(self, name):
        return getattr(self.fp, name)


class _BoundedHTTPResponse(http.client.HTTPResponse):
    def __init__(self, sock, debuglevel=0, method=None, url=None):
        super().__init__(sock, debuglevel=0, method=method, url=url)
        self.fp = _LineBudget(self.fp)


class _DeadlineHTTPSConnection(http.client.HTTPSConnection):
    """Separate DNS/TCP/TLS so deadline cancellation can register each socket."""
    response_class = _BoundedHTTPResponse

    def __init__(self, host, port, *, timeout, context, state):
        super().__init__(host, port, timeout=timeout, context=context)
        self.state = state
        self.tls_context = context
        self.auto_open = 0  # Never reconnect implicitly after cancellation/close.

    def connect(self):
        self.state.remaining()
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        self.state.remaining()  # DNS may outlive its caller: no late TCP/POST.
        if not addresses:
            raise TransportError("network_failed")
        family, kind, proto, _, address = addresses[0]
        if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
            raise TransportError("network_failed")
        raw = socket.socket(family, kind, proto)
        self.sock = raw
        self.state.register(raw)
        raw.connect(address)  # One address attempt, no fallback/retry.
        self.state.refresh()
        secured = self.tls_context.wrap_socket(raw, server_hostname=self.host,
                                                do_handshake_on_connect=False)
        self.sock = secured
        self.state.register(secured)
        secured.do_handshake()
        self.state.refresh()


def _no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise TransportError("invalid_response")
        value[key] = item
    return value


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise TransportError("invalid_response")
    return number


def _check_json_tree(value, depth=0, budget=None):
    # Preflight the tree before JSON serialization: no enormous intermediate body.
    if budget is None:
        budget = [MAX_REQUEST_BYTES]
    budget[0] -= 1
    if depth > 64 or budget[0] < 0:
        raise TransportError("invalid_response")
    if type(value) is str:
        if len(value) > budget[0]:
            raise TransportError("invalid_response")
        budget[0] -= len(value.encode("utf-8", errors="strict"))
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TransportError("invalid_response")
            _check_json_tree(key, depth + 1, budget)
            _check_json_tree(item, depth + 1, budget)
    elif type(value) is list:
        for item in value:
            _check_json_tree(item, depth + 1, budget)
    elif type(value) is int:
        if value.bit_length() > 4096:
            raise TransportError("invalid_response")
        budget[0] -= len(str(value))
    elif type(value) is float:
        if not math.isfinite(value):
            raise TransportError("invalid_response")
        budget[0] -= len(repr(value))
    elif value is not None and type(value) is not bool:
        raise TransportError("invalid_response")
    if budget[0] < 0:
        raise TransportError("invalid_response")


def _decode_response(data):
    try:
        value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=_no_duplicates,
                           parse_float=_finite_float,
                           parse_constant=lambda _: (_ for _ in ()).throw(TransportError("invalid_response")))
        if type(value) is not dict:
            raise TransportError("invalid_response")
        _check_json_tree(value, budget=[max(MAX_REQUEST_BYTES, len(data) * 2)])
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise TransportError("invalid_response") from None


def _encode_request(provider, payload):
    # Gateway owns the evidence/JSON Schema. This layer forbids network/tool modes
    # or destinations hidden in optional provider parameters.
    required = {"model", "instructions", "input", "stream", "tools", "tool_choice", "max_output_tokens", "text"}
    if provider == "openai":
        required.add("store")
    if type(payload) is not dict or set(payload) != required:
        raise TransportError("invalid_request")
    if (payload["stream"] is not False or payload["tools"] != [] or payload["tool_choice"] != "none"
            or (provider == "openai" and payload["store"] is not False)):
        raise TransportError("invalid_request")
    if (type(payload["model"]) is not str or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", payload["model"])
            or type(payload["max_output_tokens"]) is not int or not 1 <= payload["max_output_tokens"] <= 8192):
        raise TransportError("invalid_request")
    instructions = payload["instructions"]
    inputs = payload["input"]
    if type(instructions) is not str or not 1 <= len(instructions) <= 8192:
        raise TransportError("invalid_request")
    if type(inputs) is not list or len(inputs) != 1:
        raise TransportError("invalid_request")
    message = inputs[0]
    if type(message) is not dict or set(message) != {"role", "content"} or message["role"] != "user":
        raise TransportError("invalid_request")
    content = message["content"]
    if type(content) is not list or len(content) != 1:
        raise TransportError("invalid_request")
    part = content[0]
    if (type(part) is not dict or set(part) != {"type", "text"} or part["type"] != "input_text"
            or type(part["text"]) is not str or not 1 <= len(part["text"]) <= MAX_REQUEST_BYTES):
        raise TransportError("invalid_request")
    try:
        _decode_response(part["text"].encode("utf-8"))  # Data must be a JSON object, never a URL/file/image part.
    except (TransportError, UnicodeError):
        raise TransportError("invalid_request") from None
    text = payload["text"]
    if type(text) is not dict or set(text) != {"format"}:
        raise TransportError("invalid_request")
    output_format = text["format"]
    format_keys = {"type", "name", "schema"} | ({"strict"} if provider == "openai" else set())
    if (type(output_format) is not dict or set(output_format) != format_keys
            or output_format["type"] != "json_schema" or type(output_format["schema"]) is not dict
            or type(output_format["name"]) is not str
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", output_format["name"])
            or (provider == "openai" and output_format["strict"] is not True)):
        raise TransportError("invalid_request")
    try:
        _check_json_tree(payload)
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise TransportError("invalid_request")
        return body
    except (ValueError, TypeError, UnicodeError, RecursionError, TransportError):
        raise TransportError("invalid_request") from None


def _read_response(response, state, max_bytes):
    if response.status != 200:
        # This includes redirects: no redirect policy or error-body reflection.
        raise TransportError("upstream_rejected")
    fields = {}
    for key, value in response.getheaders():
        fields.setdefault(key.lower(), []).append(value.strip())
    for key in ("content-length", "content-type", "content-encoding", "transfer-encoding"):
        if len(fields.get(key, [])) > 1:
            raise TransportError("invalid_response")
    ctype = fields.get("content-type", [""])[0]
    if not re.fullmatch(r"application/json(?:\s*;\s*charset\s*=\s*utf-8)?", ctype, re.I):
        raise TransportError("invalid_response")
    if fields.get("content-encoding", ["identity"])[0].lower() != "identity":
        raise TransportError("invalid_response")
    expected = None
    if "content-length" in fields:
        length = fields["content-length"][0]
        if not re.fullmatch(r"[0-9]{1,9}", length) or int(length) > max_bytes or "transfer-encoding" in fields:
            raise TransportError("invalid_response")
        expected = int(length)
    if "transfer-encoding" in fields and fields["transfer-encoding"][0].lower() != "chunked":
        raise TransportError("invalid_response")
    chunks, size = [], 0
    while True:
        state.refresh()
        part = response.read1(min(8192, max_bytes - size + 1))
        state.remaining()
        if not part:
            break
        size += len(part)
        if size > max_bytes:
            raise TransportError("invalid_response")
        chunks.append(part)
    if expected is not None and size != expected:
        raise TransportError("invalid_response")
    return _decode_response(b"".join(chunks))


class ResponsesTransport:
    """A provider call with an absolute monotonic deadline and bounded workers.

    credential_provider(provider) is explicitly supplied by the server owner.
    It is called inside the bounded worker after authenticated TLS connection.
    No credential lookup happens during construction. connection_factory is an
    offline test seam; production uses the secure stdlib connection above.

    A deadline closes a registered socket and returns without waiting for blocked
    DNS or credential code. Python cannot kill those threads; they remain counted
    until exit. After a late DNS completion, no TCP connection or POST is started.
    A POST already in flight may have been processed; callers must never assume
    cancellation means no charge, and must keep their durable reservation.
    """
    def __init__(self, credential_provider, *, max_workers=2, max_response_bytes=131072,
                 connection_factory=None):
        if not callable(credential_provider):
            raise ValueError("credential_provider must be callable")
        if (type(max_workers) is not int or not 1 <= max_workers <= 8
                or type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 1048576):
            raise ValueError("invalid transport limits")
        self.credential_provider = credential_provider
        self.max_response_bytes = max_response_bytes
        self.connection_factory = connection_factory or _DeadlineHTTPSConnection
        self.slots = threading.BoundedSemaphore(max_workers)

    def send(self, provider, payload, *, deadline):
        if (type(provider) is not str or provider not in ENDPOINTS or type(deadline) not in (int, float)
                or deadline < 0 or deadline > time.monotonic() + 300 or not math.isfinite(deadline)):
            raise TransportError("invalid_request")
        state = _Call(deadline)
        state.remaining()
        if not self.slots.acquire(blocking=False):
            raise TransportError("capacity_reached")
        completed, results = threading.Event(), []

        def work():
            conn = response = None
            try:
                body = _encode_request(provider, payload)
                state.remaining()
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.set_alpn_protocols(["http/1.1"])
                if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
                    raise TransportError("network_failed")
                host, port, path = ENDPOINTS[provider]
                conn = self.connection_factory(host, port, timeout=state.remaining(), context=context, state=state)
                conn.connect()
                state.refresh()
                try:
                    token = self.credential_provider(provider)
                except Exception:
                    raise TransportError("credentials_unavailable") from None
                state.remaining()
                if type(token) is not str or not re.fullmatch(r"[A-Za-z0-9._~+/-]{1,4096}={0,2}", token):
                    raise TransportError("credentials_unavailable")
                headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                           "Accept": "application/json", "Accept-Encoding": "identity",
                           "Content-Length": str(len(body)), "Connection": "close"}
                state.refresh()
                conn.request("POST", path, body=body, headers=headers, encode_chunked=False)
                state.refresh()
                response = conn.getresponse()
                state.remaining()
                result = _read_response(response, state, self.max_response_bytes)
                state.remaining()
                results.append(result)
            except TransportError as exc:
                results.append(TransportError(exc.reason))
            except (TimeoutError, socket.timeout):
                results.append(TransportError("deadline_exceeded"))
            except Exception:
                results.append(TransportError("network_failed"))
            finally:
                for resource in (response, conn):
                    if resource is not None:
                        try:
                            resource.close()
                        except Exception:
                            pass
                self.slots.release()
                completed.set()

        worker = threading.Thread(target=work, name="responses-transport", daemon=True)
        try:
            worker.start()
        except Exception:
            self.slots.release()
            raise TransportError("capacity_reached") from None
        try:
            finished = completed.wait(max(0, deadline - time.monotonic()))
        except Exception:
            state.cancel()
            raise TransportError("network_failed") from None
        except BaseException:
            state.cancel()
            raise
        if not finished or time.monotonic() >= deadline:
            state.cancel()
            raise TransportError("deadline_exceeded") from None
        result = results[0] if results else TransportError("network_failed")
        if isinstance(result, TransportError):
            raise result from None
        return result
