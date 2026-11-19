"""Keep the Android 17 compatibility proof separate from the Android 13 release gate."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gecko import run_chromium_delivery as candidate
import chromium_release_publication as publication


class Api37CompatibilityTests(unittest.TestCase):
    source = {'sourceCommit': 'a' * 40, 'sourceTree': 'b' * 40, 'sourceDirty': False}
    provider = 'com.google.android.webview'

    def receipts(self, api37):
        host = dict(self.source, schema=1, package='local.pocketchat', status='passed', sdk=37 if api37 else 33,
                    versionCode=115, abi='x86_64', apkSet={'base': {'sha256': 'e' * 64},
                    'chromium': {'sha256': 'f' * 64}}, nativeSplit='chromium', nativeRenderer=False,
                    actualAndroidExecution=True, initWithoutChromium=True, appendInstall=True, baseDataRetained=True,
                    systemWebViewUnavailable=not api37, offlineRouteRejectedBeforeNativeInitialization=True,
                    runNonce='3' * 32, actualOnlineSignedMetadataDownload=False, actualSystemInstallerConsent=False,
                    testScope=candidate.API37_HOST_SCOPE if api37 else 'split-install-debug-candidate')
        fields = dict(scope='production-debug-synthetic-signing-local-content', package=host['package'],
                      runNonce=host['runNonce'], baseSha256='e' * 64, featureSha256='f' * 64,
                      versionCode=115, sdk=host['sdk'], abi='x86_64', nativeRenderers=2, chromiumVersion='156.0.8078.96')
        fields.update(dict.fromkeys(('androidExecution', 'localContentRendered', 'tlsFixtureVerified',
                      'defaultNetworkInitiallyPresent', 'defaultNetworkLost', 'chromiumBrowserRetired',
                      'navigationAfterLossWasBlocked'), 'true'))
        fields.update(dict.fromkeys(('publicNetworkRouteVerified', 'androidInstallerConfirmationVerified',
                      'vpnRouteVerified', 'internalRouteVerified', 'originTlsVerified'), 'false'))
        fields['noSystemWebViewProvider'] = 'false' if api37 else 'true'
        for name in ('protectedHttpProxy', 'protectedHttpsProxy', 'protectedSocksProxy'):
            fields.update({name + key: 'true' for key in ('Handshake', 'Rendered', 'Revoked', 'NoPrivateBypass')})
            fields.update({name + key: 1 for key in ('HandshakeCount', 'PageCount', 'HeldConnectionsClosed')})
            fields[name + 'PrivateTrapAccepted'] = 0
        fields['protectedHttpsProxyTlsHandshakeCount'] = 1
        if api37:
            host['systemWebViewProviderPackage'] = self.provider
            fields.update(scope=candidate.API37_INSTRUMENTATION_SCOPE,
                          systemWebViewProviderPackage=self.provider, webViewDisabledForTestProcess='true')
        return host, fields

    def join(self, host, fields, api37=False):
        transcript = ''.join(f'INSTRUMENTATION_RESULT: {key}={value}\n' for key, value in fields.items())
        transcript += 'INSTRUMENTATION_CODE: -1\n'
        with patch.object(candidate, 'source_state', return_value=self.source):
            return candidate.joined_report(host, transcript.encode(), api37_compatibility=api37)

    def test_standard_join_still_requires_system_webview_unavailable(self):
        host, fields = self.receipts(False)
        result = self.join(host, fields)
        self.assertEqual(result['testScope'], 'combined-debug-candidate-local-install-and-renderer')
        self.assertIs(result['systemWebViewUnavailable'], True)
        with self.assertRaises(ValueError):
            self.join(host, dict(fields, noSystemWebViewProvider='false'))

    def test_api37_join_binds_actual_provider_process_disable_and_same_renderer_checks(self):
        host, fields = self.receipts(True)
        result = self.join(host, fields, True)
        self.assertEqual(result['testScope'], candidate.API37_RENDER_SCOPE)
        self.assertEqual(result['systemWebViewProviderPackage'], self.provider)
        self.assertIs(result['webViewDisabledForTestProcess'], True)
        self.assertIs(result['systemWebViewUnavailable'], False)
        self.assertEqual(result['nativeRendererCount'], 2)
        self.assertEqual(result['protectedHttpsProxy']['tlsHandshakes'], 1)
        for changes in ({'webViewDisabledForTestProcess': 'false'}, {'systemWebViewProviderPackage': 'com.android.webview'},
                        {'noSystemWebViewProvider': 'true'}, {'sdk': 33}, {'nativeRenderers': 0},
                        {'protectedHttpProxyRevoked': 'false'}, {'navigationAfterLossWasBlocked': 'false'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.join(host, dict(fields, **changes), True)

    def test_compatibility_receipt_cannot_satisfy_standard_join_or_release_gate(self):
        host, fields = self.receipts(True)
        with self.assertRaises(ValueError):
            self.join(host, fields)
        with self.assertRaises(ValueError):
            self.join(dict(host, sdk=33), dict(fields, sdk=33), True)
        result = self.join(host, fields, True)
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder) / publication.RUNTIME_REPORT
            receipt.write_text(json.dumps(result))
            with self.assertRaises(ValueError):
                publication.runtime_summary(receipt, {'versionCode': 115}, self.source)

    def test_api37_offline_fixture_requires_real_enabled_stock_provider(self):
        device = candidate.Device(SimpleNamespace(api37_compatibility=True))
        webview = f'Current WebView package (name, version): ({self.provider}, 145.0.7632.218)'
        enabled = f'package:{self.provider}'
        with patch.object(device, 'shell', side_effect=[webview, enabled, '1', 'Active default network: none']):
            device.offline()
        self.assertEqual(device.webview_provider, self.provider)
        for replies in ([''], ['Current WebView package is null'], [webview, 'package:com.android.webview'],
                        [webview, enabled, '1', 'Active default network: 102']):
            with self.subTest(replies=replies), patch.object(device, 'shell', side_effect=replies), self.assertRaises(ValueError):
                device.offline()


if __name__ == '__main__':
    unittest.main()
