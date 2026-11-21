"""Explicit server-side composition for paid diagnostic requests.

The loopback CLI stays synthetic. An operator must supply a verified gateway
origin, a private durable ledger and a server-only credential provider.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from types import MappingProxyType
from urllib.parse import urlsplit

from diagnostic_gateway import AuthenticatedGateway, DEMO_TOKEN, Result, error, observations
from responses_diagnosis import InvalidDiagnosis, build_responses_request, parse_response
from responses_ledger import Ledger, LedgerError
from responses_transport import ResponsesTransport, TransportError


def _authority(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?", value):
        raise ValueError("invalid gateway authority")
    parts = urlsplit("//" + value)
    if not parts.hostname or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                                 for label in parts.hostname.split(".")):
        raise ValueError("invalid gateway authority")
    port = parts.port if parts.port is not None else 443
    if port == 0:
        raise ValueError("invalid gateway port")
    return parts.hostname, port


def approved_authority(endpoint):
    """Validate the operator's pinned HTTPS origin and exact diagnostic path."""
    match = re.fullmatch(r"https://([A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?)/v1/diagnose", endpoint) if isinstance(endpoint, str) else None
    if match is None:
        raise ValueError("gateway must be an approved HTTPS /v1/diagnose endpoint")
    authority = _authority(match.group(1))
    if authority[0] in ("api.openai.com", "api.deepseek.com"):
        raise ValueError("gateway authority must be configured separately")
    return authority


class ProviderGateway(AuthenticatedGateway):
    """Disabled by default; no real mode is exposed through the mock CLI."""

    def __init__(self, token, *, enable_paid_requests=False, gateway_endpoint=None,
                 device_route_accepted=False, provider_egress_accepted=False, models=None,
                 ledger=None, transport=None,
                 deadline_seconds=20.0):
        super().__init__(token)
        if type(enable_paid_requests) is not bool:
            raise ValueError("paid mode requires explicit approval")
        self._enabled = enable_paid_requests
        if not enable_paid_requests:
            return
        if token == DEMO_TOKEN or device_route_accepted is not True or provider_egress_accepted is not True:
            raise ValueError("paid mode requires a private relay token and completed device and egress acceptance")
        self._authority = approved_authority(gateway_endpoint)
        if (type(models) is not dict or not models or
                any(provider not in ("openai", "deepseek") or not isinstance(model, str)
                    or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", model)
                    for provider, model in models.items())):
            raise ValueError("configure supported providers and model names explicitly")
        if not isinstance(ledger, Ledger) or not isinstance(transport, ResponsesTransport):
            raise ValueError("paid mode requires a durable ledger and fixed HTTPS transport")
        if (type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds)
                or not 0 < deadline_seconds <= 25):
            raise ValueError("invalid paid deadline")
        if ledger.reservation_ttl <= deadline_seconds + ledger.busy_timeout_seconds:
            raise ValueError("ledger lease must outlive the paid deadline and commit wait")
        self._models = MappingProxyType(dict(models))
        self._ledger = ledger
        self._transport = transport
        self._deadline_seconds = deadline_seconds

    def host_allowed(self, host):
        if not self._enabled:
            return True
        try:
            return _authority(host) == self._authority
        except ValueError:
            return False

    def diagnose(self, key, raw, value):
        if not self._enabled:
            return error(503, "paid_requests_disabled")
        model = self._models.get(value["provider"])
        if model is None:
            return error(503, "provider_not_configured")
        deadline = time.monotonic() + self._deadline_seconds
        try:
            payload = build_responses_request(value, model) if observations(value) else None
        except InvalidDiagnosis:
            return error(400, "invalid_request")
        binding = json.dumps({"version": 2, "provider": value["provider"],
                              "model": model, "payload": payload}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        descriptor = hashlib.sha256(raw).digest() + hashlib.sha256(binding).digest()
        try:
            state = self._ledger.reserve(key, descriptor)
        except LedgerError:
            return error(503, "ledger_unavailable")
        except ValueError:
            return error(400, "invalid_request")
        if state.status == "CONFLICT":
            return error(409, "idempotency_conflict")
        if state.status == "IN_PROGRESS":
            return error(409, "request_in_progress")
        if state.status == "UNCERTAIN":
            return error(409, "request_outcome_unknown")
        if state.status == "COMPLETED":
            return error(409, "result_not_retained")
        if state.status == "RATE_LIMITED":
            return error(429, "rate_limited")
        if state.status != "RESERVED" or state.reservation is None:
            return error(503, "capacity_reached")
        reservation = state.reservation
        try:
            if payload is None:
                diagnosis = {"hypotheses": []}
            else:
                response = self._transport.send(value["provider"], payload, deadline=deadline)
                diagnosis = parse_response(response, value)
            if time.monotonic() >= deadline:
                self._mark_uncertain(reservation)
                return error(504, "deadline_exceeded")
        except TransportError as failure:
            self._mark_uncertain(reservation)
            if failure.reason == "deadline_exceeded":
                return error(504, "deadline_exceeded")
            return error(502, "provider_unavailable")
        except (InvalidDiagnosis, TypeError, ValueError):
            self._mark_uncertain(reservation)
            return error(502, "invalid_provider_response")
        try:
            if self._ledger.complete(reservation):
                return Result(200, {"version": 2, "diagnosis": diagnosis})
        except LedgerError:
            pass
        # The durable reservation still prevents a second paid call. Never give
        # a success answer whose terminal state could not be recorded.
        return error(503, "request_outcome_unknown")

    def _mark_uncertain(self, reservation):
        try:
            self._ledger.uncertain(reservation)
        except LedgerError:
            # A pre-existing durable reservation remains an admission fence.
            pass
