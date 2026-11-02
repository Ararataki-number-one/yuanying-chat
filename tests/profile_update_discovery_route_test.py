"""Historical route evidence plus synthetic discovery-ledger controls; no Android run."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = load('channel_route_contract', ROOT/'tools/gecko/update_route_contract.py')
fixture = load('channel_route_fixture', ROOT/'tests/gecko/run_update_route.py')


class DiscoveryRouteControls(unittest.TestCase):
    def setUp(self):
        self.old = json.loads((ROOT/'verification/chain-performance-v1.5.20/update-route-results.json').read_text())
        self.source = self.old['sourceCommit']
        self.core = self.old['initialProfiles'][0]['coreSha256']

    def modern(self):
        report = copy.deepcopy(self.old)
        report['updateDiscovery'] = 'release-catalog-v1'
        api = 'https://api.github.com/repos/Ararataki-number-one/yuanying-chat/releases?per_page=50&page=1'
        manifest = 'https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v99.0.0-gecko/release-manifest.json'
        first = report['opens'][0]
        report['opens'] = [dict(first, officialUrl=api), dict(first, officialUrl=manifest), *report['opens'][1:]]
        wire = []
        for row in report['serverTrace']:
            if row['path'] == '/feed':
                wire += [dict(row, path='/catalogue'), dict(row, path='/manifest')]
            else:
                wire.append(row)
        report['serverTrace'] = wire
        return report

    def verify(self, report):
        return contract.verify_update_route(report, self.source, self.core)

    def test_historical_single_feed_keeps_its_complete_original_contract(self):
        self.assertEqual(self.verify(self.old)['selectedSlot'], 7)

    def test_new_discovery_requires_both_metadata_hops_before_identical_apk_resume(self):
        report = self.modern()
        result = self.verify(report)
        self.assertEqual(result['invalidations'], 8)
        self.assertEqual(result['internalDirectFallbackCalls'], 0)
        self.assertEqual(result['signedArchiveBytes'], self.old['verifiedArchive']['bytes'])

    def test_missing_marker_wrong_repository_or_manifest_cannot_use_legacy_path(self):
        for mutation in ('missing', 'unknown', 'repository', 'manifest', 'order', 'extra'):
            with self.subTest(mutation=mutation):
                report = self.modern()
                if mutation == 'missing':
                    report.pop('updateDiscovery')
                elif mutation == 'unknown':
                    report['updateDiscovery'] = 'unrecognized'
                elif mutation == 'repository':
                    report['opens'][0]['officialUrl'] = report['opens'][0]['officialUrl'].replace('yuanying-chat', 'another-app')
                elif mutation == 'manifest':
                    report['opens'][1]['officialUrl'] = report['opens'][1]['officialUrl'].replace('v99.0.0-gecko', 'v99.0.0-candidate1-gecko')
                elif mutation == 'order':
                    report['opens'][0], report['opens'][1] = report['opens'][1], report['opens'][0]
                else:
                    report['opens'].append(copy.deepcopy(report['opens'][0]))
                with self.assertRaises(AssertionError):
                    self.verify(report)

    def test_incomplete_metadata_credentials_or_direct_fallback_still_fail(self):
        for mutation in ('incomplete', 'credentials', 'direct', 'port', 'resume'):
            with self.subTest(mutation=mutation):
                report = self.modern()
                if mutation == 'incomplete':
                    report['serverTrace'][0]['completed'] = False
                elif mutation == 'credentials':
                    report['serverTrace'][0]['personalCredentialsSeen'] = True
                elif mutation == 'direct':
                    report['internalDirectFallbackCalls'] = 1
                elif mutation == 'port':
                    report['opens'][0]['port'] = -1
                else:
                    next(row for row in report['serverTrace'] if row['path'] == '/update-route.apk' and row['range'])['range'] = 'bytes=0-'
                with self.assertRaises(AssertionError):
                    self.verify(report)

    def test_fixture_catalogue_and_manifest_bind_the_same_synthetic_archive(self):
        url = 'https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v99.0.0-gecko/PocketChat-99.0.0-gecko-arm64.apk'
        metadata = dict(version='99.0.0', downloadUrl=url, sha256='a'*64, bytes=1234567)
        catalogue, manifest = fixture.discovery_fixture(metadata)
        self.assertEqual(catalogue[0]['assets'][1]['browser_download_url'], manifest['downloadUrl'])
        self.assertEqual(manifest['sha256'], metadata['sha256'])
        self.assertEqual(manifest['filename'], 'PocketChat-99.0.0-gecko-arm64.apk')
        with self.assertRaises(AssertionError):
            fixture.discovery_fixture(dict(metadata, downloadUrl='https://example.invalid/app.apk'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
