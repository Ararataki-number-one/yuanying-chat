"""Public certificate identities and dates for the existing ephemeral TLS peers."""
import hashlib
import ssl
import time
from fingerprint_fixture_server import certificate_validity_ms


def fixture_trust_input(certificates):
    """No private bytes, additional certificate, request or trust-store mutation."""
    ca = ssl.PEM_cert_to_DER_cert(certificates.ca.read_text('ascii'))
    leaf = ssl.PEM_cert_to_DER_cert(certificates.leaf.read_text('ascii'))
    result = dict(caPemSha256=certificates.ca_sha,
                  caDerSha256=hashlib.sha256(ca).hexdigest(),
                  leafDerSha256=hashlib.sha256(leaf).hexdigest())
    if result['leafDerSha256'] != certificates.leaf_sha:
        raise ValueError('Fixture trust public leaf differs')
    for prefix, path in (('ca', certificates.ca), ('leaf', certificates.leaf)):
        result[prefix+'NotBeforeMs'], result[prefix+'NotAfterMs'] = certificate_validity_ms(path)
    result['hostUtcMs'] = int(time.time()*1000)
    return result
