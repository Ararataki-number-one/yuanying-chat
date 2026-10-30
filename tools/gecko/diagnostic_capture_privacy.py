"""Pure, bounded diagnostic derivatives under the existing service-key policy.

These adapters never modify commands, browser settings or structured acceptance
evidence. Original hashes are provenance, not proof of discarded raw authenticity.
"""
import hashlib

if __package__:
    from .caret_ime_guard import redact_service_api_keys, verify_capture_privacy, PRIVACY_MAX_BYTES
else:
    from caret_ime_guard import redact_service_api_keys, verify_capture_privacy, PRIVACY_MAX_BYTES


def checked_text(value):
    """Return verified text plus the unchanged policy's complete-capture marker."""
    derivative, metadata = redact_service_api_keys(value)
    if not verify_capture_privacy(metadata, derivative):
        raise ValueError('Diagnostic capture privacy: invalid derivative metadata')
    return derivative, metadata


def checked_bytes(value):
    """Remove supported key spans while preserving every other captured byte.

    Latin-1 maps each input byte to exactly one code point. Existing helper
    markers hash the UTF-8 encoding of that projection; the outer marker hashes
    actual original and stored byte sequences. They are intentionally distinct.
    The unchanged helper bounds apply before any derivative is returned.
    """
    if not isinstance(value, bytes) or len(value) > PRIVACY_MAX_BYTES:
        raise ValueError('Diagnostic capture privacy: original bytes required')
    projection, privacy = checked_text(value.decode('latin1'))
    derivative = projection.encode('latin1')
    metadata = dict(schema=1, kind='service-key-byte-derivative',
                    originalBytes=len(value), originalSha256=hashlib.sha256(value).hexdigest(),
                    projectionEncoding='latin1', helperHashEncoding='utf-8', projectionPrivacy=privacy,
                    storedBytes=len(derivative), storedSha256=hashlib.sha256(derivative).hexdigest(),
                    changed=derivative != value)
    return derivative, metadata


def safe_error_text(error, *, use_repr=True):
    """Keep public secondary errors bounded without replacing a live failure."""
    try:
        return checked_text(repr(error) if use_repr else str(error))[0]
    except Exception:
        return 'Diagnostic error text unavailable'
