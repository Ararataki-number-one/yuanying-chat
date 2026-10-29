#!/usr/bin/env python3
"""Production download route lease with controlled Android/service/connection adapters."""
import hashlib, importlib.util, json, os, pathlib, shutil, subprocess, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'
HERE = ROOT / 'tests/native-download-route-host'
spec = importlib.util.spec_from_file_location('download_route_members', ROOT / 'tests/download-resume-host/run.py')
members = importlib.util.module_from_spec(spec)
spec.loader.exec_module(members)


class NativeDownloadRouteTests(unittest.TestCase):
    def test_production_route_lease_and_inflight_revocation(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'Java 17 required')
        jar = next((pathlib.Path(p) for p in (os.environ.get('PROFILE_JSON_JAR', ''), str(ROOT / 'work/profile-host/json.jar')) if p and pathlib.Path(p).is_file()), None)
        self.assertIsNotNone(jar, 'Existing host JSON dependency required')
        guard = (SOURCE / 'BrowserNetworkGuard.java').read_text()
        native = (SOURCE / 'NativeNetwork.java').read_text()
        downloads = (SOURCE / 'FileDownloads.java').read_text()
        selected = {
            'GUARD_ROUTE': members.member(guard, 'boolean routeProtected()'),
            'GUARD_ALLOWED': members.member(guard, 'boolean allowed()'),
            'DOWNLOAD_ROUTE': members.member(downloads, 'Proxy route()'),
            'RECEIPT': members.member(native, 'static final class ExitRouteReceipt'),
            'INVALIDATE': members.member(native, 'void invalidateVerifiedRoute()'),
            'ADMISSION': members.member(native, 'NetworkHealthPolicy.Admission connectionAdmission()'),
            'CURRENT': members.member(native, 'boolean verifiedRouteCurrent()'),
            'CLOSER': members.member((SOURCE / 'AppUpdateTransfer.java').read_text(), 'static void disconnectLater('),
        }
        files = [SOURCE / name for name in ('NativeDownloadRoute.java', 'NetworkPoolIdentity.java', 'NetworkHealthPolicy.java', 'EnvironmentSpec.java', 'AppUpdateTransfer.java', 'BrowserNetworkGuard.java', 'NativeNetwork.java', 'FileDownloads.java')]
        files += [HERE / 'NativeDownloadRouteHost.java.in', pathlib.Path(__file__), ROOT / 'tests/download-resume-host/run.py'] + sorted((HERE / 'android').rglob('*.java'))
        hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        with tempfile.TemporaryDirectory(prefix='native-download-route-host-') as directory:
            temp = pathlib.Path(directory)
            package = temp / 'local/pocketchat'
            package.mkdir(parents=True)
            for name in ('NativeDownloadRoute.java', 'NetworkPoolIdentity.java', 'NetworkHealthPolicy.java', 'EnvironmentSpec.java'):
                (package / name).write_bytes((SOURCE / name).read_bytes())
            template = (HERE / 'NativeDownloadRouteHost.java.in').read_text()
            for marker, text in selected.items():
                self.assertEqual(template.count('/* ' + marker + ' */'), 1)
                template = template.replace('/* ' + marker + ' */', text)
            (package / 'NativeDownloadRouteHost.java').write_text(template)
            inputs = list(package.glob('*.java')) + sorted((HERE / 'android').rglob('*.java'))
            build = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(temp), *map(str, inputs)], capture_output=True, text=True, timeout=40)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([java, '-cp', str(temp) + os.pathsep + str(jar), 'local.pocketchat.NativeDownloadRouteHost'], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            report = json.loads(run.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['passed'], report['total'])
            self.assertEqual(report['total'], 51)
            self.assertEqual(len(report['checks']), len({item['name'] for item in report['checks']}))
            self.assertTrue(all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items()))
            report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), sourceFiles=hashes, selectedMethodsSha256={k: hashlib.sha256(v.encode()).hexdigest() for k, v in selected.items()}, executionInputsUnchanged=True, actualAndroidExecution=False, actualGeckoExecution=False, actualNetworkExecution=False, actualPhoneExecution=False, scope='Complete production NativeDownloadRoute, NetworkPoolIdentity and NetworkHealthPolicy, exact existing guard/download/admission/receipt methods; controlled Android, catalog, IPC and HTTP connection doubles with real JVM watcher threads. No actual Android, VPN, sockets, leakage, SQLite or phone acceptance.')
            target = pathlib.Path(os.environ.get('NATIVE_DOWNLOAD_ROUTE_HOST_REPORT') or ROOT / 'work/profile-host/native-download-route-results.json')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def test_production_stream_uses_one_frozen_attempt_and_preserves_partial(self):
        text = (SOURCE / 'FileDownloads.java').read_text()
        method = members.member(text, 'void download(')
        self.assertEqual(method.count('new NativeDownloadRoute(a.session,route())'), 1)
        self.assertIn('try(NativeDownloadRoute frozen=', method)
        self.assertIn('frozen.open(url,this::connect)', method)
        self.assertIn('frozen.check();int code=c.getResponseCode();frozen.check();', method)
        self.assertIn('while((size=in.read(bytes))!=-1){frozen.check();', method)
        self.assertIn('finally{frozen.released(c);c.disconnect();', method)
        catch = method[method.rindex('}catch(Exception e)'):]
        self.assertNotIn('delete(', catch)
        self.assertNotIn('download(', catch)
        self.assertNotIn('Proxy.NO_PROXY', method)
        self.assertNotIn('connect(url,proxy)', method)


if __name__ == '__main__':
    unittest.main()
