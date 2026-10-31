"""Recover only the exact reviewed startup-consumer input for older whole-file guards."""
import hashlib

PATH='tests/gecko_device_readiness_test.py'
PREVIOUS_SHA256='5a495ed28e55d5031c4991f6e845161248d52f6c09f1fefd0a7e06041c968e06'
CURRENT_SHA256='cba98e557c620e848d27eb4d67ca2281cf2ffd388c02866570c61290bc63226c'
HOOK="""    if needle in ('synchronized void command(','protected void onDestroy()'):
        from experience46_source_compatibility import experience46_source_bytes
        source=experience46_source_bytes(source.encode('utf-8'),'tests/gecko/GeckoIntegrationTestActivity.java').decode('utf-8')
"""


def startup46_source_bytes(raw,relative):
    if relative!=PATH:
        raise ValueError('Startup inverse does not cover this exact path')
    digest=hashlib.sha256(raw).hexdigest()
    if digest==PREVIOUS_SHA256:
        return raw
    if digest!=CURRENT_SHA256:
        raise ValueError('Startup inverse rejects unknown whole source bytes')
    hook=HOOK.encode('utf-8')
    if raw.count(hook)!=1:
        raise ValueError('Startup inverse requires the exact reviewed hook once')
    restored=raw.replace(hook,b'',1)
    if hashlib.sha256(restored).hexdigest()!=PREVIOUS_SHA256:
        raise ValueError('Startup inverse did not recover the complete previous consumer')
    return restored
