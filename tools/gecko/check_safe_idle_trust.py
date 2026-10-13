#!/usr/bin/env python3
"""Verify public test CA identity, NSS public-only store, and integration APK assets."""
import argparse
import hashlib
import json
import pathlib
import sqlite3
import subprocess
import tempfile
import zipfile

DIRECTORY = 'network-safe-idle-trust/'
LOCKED = {
    'root-ca.der': '794f38936cb5ebc28b6d0f681f9d5b00a2431f48ced181137f4f3bf45fe67226',
    'server-leaf.der': '66c659c8f20a9ea7d132d66e4020897be19fab099aa3cc17fa870a967c16266c',
    'cert9.db': 'a3114642d39ee1f3bc23c4428b08035abeb101de367547dcfe32680af6286023',
    'server.p12': '5fe7edd5f9b89854977cc3f6181faf8b38386eb03f4829ec9d39bd3cbfb6acc3',
}
ASSET_NAMES = sorted(set(LOCKED) | {'manifest.json', 'README.md'})


def verify_assets(root, integration_apk=None):
    root = pathlib.Path(root)
    folder = root / 'tests/gecko/assets' / DIRECTORY
    manifest_bytes = (folder / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest['schema'] == 1 and manifest['testOnly'] is True
    assert manifest['origin'] == 'https://chatgpt.com' and manifest['hostname'] == 'chatgpt.com'
    assert manifest['nssTrust'] == 'C,,' and manifest['caPrivateKeyPackaged'] is False
    assert set(manifest['files']) == set(LOCKED)
    assert {p.name for p in folder.iterdir()} == set(ASSET_NAMES)
    records = {}
    for name, expected in LOCKED.items():
        payload = (folder / name).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        assert digest == expected == manifest['files'][name]['sha256'], name
        assert len(payload) == manifest['files'][name]['bytes'], name
        records[name] = {'sha256': digest, 'bytes': len(payload)}
    # NSS SQL PKCS#11 public store: exactly one certificate object and one trust
    # object. CKA_NSS_TRUST_SERVER_AUTH is CKT_NSS_TRUSTED_DELEGATOR (C,,).
    with sqlite3.connect('file:' + str((folder / 'cert9.db').resolve()) + '?mode=ro', uri=True) as database:
        rows = database.execute('SELECT a0,a11,ace536358 FROM nssPublic').fetchall()
    assert len(rows) == 2
    certificate = [row for row in rows if row[0] == bytes.fromhex('00000001')]
    trust = [row for row in rows if row[0] == bytes.fromhex('ce534353')]
    assert len(certificate) == len(trust) == 1
    assert certificate[0][1] == (folder / 'root-ca.der').read_bytes()
    assert trust[0][2] == bytes.fromhex('ce534352')

    def openssl(*args):
        return subprocess.check_output(['openssl', *args], stderr=subprocess.PIPE)

    with tempfile.TemporaryDirectory(prefix='pocket-safe-idle-public-trust-') as temporary:
        temporary = pathlib.Path(temporary)
        ca, leaf = temporary / 'root.pem', temporary / 'leaf.pem'
        ca.write_bytes(openssl('x509', '-inform', 'DER', '-in', str(folder / 'root-ca.der'), '-outform', 'PEM'))
        leaf.write_bytes(openssl('x509', '-inform', 'DER', '-in', str(folder / 'server-leaf.der'), '-outform', 'PEM'))
        openssl('verify', '-CAfile', str(ca), '-check_ss_sig', str(ca))
        openssl('verify', '-CAfile', str(ca), '-verify_hostname', 'chatgpt.com', '-purpose', 'sslserver', str(leaf))
        packaged = temporary / 'packaged-leaf.pem'
        packaged.write_bytes(openssl('pkcs12', '-in', str(folder / 'server.p12'), '-passin', 'pass:network-safe-idle', '-clcerts', '-nokeys'))
        assert openssl('x509', '-in', str(packaged), '-outform', 'DER') == (folder / 'server-leaf.der').read_bytes()

    apk_sha = ''
    apk_assets = []
    if integration_apk is not None:
        integration_apk = pathlib.Path(integration_apk)
        with integration_apk.open('rb') as stream:
            apk_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        with zipfile.ZipFile(integration_apk) as archive:
            entries = [name.removeprefix('assets/' + DIRECTORY) for name in archive.namelist() if name.startswith('assets/' + DIRECTORY)]
            actual = set(entries)
            assert actual == set(ASSET_NAMES) and len(entries) == len(ASSET_NAMES)
            for name in actual:
                assert archive.read('assets/' + DIRECTORY + name) == (folder / name).read_bytes(), name
            apk_assets = sorted(actual)
    return {'status': 'passed', 'schema': 1, 'assetDirectory': DIRECTORY, 'hostname': 'chatgpt.com',
            'manifestSha256': hashlib.sha256(manifest_bytes).hexdigest(), 'files': records,
            'publicOnlyNssDatabase': True, 'nssServerCaTrustVerified': True, 'validCaSignedServerHostname': True,
            'pkcs12LeafMatchesSource': True, 'integrationApkAssetsVerified': integration_apk is not None,
            'integrationApkAssetNames': apk_assets, 'integrationApkAssetCount': len(apk_assets),
            'integrationApkSha256': apk_sha, 'actualAndroidExecution': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-apk', type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(verify_assets(pathlib.Path(__file__).resolve().parents[2], args.integration_apk), indent=2))
