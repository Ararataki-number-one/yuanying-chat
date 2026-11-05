#!/usr/bin/env python3
"""Strict offline checks; native preference acknowledgements never replace TLS wire."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "browser"))
from native_tls_probe_server import TRIALS, HOSTS, parse_client_hello

MIN, MAX = "security.tls.version.min", "security.tls.version.max"
PROTECTED = ("privacy.resistFingerprinting", "network.http.http2.enabled", "network.http.http3.enable")


def require(condition, message):
    if not condition:
        raise ValueError("Native TLS evidence: " + message)


def strict_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 262144, "JSON byte bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(equal(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_preferences(value):
    require(type(value) is dict and set(value) == {MIN, MAX, *PROTECTED}, "exact fixed native preference keys")
    for key, row in value.items():
        require(type(row) is dict and set(row) == {"default", "user", "effective", "hasUserValue"}, "native preference row")
        expected = int if key in (MIN, MAX) else bool
        require(type(row["default"]) is expected and type(row["effective"]) is expected, "native preference type")
        require(row["user"] is None or type(row["user"]) is expected, "native USER preference type")
        require(type(row["hasUserValue"]) is bool and row["hasUserValue"] is (row["user"] is not None), "native USER presence")
        require(equal(row["effective"], row["user"] if row["hasUserValue"] else row["default"]), "native effective preference")
        if expected is int:
            require(3 <= row["default"] <= 4 and 3 <= row["effective"] <= 4, "obsolete protocol forbidden")


def validate_device(device, *, run, source, tree, leaf):
    require(type(device) is dict and type(device.get("schema")) is int and device["schema"] == 1, "device schema")
    require(device.get("status") == "observed" and device.get("stage") == "complete" and device.get("failureCode") == "", "completed native trial")
    for key, value in dict(runNonce=run, sourceCommit=source, sourceTree=tree).items():
        require(type(device.get(key)) is str and device[key] == value, "device identity: " + key)
    for key in ("actualAndroidExecution", "actualGeckoExecution", "standaloneSessionCapabilityOnly", "diagnosticOnly", "nativeRestoreSucceeded", "enterpriseRootsRestored"):
        require(device.get(key) is True, "actual native scope/restore: " + key)
    for key in ("releaseQualification", "nativeSettingReadbackIsWireProof", "fullTlsFingerprintEmulation", "quicWireVerified", "debuggingEndpointUsed", "javascriptTlsOverrideUsed", "rfpModified", "h2OrH3PrefsModified"):
        require(device.get(key) is False, "scope must remain false: " + key)
    require(type(device.get("pid")) is int and device["pid"] > 0, "native PID")
    require(type(device.get("enterpriseRootsInitiallyEnabled")) is bool, "initial trust setting")
    require(type(device.get("elapsedMs")) is int and 0 <= device["elapsedMs"] <= 150000, "bounded native execution")
    for phase in ("nativeOriginal", "nativeStrict", "nativeRestored"):
        validate_preferences(device.get(phase))
    original, strict, restored = (device[key] for key in ("nativeOriginal", "nativeStrict", "nativeRestored"))
    require(equal(original, restored), "real DEFAULT and USER branches must be restored exactly")
    for key in (MIN, MAX):
        require(strict[key] == dict(default=4, user=None, effective=4, hasUserValue=False), "native TLS1.3-only setting")
    require(original[MIN]["default"] <= 3 and original[MAX]["default"] >= 4, "original native TLS1.2/1.3 range")
    for key in PROTECTED:
        require(equal(original[key], strict[key]) and equal(original[key], restored[key]), "RFP/H2/H3 must remain unchanged")
    rows = device.get("observations")
    require(type(rows) is list and [row.get("trial") for row in rows] == [item[0] for item in TRIALS], "all four ordered native trials")
    for row, (name, port, version, success) in zip(rows, TRIALS):
        target = "https://" + HOSTS[0] + ":" + str(port) + "/tls-probe?run=" + run + "&source=" + source + "&trial=" + name
        require(row.get("target") == target and row.get("securityExceptionUsed") is False, "owned native target without TLS exception")
        require(all(type(row.get(key)) is bool for key in ("started", "located", "targetError", "leafVerified", "titleMatched", "nativeTargetTlsReady", "nativeStopOwnershipVerified")), "native callback Boolean types")
        require(row["nativeStopOwnershipVerified"] is False and all(type(row.get(key)) is int and 0 <= row[key] <= 64 for key in ("stopCallbacks", "successfulStopCallbacks")) and row["successfulStopCallbacks"] <= row["stopCallbacks"], "SDK stops have no URL and are diagnostic only")
        if success:
            require(row["started"] and row["located"] and row["leafVerified"] and row["titleMatched"] and row["nativeTargetTlsReady"] and row["targetError"] is False, "exact native target TLS leaf and nonce title required")
            require(row.get("secure") is True and row.get("leafSha256") == leaf and not any(key in row for key in ("errorCategory", "errorCode")), "exact native TLS leaf")
        else:
            # Actual constants from pinned Gecko157 SDK javap -constants: SSL=34, security category=2.
            require(row["targetError"] and row.get("nativeErrorUrlMatched") is True and not row["nativeTargetTlsReady"] and not row["titleMatched"] and not row["leafVerified"], "strict TLS1.2 must actually fail at exact native error URI")
            require(type(row.get("errorCategory")) is int and row["errorCategory"] == 2 and type(row.get("errorCode")) is int and row["errorCode"] == 34, "native TLS protocol error, not a timeout or certificate exception")
    return rows


def validate_wire(host, *, run, source):
    require(type(host) is dict and type(host.get("schema")) is int and host["schema"] == 1, "host schema")
    require(host.get("runNonce") == run and host.get("sourceCommit") == source, "wire run/source binding")
    for key in ("actualNativeWireCapture", "ticketsDisabled"):
        require(host.get(key) is True, "wire capture/fresh sessions")
    require(type(host.get("upstreamConnections")) is int and host["upstreamConnections"] == 0, "no upstream traffic")
    for key in ("forwardingImplemented", "privateMaterialExported", "certificateExceptionUsed", "h2OrH3PrefsModified", "recordsOverflow"):
        require(host.get(key) is False, "controlled loopback scope")
    records = host.get("records")
    require(type(records) is list and 4 <= len(records) <= 16, "bounded actual wire trials")
    randoms, offered, result = set(), None, {}
    require(set(row.get("trial") for row in records) == {item[0] for item in TRIALS}, "all four independent wire peers")
    for name, port, version, success in TRIALS:
        rows = [row for row in records if row.get("trial") == name]
        require(1 <= len(rows) <= 4, "bounded connections for " + name)
        completed = 0
        for row in rows:
            require(type(row.get("schema")) is int and row["schema"] == 1 and type(row.get("destinationPort")) is int and row["destinationPort"] == port
                    and row.get("serverOnlyVersion") == version and row.get("expectedSuccess") is success, "independent fixed peer mode")
            hello = row.get("clientHello")
            require(type(hello) is dict and hello.get("actualWireBytes") is True and type(hello.get("schema")) is int and hello["schema"] == 1, "actual ClientHello required")
            for key in ("clientHelloSha256", "clientRandomHex"):
                require(type(hello.get(key)) is str and re.fullmatch("[0-9a-f]{64}", hello[key]), "ClientHello wire hash/random")
            raw_hex=hello.get("clientHelloHandshakeHex")
            require(type(raw_hex) is str and 76 <= len(raw_hex) <= 131072 and len(raw_hex)%2==0 and re.fullmatch("[0-9a-f]+",raw_hex), "original bounded ClientHello bytes")
            raw=bytes.fromhex(raw_hex)
            hello_records=b"".join(b"\x16\x03\x01"+len(piece).to_bytes(2,"big")+piece for piece in (raw[i:i+16384] for i in range(0,len(raw),16384)))
            require(equal(parse_client_hello(hello_records),hello), "parsed ClientHello fields differ from original handshake bytes")
            require(hello["clientRandomHex"] not in randoms, "fresh independent ClientHello random required")
            randoms.add(hello["clientRandomHex"])
            require(hello.get("legacyVersion") == 0x0303 and type(hello["legacyVersion"]) is int and hello.get("serverNames") == [HOSTS[0]], "actual TLS SNI/legacy version")
            versions = hello.get("supportedVersions")
            require(type(versions) is list and 1 <= len(versions) <= 16 and all(type(item) is int and 0 <= item <= 65535 for item in versions) and len(versions) == len(set(versions)), "wire supported_versions")
            require(not ({0x0301, 0x0302} & set(versions)), "obsolete TLS1.0/1.1 must not be offered")
            require(0x0304 in versions and ((0x0303 not in versions) if name.startswith("strict-") else (0x0303 in versions)), "actual protocol restriction must appear on wire")
            require(hello.get("preSharedKeyOffered") is False, "resumed/PSK connection forbidden")
            alpn = hello.get("offeredAlpn")
            require(type(alpn) is list and "http/1.1" in alpn and "h2" in alpn and len(alpn) == len(set(alpn)) and all(type(item) is str for item in alpn), "native H2/HTTP1 ALPN offers remain available")
            if offered is None:
                offered = alpn
            require(equal(offered, alpn), "TLS protocol cap must not mutate ALPN offer")
            if success:
                require(row.get("tlsNegotiated") is True and row.get("negotiatedVersion") == version and row.get("negotiatedAlpn") == "http/1.1" and row.get("sessionReused") is False, "actual independent negotiated TLS/ALPN")
                require(row.get("httpReceived") is True and "errorType" not in row, "actual nonce-bound TLS HTTP request")
                completed += 1
            else:
                require(row.get("tlsNegotiated") is False and row.get("httpReceived") is False and row.get("errorType") == "SSLError"
                        and row.get("tlsErrorReason") == "UNSUPPORTED_PROTOCOL", "strict rejection requires actual protocol alert, not timeout")
        require(completed >= 1 if success else completed == 0, "actual TLS result incomplete")
        result[name] = dict(connections=len(rows), negotiatedVersion=version if success else None, protocolRejected=not success)
    return dict(trials=result, uniqueClientRandoms=len(randoms), offeredAlpn=offered,
                fullTlsFingerprintEmulation=False, quicWireVerified=False)


def validate_native_tls(device, host, *, run, source, tree, leaf):
    validate_device(device, run=run, source=source, tree=tree, leaf=leaf)
    return validate_wire(host, run=run, source=source)
