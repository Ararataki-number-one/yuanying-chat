#!/usr/bin/env python3
"""Require source-bound host and Android model evidence; keep SDK prototypes diagnostic."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HOST_GROUPS = {
    'NetworkHealthPolicyTest', 'NetworkStatusPolicyTest', 'NetworkPoolIdentityTest',
    'LatencyProbePolicyTest', 'EnvironmentSpecTest', 'network-catalog-host',
    'network-source-host', 'network-lineage-host', 'sealed-file-host', 'environment-intent-host',
}
MIN_HOST_COUNTS = {'NetworkHealthPolicyTest':52,'NetworkStatusPolicyTest':16,
    'NetworkPoolIdentityTest':54,'LatencyProbePolicyTest':70,'EnvironmentSpecTest':102,
    'network-catalog-host':113,'network-source-host':94,'network-lineage-host':26,
    'sealed-file-host':32,'environment-intent-host':75}
MODEL_INPUTS = {
    'EnvironmentSpec', 'EnvironmentSpecMigration', 'EnvironmentSpecRepository',
    'EnvironmentSpecRuntime', 'EnvironmentApplyCoordinator', 'ProfileCatalog',
    'NativeNetwork', 'NetworkHealthPolicy', 'NetworkStatusPolicy', 'NetworkUiProvider',
    'NetworkChanges', 'NetworkCatalog', 'NetworkSourceSelection', 'SealedFileIo',
}


def source_bytes(source, path):
    return subprocess.check_output(['git', 'show', source + ':' + path], cwd=ROOT)


def verify_profile_evidence(directory, source):
    directory = Path(directory)
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('Exact source commit is required')
    tree = subprocess.check_output(['git', 'rev-parse', source + '^{tree}'], cwd=ROOT, text=True).strip()
    settings=source_bytes(source,'app/build.gradle').decode()
    version=re.search(r"versionName '([^']+)'",settings).group(1)
    version_code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
    runner_path = Path(__file__).with_name('profile_invocation_contract.py')
    if runner_path.read_bytes() != source_bytes(source, 'tools/gecko/profile_invocation_contract.py'):
        raise ValueError('Fixture contract differs from selected source')
    spec = importlib.util.spec_from_file_location('selected_profile_contract', runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    host = json.loads((directory / 'profile-host-results.json').read_text())
    if host.get('status') != 'passed' or host.get('actualAndroidExecution') is not False or host.get('sourceDirty') is not False or host.get('sourceCommit') != source or host.get('sourceTree') != tree:
        raise ValueError('A clean, exact-source host report is required')
    groups = host.get('results', [])
    by_name = {group.get('test'): group for group in groups}
    if len(by_name) != len(groups) or not HOST_GROUPS.issubset(by_name):
        raise ValueError('Every model, intent and existing network host group is required')
    counts = {}
    for name in HOST_GROUPS:
        group = by_name[name]
        if name.endswith('-host'):
            receipt_path = directory / Path(group.get('report', '')).name
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('actualAndroidExecution') is not False or receipt.get('passed') != group.get('passed'):
                raise ValueError('Host receipt disagrees with profile execution: ' + name)
            count = receipt.get('passed')
            if name=='environment-intent-host':
                expected_names=re.findall(r'(?:check|rejects)\("([^"\n]+)"',source_bytes(source,'tests/environment-intent-host/local/pocketchat/EnvironmentIntentHostTest.java').decode())
                checks=receipt.get('checks',[])
                actual_names=[row.get('name') for row in checks]
                if receipt.get('status')!='passed' or receipt.get('total')!=len(expected_names) or receipt.get('executed')!=len(expected_names) or count!=len(expected_names) or actual_names!=expected_names or len(set(actual_names))!=len(actual_names) or any(row.get('pass') is not True for row in checks) or receipt.get('actualCrossProcessIntentLease') is not True:
                    raise ValueError('Every exact source intent host assertion and cross-process lease must pass')
                for path,digest in receipt.get('files',{}).items():
                    if '..' in Path(path).parts or Path(path).is_absolute() or hashlib.sha256(source_bytes(source,path)).hexdigest()!=digest:
                        raise ValueError('Intent host inputs changed from selected source')
        else:
            if group.get('exitCode') != 0:
                raise ValueError('Host policy execution failed: ' + name)
            count = json.loads(group.get('output', '{}')).get('passed')
        if type(count) is not int or count < MIN_HOST_COUNTS[name]:
            raise ValueError('Host assertions are missing: ' + name)
        counts[name] = count
    hashes = host.get('files', {})
    mandatory = {'app/src/main/java/local/pocketchat/' + name + '.java' for name in MODEL_INPUTS}
    if not mandatory.issubset(hashes):
        raise ValueError('Host report omits model or network production inputs')
    for path, digest in hashes.items():
        if not isinstance(path, str) or '..' in Path(path).parts or Path(path).is_absolute() or not re.fullmatch('[0-9a-f]{64}', str(digest)):
            raise ValueError('Invalid host source hash record')
        if hashlib.sha256(source_bytes(source, path)).hexdigest() != digest:
            raise ValueError('Host execution source hash changed: ' + path)
    android = {}
    identities = []
    for name in ('environment-spec', 'environment-intent', 'gecko-identity-prototype'):
        report_path = directory / (name + '-results.json')
        raw = report_path.read_bytes()
        report = json.loads(raw)
        log = json.loads((directory / (name + '-runner-log.json')).read_text())
        identity = log.get('buildIdentity', {})
        if log.get('status') != 'passed' or log.get('sourceCommit') != source or log.get('installedBeforeAndAfterMatched') is not True or log.get('rawReportPreserved') is not True or log.get('reportSha256') != hashlib.sha256(raw).hexdigest() or log.get('reportBytes') != len(raw):
            raise ValueError('Raw Android report or verified invocation changed: ' + name)
        if identity.get('sourceCommit') != source or identity.get('sourceTree') != tree or identity.get('dirtySource') is not False:
            raise ValueError('Android installation is bound to another source: ' + name)
        if identity.get('schema')!=1 or identity.get('package')!='local.pocketchat.test' or identity.get('version')!=version or identity.get('versionCode')!=version_code or identity.get('sdkCoordinate')!='org.mozilla.geckoview:geckoview:157.0.20261005135250':
            raise ValueError('Android build identity does not match this version and official SDK')
        if type(identity.get('apkBytes')) is not int or identity['apkBytes']<=0 or not re.fullmatch('[0-9a-f]{64}',str(identity.get('apkSha256',''))) or not re.fullmatch('[0-9a-f]{64}',str(identity.get('buildStampSha256',''))):
            raise ValueError('Actual installed APK byte identity is incomplete')
        runner.verify_invocation(report, identity, log.get('runNonce', ''))
        runner.verify(report, 1, True)
        if report.get('androidSdk') != log.get('androidSdk') or type(report.get('androidSdk')) is not int or report['androidSdk'] < 26:
            raise ValueError('Android SDK observation disagrees: ' + name)
        identities.append(identity)
        android[name] = report['passed']
        if name == 'environment-spec':
            expected_names = re.findall(r'(?:check|rejects)\("([^"\n]+)"', source_bytes(source, 'tests/gecko/EnvironmentSpecIntegrationActivity.java').decode())
            actual_names = [check.get('name') for check in report['checks']]
            if actual_names != expected_names or len(actual_names) < 20:
                raise ValueError('Actual environment model checks differ from selected source')
            if report.get('syntheticAcknowledgementsOnly') is not True or report.get('realAccountLogin') is not False or report.get('webpageFingerprintAcceptance') is not False:
                raise ValueError('Model persistence must not claim real browser acceptance')
        elif name == 'gecko-identity-prototype':
            runner.verify_diagnostic(report)
            if log.get('diagnosticOnly') is not True:
                raise ValueError('Prototype runner lost its diagnostic boundary')
            engine_version=re.search(r'static final String VERSION="([^"]+)"',source_bytes(source,'app/src/main/java/local/pocketchat/GeckoWebView.java').decode()).group(1)
            if report.get('sdkCoordinate')!='org.mozilla.geckoview:geckoview:157.0.20261005135250' or report.get('sdkAarSha256')!='15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268' or report.get('engineVersion')!=engine_version:
                raise ValueError('Diagnostic prototype must identify the unchanged pinned official engine')
        elif name=='environment-intent':
            expected_names=re.findall(r'(?:check|rejects)\("([^"\n]+)"',source_bytes(source,'tests/gecko/EnvironmentIntentIntegrationActivity.java').decode())
            actual_names=[row.get('name') for row in report['checks']]
            if actual_names!=expected_names or len(set(actual_names))!=len(actual_names) or report.get('executed')!=len(expected_names) or report.get('total')!=len(expected_names) or len(expected_names)<43:
                raise ValueError('Actual Android intent recovery checks differ from selected source')
    if any(identity != identities[0] for identity in identities[1:]):
        raise ValueError('Model and prototype fixtures used different installed APKs')
    return {'status': 'passed', 'sourceCommit': source, 'sourceTree': tree,
            'actualAndroidExecution': True, 'hostCounts': counts, 'androidCounts': android,
            'sourceHashCount': len(hashes), 'apkSha256': identities[0]['apkSha256'],
            'scope': 'Synthetic environment migration and authoritative intent recovery; SDK prototype diagnostic only',
            'realAccountLogin': False, 'fingerprintTemplateAcceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_profile_evidence(args.directory, args.source), indent=2))
