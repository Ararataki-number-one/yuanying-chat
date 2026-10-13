Public synthetic trust fixtures for the SafeIdle integration Activity only.

`root-ca.der` is a self-signed CA constrained to DNS `chatgpt.com`.
`server-leaf.der` is its valid server certificate with SAN `chatgpt.com`.
`server.p12` contains the synthetic server key and the leaf/CA chain; its public
test password is `network-safe-idle`. The CA private generation key is not retained
or packaged. None of these keys may be used for real services or release signing.

`cert9.db` is an NSS SQL public certificate database generated with the official
NSS `certutil -N --empty-password` and `certutil -A -t 'C,,'`. Its only records are
the public CA certificate and server trust. No `key4.db`, `pkcs11.txt` or private
CA key is packaged. The Activity verifies source hashes and copies this database
to its fresh, isolated existing Gecko `-profile` directory before runtime creation.
It refuses to replace an existing profile database. The ordinary Gecko certificate
verifier, HSTS and production extension remain enabled.

The official native security callback must report a secure non-exception page at
`chatgpt.com`, with the exact server certificate signed by this public CA, before
the original real-gesture/observer checks may run. The CONNECT server allows only
that domain and forwards exclusively to its recorded loopback TLS port.

All files live in the integration-only asset source set. A production APK must
not include any `assets/network-safe-idle-trust/` entry. See `manifest.json` for
the frozen public certificate/database hashes and `tools/gecko/check_safe_idle_trust.py`
for independent host identity and APK source-set checks.
