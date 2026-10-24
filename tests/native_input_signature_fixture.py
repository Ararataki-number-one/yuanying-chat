"""Synthetic host inputs for signature evidence parsers; never cryptographic proof."""
import hashlib
import json


def signature_files(build, verifier_sha):
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    certificate = build['signerCertificateSha256']
    build['signatureVerifierSourceSha256'] = verifier_sha
    build['toolchain'] = dict(buildTools='37.0.0', tools={'apksignerJar': dict(path='synthetic/apksigner.jar', sha256='9' * 64)})
    cli = {'native-input-driver-signature-stdout.log': ('Verifies\nNumber of signers: 1\nV3.0 Signer: certificate SHA-256 digest: ' + certificate + '\n').encode(),
           'native-input-driver-signature-stderr.log': b''}
    value = dict(schema=1, status='passed', verified=True, containsErrors=False, error='',
                 **{key: build[key] for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'apkSha256', 'apkBytes', 'signerCertificateSha256')},
                 apksignerJarSha256='9' * 64, verifierSourceSha256=verifier_sha,
                 loadedApksignerJarPath='synthetic/apksigner.jar', inputsUnchangedDuringVerification=True,
                 effectiveSignerCertificateSha256=[certificate], lineagePresent=False,
                 lineageCertificateSha256=[], ignoredV1SignerCertificateSha256=[], noRotation=True, v32Detected=False,
                 schemes=[dict(name=name, verified=name in ('v2', 'v3'), signerCertificateSha256=[certificate] if name in ('v2', 'v3') else [],
                               signers=[dict(certificateSha256=certificate, certificateChainSha256=[certificate],
                                             containsErrors=False, lineagePresent=False, lineageCertificateSha256=[],
                                             rotationTargetsDevRelease=False, signerTargetsDevRelease=False)]
                                       if name in ('v2', 'v3') else [])
                          for name in ('v1', 'v2', 'v3', 'v31', 'v4')])
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    api = {'native-input-driver-signature-api-stdout.log': raw, 'native-input-driver-signature-api-stderr.log': b''}
    build.update(signatureApiSha256=digest(raw), signatureLogs={name:digest(data) for name,data in cli.items()},
                 signatureApiLogs={name:digest(data) for name,data in api.items()}, signatureCliReturnCode=0, signatureApiReturnCode=0)
    return {**cli, **api, 'native-input-driver-signature-api.json': raw}
