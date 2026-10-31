"""Generated-key controls for public diagnostic derivatives, never phone evidence.

Only fake child processes and mocked external runner edges execute. The original
raw/timeout fixture and its acceptance assertions remain unchanged.
"""
import ast
import copy
import textwrap
import types
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests'), str(ROOT / 'tests/gecko')]
from tools.gecko import diagnostic_capture_privacy as P
from tools.gecko import caret_ime_guard as G
import gecko_source_route_logcat_test as HOST
import network_settings_internal46_contract as INTERNAL46

RUNNER = HOST.RUNNER
ROUTE = ROOT / 'tests/gecko/run_network_sources_route.py'
PREVIOUS_RUNNER_SHA256 = '5abc798d2d8fe8357bbc4e2625b98d411e836c857fa7597eb1462d276626efe5'
CHANGES = (('from tools.gecko.network_sources_contract import verify_source_route as verify\n', 'from tools.gecko.network_sources_contract import verify_source_route as verify\nfrom tools.gecko.diagnostic_capture_privacy import checked_text, checked_bytes, safe_error_text\n'), ('def capture_logcat(adb_path, serial, filters=(), stem=\'network-source-route-logcat\', check=True):\n    """Preserve original log bytes; decoded text is diagnostic display only."""\n    command=[adb_path,\'-s\',serial,\'logcat\',\'-d\',*filters]\n    def save(stdout, stderr, returncode, timed_out=False):\n        streams={}\n        for label, raw in ((\'stdout\',stdout or b\'\'),(\'stderr\',stderr or b\'\')):\n            (OUT/(stem+\'-\'+label+\'.raw.log\')).write_bytes(raw)\n            invalid=None\n            try:raw.decode(\'utf-8\',errors=\'strict\')\n            except UnicodeDecodeError as error:invalid=dict(start=error.start,end=error.end,reason=error.reason)\n            streams[label]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),invalidUtf8=invalid)\n        display=(stdout or b\'\').decode(\'utf-8\',errors=\'backslashreplace\')\n        (OUT/(stem+\'-display.txt\')).write_text(display,encoding=\'utf-8\')\n        (OUT/(stem+\'-decode.json\')).write_text(json.dumps(dict(schema=1,scope=\'Diagnostic display only; never structured acceptance evidence\',encoding=\'utf-8\',errors=\'backslashreplace\',returncode=returncode,timedOut=timed_out,streams=streams),indent=2)+\'\\n\',encoding=\'utf-8\')\n        return display\n    try:result=subprocess.run(command,capture_output=True,timeout=30,check=False)\n    except subprocess.TimeoutExpired as error:\n        save(error.stdout,error.stderr,None,True)\n        raise\n    display=save(result.stdout,result.stderr,result.returncode)\n    if check and result.returncode:raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)\n    return display', 'def capture_logcat(adb_path, serial, filters=(), stem=\'network-source-route-logcat\', check=True):\n    """Preserve non-key log bytes in explicitly verified diagnostic derivatives."""\n    command=[adb_path,\'-s\',serial,\'logcat\',\'-d\',*filters]\n    def save(stdout, stderr, returncode, timed_out=False):\n        streams={};privacy_streams={}\n        for label, raw in ((\'stdout\',stdout or b\'\'),(\'stderr\',stderr or b\'\')):\n            stored,privacy_streams[label]=checked_bytes(raw)\n            (OUT/(stem+\'-\'+label+\'.raw.log\')).write_bytes(stored)\n            invalid=None\n            try:raw.decode(\'utf-8\',errors=\'strict\')\n            except UnicodeDecodeError as error:invalid=dict(start=error.start,end=error.end,reason=error.reason)\n            streams[label]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),invalidUtf8=invalid)\n        display,display_privacy=checked_text((stdout or b\'\').decode(\'utf-8\',errors=\'backslashreplace\'))\n        (OUT/(stem+\'-display.txt\')).write_text(display,encoding=\'utf-8\')\n        capture_privacy=dict(schema=1,scope=\'streams describe original captured bytes; public *.raw.log files are byte derivatives. Projection helper hashes use UTF-8 of the Latin-1 byte map; stored hashes describe actual public bytes.\',\n                             byteStreams=privacy_streams,displayPrivacy=display_privacy)\n        (OUT/(stem+\'-decode.json\')).write_text(json.dumps(dict(schema=1,scope=\'Diagnostic display only; never structured acceptance evidence\',encoding=\'utf-8\',errors=\'backslashreplace\',returncode=returncode,timedOut=timed_out,streams=streams,capturePrivacy=capture_privacy),indent=2)+\'\\n\',encoding=\'utf-8\')\n        return display\n    try:result=subprocess.run(command,capture_output=True,timeout=30,check=False)\n    except subprocess.TimeoutExpired as error:\n        try:save(error.stdout,error.stderr,None,True)\n        except Exception:pass  # Diagnostic capture failure cannot replace the original timeout.\n        raise\n    display=save(result.stdout,result.stderr,result.returncode)\n    if check and result.returncode:raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)\n    return display'), ("    except Exception as error:failures.append(dict(stage='server-copy',error=repr(error)))\n", "    except Exception as error:failures.append(dict(stage='server-copy',error=safe_error_text(error)))\n"), ("    except Exception as error:failures.append(dict(stage='logcat',error=repr(error)))\n", "    except Exception as error:failures.append(dict(stage='logcat',error=safe_error_text(error)))\n"))


def original_route_runner(text):
    for previous, added in CHANGES:
        if text.count(added) != 1:
            raise ValueError('Missing or repeated exact route diagnostic addition')
        text = text.replace(added, previous, 1)
    return text


def key(letter='g'):
    return ('AIza' + letter * 35).encode()


def service_bytes():
    return (b'expressive_stickers_api_key=' + key() + b'\n'
            b'https://location.services.mozilla.com/v1/country?key=' + b'm' * 36 + b'&kept=1\n'
            b'https://safebrowsing.googleapis.com/v5/hashLists:batchGet?key=' + key('s') + b'&alt=json\n'
            b'unknown-setting=' + key('u') + b'\n')


def expected_plain(raw):
    for token in [key(), b'm' * 36, key('s'), key('u')]:
        raw = raw.replace(token, G.PRIVACY_REPLACEMENT.encode())
    return raw


PRODUCER_PINS = {'tests/gecko/run_network_safe_idle.py': '8b777674aed1c08a216275d7b003b3d08cd0201433f2e55b69d856641ae4a667', 'tests/gecko/run_network_settings_application.py': '43b323bd5ef52b3a61e9ce41cdd494e193e87e9be0a906bfc03063be516ea5fd', 'tests/gecko/run_network_settings_retry.py': 'ae038679cc3f572171abe8447d18283e57d6fac2a54f6b90387f47009ef9fc4c', 'tests/gecko/run_network_settings_internal.py': '712b56594256858664e3549b4113fdd8987939743088bca96ed73b743f1a3a4f', 'tests/gecko/run_ui_fixes.py': '78f1db17e34815cc8bff07d566268eb4924c652d70cde5ad60c7b6fc3bc53b4f', 'tests/gecko/run_native_probe.py': '4d049a44ddf286b4c0b263f747058565581432853dc9ef87a30e4fbf5e4fd50f', 'tests/gecko/run_network_client_binding.py': '152e2610a2435e335461c961e1c6b519616fc08ddda24511326e33bdad144c71', 'tests/gecko/run_appearance_web.py': '39a4a3d845d0d02dd7cf3b271a04dc04bfed50b8f8580238057e1ef219b4ed6b'}
PRODUCER_HUNKS = {'tests/gecko/run_network_safe_idle.py': (('ROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / "tools"))\nfrom gecko.network_sources_contract import verify_safe_idle as verify\nOUT = ROOT / "work/gecko-integration"\nOUT.mkdir(parents=True, exist_ok=True)\nPKG = "local.pocketchat.test"\n', 'ROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / "tools"))\nfrom gecko.network_sources_contract import verify_safe_idle as verify\nfrom gecko.diagnostic_capture_privacy import checked_text, safe_error_text\n# Stored diagnostic text is a verified service-key derivative.\nOUT = ROOT / "work/gecko-integration"\nOUT.mkdir(parents=True, exist_ok=True)\nPKG = "local.pocketchat.test"\n'), ('\n\ndef events():\n    raw = adb("logcat", "-d", "-s", "PocketNetworkSafeIdle:I", "AndroidRuntime:E", "*:S")\n    if "FATAL EXCEPTION" in raw:\n        raise AssertionError(raw)\n    found = []\n', '\n\ndef events():\n    raw = checked_text(adb("logcat", "-d", "-s", "PocketNetworkSafeIdle:I", "AndroidRuntime:E", "*:S"))[0]\n    if "FATAL EXCEPTION" in raw:\n        raise AssertionError(raw)\n    found = []\n'), ('    assert report["coreSha256"] == receipt["binaries"]["x86_64"]["sha256"]\n    verify(report)\n    (OUT / "network-safe-idle-final.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))\n    (OUT / "network-safe-idle-log.txt").write_text(adb("logcat", "-d"))\n    print(json.dumps({"status": "passed", "checkCount": report["checkCount"], "cases": len(report["cases"]), "realTrustedGestures": len(GESTURES), "report": str(OUT / "network-safe-idle-results.json")}))\nexcept BaseException as error:\n    failure = {"status": "failed", "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "error": str(error), "events": EVENTS, "gestures": GESTURES}\n    terminal = next((e["value"] for e in reversed(EVENTS) if e.get("kind") == "result" and e.get("value", {}).get("status") == "failed"), None)\n    if terminal is not None:\n        try:\n            save_report(terminal)\n        except Exception as report_error:\n            failure["reportCaptureError"] = str(report_error)\n    (OUT / "network-safe-idle-runner-failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\\n")\n    try:\n        (OUT / "network-safe-idle-failure-log.txt").write_text(adb("logcat", "-d"))\n        (OUT / "network-safe-idle-failure.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))\n    except Exception:\n        pass\n', '    assert report["coreSha256"] == receipt["binaries"]["x86_64"]["sha256"]\n    verify(report)\n    (OUT / "network-safe-idle-final.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))\n    (OUT / "network-safe-idle-log.txt").write_text(checked_text(adb("logcat", "-d"))[0])\n    print(json.dumps({"status": "passed", "checkCount": report["checkCount"], "cases": len(report["cases"]), "realTrustedGestures": len(GESTURES), "report": str(OUT / "network-safe-idle-results.json")}))\nexcept BaseException as error:\n    failure = {"status": "failed", "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "error": safe_error_text(error, use_repr=False), "events": EVENTS, "gestures": GESTURES}\n    terminal = next((e["value"] for e in reversed(EVENTS) if e.get("kind") == "result" and e.get("value", {}).get("status") == "failed"), None)\n    if terminal is not None:\n        try:\n            save_report(terminal)\n        except Exception as report_error:\n            failure["reportCaptureError"] = safe_error_text(report_error, use_repr=False)\n    (OUT / "network-safe-idle-runner-failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\\n")\n    try:\n        (OUT / "network-safe-idle-failure-log.txt").write_text(checked_text(adb("logcat", "-d"))[0])\n        (OUT / "network-safe-idle-failure.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))\n    except Exception:\n        pass\n')), 'tests/gecko/run_network_settings_application.py': (("import json\nimport pathlib\nimport subprocess\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\n\n", "import json\nimport pathlib\nimport subprocess\nimport sys\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tools/gecko'))\nfrom diagnostic_capture_privacy import checked_text, safe_error_text\n# Stored diagnostic text is a verified service-key derivative.\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\n\n"), ("        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / 'network-settings-application-runner-failure.json').write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n        try:\n            (out / 'network-settings-application-log.txt').write_text(adb('logcat', '-d'))\n            (out / 'network-settings-application-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))\n        finally:\n            adb('shell', 'am', 'force-stop', PKG)\n", "        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / 'network-settings-application-runner-failure.json').write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': safe_error_text(error, use_repr=False),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n        try:\n            (out / 'network-settings-application-log.txt').write_text(checked_text(adb('logcat', '-d'))[0])\n            (out / 'network-settings-application-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))\n        finally:\n            adb('shell', 'am', 'force-stop', PKG)\n")), 'tests/gecko/run_network_settings_retry.py': (("import pathlib\nimport re\nimport subprocess\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\n\n", "import pathlib\nimport re\nimport subprocess\nimport sys\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tools/gecko'))\nfrom diagnostic_capture_privacy import checked_text, safe_error_text\n# Stored diagnostic text is a verified service-key derivative.\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\n\n"), ("        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / 'network-settings-retry-runner-failure.json').write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n        try:\n            (out / 'network-settings-retry-log.txt').write_text(adb('logcat', '-d'))\n            (out / 'network-settings-retry-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))\n        finally:\n            adb('shell', 'am', 'force-stop', PKG)\n", "        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / 'network-settings-retry-runner-failure.json').write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': safe_error_text(error, use_repr=False),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n        try:\n            (out / 'network-settings-retry-log.txt').write_text(checked_text(adb('logcat', '-d'))[0])\n            (out / 'network-settings-retry-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))\n        finally:\n            adb('shell', 'am', 'force-stop', PKG)\n")), 'tests/gecko/run_network_settings_internal.py': (("import pathlib\nimport re\nimport subprocess\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\nPREFIX = 'network-settings-internal'\n", "import pathlib\nimport re\nimport subprocess\nimport sys\nimport time\nimport uuid\n\nROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tools/gecko'))\nfrom diagnostic_capture_privacy import checked_text, safe_error_text\n# Stored diagnostic text is a verified service-key derivative.\nPKG = 'local.pocketchat.test'\nACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'\nPREFIX = 'network-settings-internal'\n"), ("        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / (PREFIX + '-runner-failure.json')).write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n", "        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))\n    except BaseException as error:\n        (out / (PREFIX + '-runner-failure.json')).write_text(json.dumps({\n            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': safe_error_text(error, use_repr=False),\n            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\\n')\n        raise\n    finally:\n"), ("            try:\n                value = adb(*command, binary=binary)\n                destination = out / (PREFIX + suffix)\n                destination.write_bytes(value) if binary else destination.write_text(value)\n            except Exception as error:\n                errors.append({'stage': suffix, 'error': str(error)})\n        try:\n            adb('shell', 'am', 'force-stop', PKG)\n        except Exception as error:\n            errors.append({'stage': 'force-stop', 'error': str(error)})\n        if errors:\n            (out / (PREFIX + '-diagnostic-errors.json')).write_text(json.dumps(errors, ensure_ascii=False, indent=2) + '\\n')\n\n", "            try:\n                value = adb(*command, binary=binary)\n                destination = out / (PREFIX + suffix)\n                destination.write_bytes(value) if binary else destination.write_text(checked_text(value)[0])\n            except Exception as error:\n                errors.append({'stage': suffix, 'error': safe_error_text(error, use_repr=False)})\n        try:\n            adb('shell', 'am', 'force-stop', PKG)\n        except Exception as error:\n            errors.append({'stage': 'force-stop', 'error': safe_error_text(error, use_repr=False)})\n        if errors:\n            (out / (PREFIX + '-diagnostic-errors.json')).write_text(json.dumps(errors, ensure_ascii=False, indent=2) + '\\n')\n\n")), 'tests/gecko/run_ui_fixes.py': (("import json\nfrom pathlib import Path\nimport subprocess\nimport time\n\nROOT = Path(__file__).resolve().parents[2]\nOUT = ROOT / 'work/gecko-integration'\n\ndef main():\n", "import json\nfrom pathlib import Path\nimport subprocess\nimport sys\nimport time\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tools/gecko'))\nfrom diagnostic_capture_privacy import checked_text, safe_error_text\n# Stored diagnostic text is a verified service-key derivative.\nOUT = ROOT / 'work/gecko-integration'\n\ndef main():\n"), ("            else:\n                raise TimeoutError('No complete report for '+key)\n        except Exception as failure:\n            failures.append((key,str(failure)))\n        finally:\n            (OUT/(key+'-log.txt')).write_text(adb('logcat', '-d'))\n    if failures:raise AssertionError(failures)\n\nif __name__=='__main__':\n", "            else:\n                raise TimeoutError('No complete report for '+key)\n        except Exception as failure:\n            failures.append((key,safe_error_text(failure, use_repr=False)))\n        finally:\n            (OUT/(key+'-log.txt')).write_text(checked_text(adb('logcat', '-d'))[0])\n    if failures:raise AssertionError(failures)\n\nif __name__=='__main__':\n")), 'tests/gecko/run_native_probe.py': (("import sys\nsys.path.insert(0, str(ROOT / 'tools'))\nfrom gecko.chain_runtime_contract import verify_native_probe\n\nOUT = ROOT / 'work/gecko-integration'\n\n", "import sys\nsys.path.insert(0, str(ROOT / 'tools'))\nfrom gecko.chain_runtime_contract import verify_native_probe\nfrom gecko.diagnostic_capture_privacy import checked_text\n# Stored diagnostic text is a verified service-key derivative.\n\nOUT = ROOT / 'work/gecko-integration'\n\n"), ("        return result.stdout\n\n    def failure_log():\n        (OUT / 'native-probe-failure-log.txt').write_text(adb('logcat', '-d', check=False))\n\n    adb('shell', 'am', 'force-stop', 'local.pocketchat.test')\n    adb('shell', 'pm', 'clear', 'local.pocketchat.test')\n", "        return result.stdout\n\n    def failure_log():\n        (OUT / 'native-probe-failure-log.txt').write_text(checked_text(adb('logcat', '-d', check=False))[0])\n\n    adb('shell', 'am', 'force-stop', 'local.pocketchat.test')\n    adb('shell', 'pm', 'clear', 'local.pocketchat.test')\n"), ("            report['sourceCommit'] = subprocess.check_output(\n                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()\n            (OUT / 'native-probe-results.json').write_text(json.dumps(report, indent=2) + '\\n')\n            (OUT / 'native-probe-log.txt').write_text(adb('logcat', '-d', '-s',\n                'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S'))\n            try:\n                verify(report)\n            except Exception:\n", "            report['sourceCommit'] = subprocess.check_output(\n                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()\n            (OUT / 'native-probe-results.json').write_text(json.dumps(report, indent=2) + '\\n')\n            (OUT / 'native-probe-log.txt').write_text(checked_text(adb('logcat', '-d', '-s',\n                'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S'))[0])\n            try:\n                verify(report)\n            except Exception:\n"), ("                              'cancellations': report['cancellations'],\n                              'startupSearches': report['startupSearches']}, indent=2), flush=True)\n            return\n        log = adb('logcat', '-d', '-s', 'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S')\n        if 'FATAL EXCEPTION' in log:\n            failure_log()\n            raise AssertionError(log)\n", "                              'cancellations': report['cancellations'],\n                              'startupSearches': report['startupSearches']}, indent=2), flush=True)\n            return\n        log = checked_text(adb('logcat', '-d', '-s', 'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S'))[0]\n        if 'FATAL EXCEPTION' in log:\n            failure_log()\n            raise AssertionError(log)\n")), 'tests/gecko/run_network_client_binding.py': (('from integration_event_contract import EventTransfer,parse_receipt_line\nfrom profile_invocation_contract import expected_build,verify_installed\nfrom network_client_binding_contract import ACTION,PACKAGE,verify_runner_report\n\n\ndef main():\n', 'from integration_event_contract import EventTransfer,parse_receipt_line\nfrom profile_invocation_contract import expected_build,verify_installed\nfrom network_client_binding_contract import ACTION,PACKAGE,verify_runner_report\nfrom diagnostic_capture_privacy import checked_bytes, safe_error_text\n\n\ndef main():\n'), ("        except subprocess.TimeoutExpired as error:\n            stdout,stderr=error.stdout or b'',error.stderr or b'';code=None\n        else:stdout,stderr,code=run.stdout,run.stderr,run.returncode\n        observation=dict(index=index,command=command,returnCode=code,streams={})\n        for label,raw in (('stdout',stdout),('stderr',stderr)):\n            path=out/('network-client-binding-adb-%04d-%s.raw.log'%(index,label));path.write_bytes(raw)\n            observation['streams'][label]=dict(path=path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())\n        records.append(observation)\n        if check and code!=0:raise RuntimeError('Binding fixture ADB command failed: '+repr(observation))\n        return stdout if binary else stdout.decode('utf-8',errors='strict')\n    def raw_proof(raw):return dict(rawUtf8=raw.decode('utf-8',errors='strict'),utf8Bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())\n    try:\n        gradle=(ROOT/'app/build.gradle').read_text()\n", "        except subprocess.TimeoutExpired as error:\n            stdout,stderr=error.stdout or b'',error.stderr or b'';code=None\n        else:stdout,stderr,code=run.stdout,run.stderr,run.returncode\n        observation=dict(index=index,command=command,returnCode=code,streams={});public_stdout=stdout\n        for label,raw in (('stdout',stdout),('stderr',stderr)):\n            # Only logcat diagnostics are byte derivatives; primary commands remain exact.\n            stored,privacy=checked_bytes(raw) if parts and parts[0]=='logcat' else (raw,None)\n            path=out/('network-client-binding-adb-%04d-%s.raw.log'%(index,label));path.write_bytes(stored)\n            observation['streams'][label]=dict(path=path.name,bytes=len(stored),sha256=hashlib.sha256(stored).hexdigest())\n            if privacy is not None:\n                observation['streams'][label]['capturePrivacy']=privacy\n                if label=='stdout':public_stdout=stored\n        records.append(observation)\n        if check and code!=0:raise RuntimeError('Binding fixture ADB command failed: '+repr(observation))\n        return public_stdout if binary else public_stdout.decode('utf-8',errors='strict')\n    def raw_proof(raw):return dict(rawUtf8=raw.decode('utf-8',errors='strict'),utf8Bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())\n    try:\n        gradle=(ROOT/'app/build.gradle').read_text()\n"), ("        wrapper['packageUidAfterRaw']=adb('shell','cmd','package','list','packages','-U',PACKAGE)\n        wrapper['status']='passed';wrapper['verification']=verify_runner_report(wrapper,source)\n    except BaseException as error:\n        wrapper['status']='failed';wrapper['error']=type(error).__name__+': '+str(error)\n        try:adb('logcat','-d',binary=True,check=False)\n        except BaseException as secondary:wrapper['failureLogCollectionError']=str(secondary)\n        raise\n    finally:\n        # Includes original failed event/identity/CLI bytes; no synthetic completion.\n", "        wrapper['packageUidAfterRaw']=adb('shell','cmd','package','list','packages','-U',PACKAGE)\n        wrapper['status']='passed';wrapper['verification']=verify_runner_report(wrapper,source)\n    except BaseException as error:\n        wrapper['status']='failed';wrapper['error']=type(error).__name__+': '+safe_error_text(error, use_repr=False)\n        try:adb('logcat','-d',binary=True,check=False)\n        except BaseException as secondary:wrapper['failureLogCollectionError']=safe_error_text(secondary, use_repr=False)\n        raise\n    finally:\n        # Includes original failed event/identity/CLI bytes; no synthetic completion.\n")), 'tests/gecko/run_appearance_web.py': (('from pathlib import Path\nimport re\nimport subprocess\nimport threading\nimport time\nfrom urllib.parse import parse_qs, urlsplit\n', 'from pathlib import Path\nimport re\nimport subprocess\nimport sys\nimport threading\nimport time\nfrom urllib.parse import parse_qs, urlsplit\n'), ("\n\nROOT = Path(__file__).resolve().parents[2]\nOUT = ROOT / 'work/gecko-integration'\nPACKAGE = 'local.pocketchat.test'\nACTION = 'appearanceSync'\n", "\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tools/gecko'))\nfrom diagnostic_capture_privacy import checked_bytes, safe_error_text\nOUT = ROOT / 'work/gecko-integration'\nPACKAGE = 'local.pocketchat.test'\nACTION = 'appearanceSync'\n"), ("            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None\n        index = len(commands) + 1\n        observation = dict(index=index, command=command, returnCode=code, streams={})\n        for stream, raw in (('stdout', stdout), ('stderr', stderr)):\n            path = OUT / ('appearance-web-adb-%04d-%s.raw' % (index, stream))\n            path.write_bytes(raw)\n            observation['streams'][stream] = dict(path=path.name, bytes=len(raw), sha256=digest(raw))\n        commands.append(observation)\n        if check and code != 0:\n            raise RuntimeError('Appearance fixture ADB command failed: ' + repr(observation))\n        return stdout if binary else stdout.decode('utf-8', errors='strict')\n\n    def capture(phase):\n        png = adb('exec-out', 'screencap', '-p', binary=True)\n", "            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None\n        index = len(commands) + 1\n        observation = dict(index=index, command=command, returnCode=code, streams={})\n        public_stdout = stdout\n        for stream, raw in (('stdout', stdout), ('stderr', stderr)):\n            # Only logcat diagnostics are byte derivatives; primary commands remain exact.\n            stored, privacy = checked_bytes(raw) if parts and parts[0] == 'logcat' else (raw, None)\n            path = OUT / ('appearance-web-adb-%04d-%s.raw' % (index, stream))\n            path.write_bytes(stored)\n            observation['streams'][stream] = dict(path=path.name, bytes=len(stored), sha256=digest(stored))\n            if privacy is not None:\n                observation['streams'][stream]['capturePrivacy'] = privacy\n                if stream == 'stdout':\n                    public_stdout = stored\n        commands.append(observation)\n        if check and code != 0:\n            raise RuntimeError('Appearance fixture ADB command failed: ' + repr(observation))\n        return public_stdout if binary else public_stdout.decode('utf-8', errors='strict')\n\n    def capture(phase):\n        png = adb('exec-out', 'screencap', '-p', binary=True)\n"), ("        report.update(status='passed', actualAndroidExecution=True,\n                      phaseCount=len(invocations), checkCount=sum(len(row['result']['checks']) for row in invocations))\n    except BaseException as error:\n        report.update(status='failed', error=type(error).__name__ + ': ' + str(error))\n        if report.get('actualAndroidFixtureAttempted'):\n            try:\n                capture('failure')\n            except BaseException as secondary:\n                report['failureCaptureError'] = type(secondary).__name__ + ': ' + str(secondary)\n        raise\n    finally:\n        if commands:\n", "        report.update(status='passed', actualAndroidExecution=True,\n                      phaseCount=len(invocations), checkCount=sum(len(row['result']['checks']) for row in invocations))\n    except BaseException as error:\n        report.update(status='failed', error=type(error).__name__ + ': ' + safe_error_text(error, use_repr=False))\n        if report.get('actualAndroidFixtureAttempted'):\n            try:\n                capture('failure')\n            except BaseException as secondary:\n                report['failureCaptureError'] = type(secondary).__name__ + ': ' + safe_error_text(secondary, use_repr=False)\n        raise\n    finally:\n        if commands:\n"), ("                raw = adb('logcat', '-d', binary=True, check=False)\n                (OUT / 'appearance-web-logcat.raw.log').write_bytes(raw)\n            except BaseException as error:\n                report['finalLogError'] = str(error)\n        for port in reversed_ports:\n            try:\n                adb('reverse', '--remove', 'tcp:' + str(port), check=False)\n            except BaseException as error:\n                report.setdefault('cleanupErrors', []).append(str(error))\n        with device.fixture.CONNECTION_LOCK:\n            for connection in tuple(device.fixture.CONNECTIONS):\n                try:\n", "                raw = adb('logcat', '-d', binary=True, check=False)\n                (OUT / 'appearance-web-logcat.raw.log').write_bytes(raw)\n            except BaseException as error:\n                report['finalLogError'] = safe_error_text(error, use_repr=False)\n        for port in reversed_ports:\n            try:\n                adb('reverse', '--remove', 'tcp:' + str(port), check=False)\n            except BaseException as error:\n                report.setdefault('cleanupErrors', []).append(safe_error_text(error, use_repr=False))\n        with device.fixture.CONNECTION_LOCK:\n            for connection in tuple(device.fixture.CONNECTIONS):\n                try:\n"))}


def original_additional_producer(path, text):
    for previous, added in PRODUCER_HUNKS[path]:
        if text.count(added) != 1:
            raise ValueError('Missing, moved or repeated exact diagnostic producer addition')
        text = text.replace(added, previous, 1)
    return text


class ProducerCapturePrivacyTest(HOST.TestBase):
    def fake_child(self, out, err=b'', code=0):
        adb = self.root / 'fake-adb'
        adb.write_text('#!' + sys.executable + '\nimport os,sys\nos.write(1,bytes.fromhex(' + repr(out.hex()) + '))\nos.write(2,bytes.fromhex(' + repr(err.hex()) + '))\nsys.exit(' + str(code) + ')\n')
        adb.chmod(0o700)
        return str(adb)

    def public_files_have_no_supported_keys(self):
        for p in RUNNER.OUT.iterdir():
            raw = p.read_bytes()
            G.assert_public_diagnostic_text(p, raw)
            self.assertEqual(G.service_api_key_findings(raw.decode('utf-8', errors='replace')), [], p.name)

    def marker(self, name, out, err):
        meta = json.loads((RUNNER.OUT / (name + '-decode.json')).read_text())
        for label, original in [('stdout', out), ('stderr', err)]:
            stored = (RUNNER.OUT / (name + '-' + label + '.raw.log')).read_bytes()
            marker = meta['capturePrivacy']['byteStreams'][label]
            self.assertEqual(meta['streams'][label]['bytes'], len(original))
            self.assertEqual(meta['streams'][label]['sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(marker['originalBytes'], len(original))
            self.assertEqual(marker['originalSha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(marker['storedBytes'], len(stored))
            self.assertEqual(marker['storedSha256'], hashlib.sha256(stored).hexdigest())
            self.assertEqual(marker['changed'], original != stored)
            self.assertEqual(marker['projectionEncoding'], 'latin1')
            self.assertEqual(marker['helperHashEncoding'], 'utf-8')
            projection = original.decode('latin1').encode('utf-8')
            self.assertEqual(marker['projectionPrivacy']['originalBytes'], len(projection))
            self.assertEqual(marker['projectionPrivacy']['originalSha256'], hashlib.sha256(projection).hexdigest())
            self.assertTrue(G.verify_capture_privacy(marker['projectionPrivacy'], stored.decode('latin1')))
        display = (RUNNER.OUT / (name + '-display.txt')).read_bytes().decode('utf-8')
        self.assertTrue(G.verify_capture_privacy(meta['capturePrivacy']['displayPrivacy'], display))
        self.public_files_have_no_supported_keys()
        return meta

    def test_whole_old_runner_and_all_workload_bytes_inverse_exactly(self):
        current = ROUTE.read_text()
        self.assertEqual(hashlib.sha256(original_route_runner(current).encode()).hexdigest(), PREVIOUS_RUNNER_SHA256)
        for previous, added in CHANGES:
            with self.subTest(addition=added.splitlines()[0]), self.assertRaises(ValueError):
                original_route_runner(current.replace(added, previous, 1))
        for before, after in [("default=420", "default=999"), ("timeout=30", "timeout=99"),
                              ("time.sleep(1)", "time.sleep(0)"), ("result=verify(report,server,receipt,source)", "result={}")]:
            changed = current.replace(before, after, 1)
            try:
                restored = original_route_runner(changed)
            except ValueError:
                continue
            self.assertNotEqual(hashlib.sha256(restored.encode()).hexdigest(), PREVIOUS_RUNNER_SHA256)
        moved = current.replace(CHANGES[0][1], CHANGES[0][0], 1).replace("ROOT=", "from tools.gecko.diagnostic_capture_privacy import checked_text, checked_bytes, safe_error_text\nROOT=", 1)
        with self.assertRaises(ValueError):
            original_route_runner(moved)

    def test_actual_child_plain_keys_and_invalid_utf8_preserve_non_key_bytes(self):
        out = '前🙂'.encode() + b'\xff\xc2 \r\n' + service_bytes() + b'unchanged-tail\x80\n'
        err = b'err\xfe ' + service_bytes()
        display = RUNNER.capture_logcat(self.fake_child(out, err), 'controlled', stem='plain')
        self.assertEqual((RUNNER.OUT / 'plain-stdout.raw.log').read_bytes(), expected_plain(out))
        self.assertEqual((RUNNER.OUT / 'plain-stderr.raw.log').read_bytes(), expected_plain(err))
        self.assertEqual(display, expected_plain(out).decode('utf-8', errors='backslashreplace'))
        meta = self.marker('plain', out, err)
        marker = meta['capturePrivacy']['byteStreams']['stdout']
        self.assertNotEqual(marker['originalSha256'], marker['projectionPrivacy']['originalSha256'])
        self.assertNotEqual(marker['storedSha256'], marker['projectionPrivacy']['finalSha256'])
        self.assertEqual(sum(marker['projectionPrivacy']['replacements'].values()), 4)

    def test_actual_child_escaped_key_forms_change_only_value_spans(self):
        def encoded(value): return b''.join(('%%%02X' % b).encode() for b in value)
        mozilla = b'https://location.services.mozilla.com/v1/country?key=' + b'm' * 36 + b'&kept=1'
        values = [(mozilla.replace(b'/', b'\\/'), b'm' * 36),
                  (mozilla.replace(b'key=', b'%6bey='), b'm' * 36),
                  (mozilla.replace(b'm' * 36, encoded(b'm' * 36)), encoded(b'm' * 36)),
                  (encoded(mozilla), encoded(b'm' * 36)),
                  (b'unknown=' + b'\\u0041\\u0049\\u007a\\u0061' + b'g' * 35, b'\\u0041\\u0049\\u007a\\u0061' + b'g' * 35),
                  (b'unknown=' + encoded(key()), encoded(key()))]
        for i, (body, token) in enumerate(values):
            with self.subTest(form=i):
                raw = b'prefix\xff\r\n' + body + b'\n\xc2tail'
                name = 'escaped' + str(i)
                RUNNER.capture_logcat(self.fake_child(raw), 'controlled', stem=name)
                self.assertEqual((RUNNER.OUT / (name + '-stdout.raw.log')).read_bytes(), raw.replace(token, G.PRIVACY_REPLACEMENT.encode()))
                self.marker(name, raw, b'')

    def test_actual_nonzero_child_retains_private_exception_bytes_but_public_derivatives(self):
        out = b'prefix\xff ' + service_bytes(); err = b'error\xfe ' + key()
        with self.assertRaises(subprocess.CalledProcessError) as got:
            RUNNER.capture_logcat(self.fake_child(out, err, 9), 'controlled', stem='nonzero')
        self.assertEqual(got.exception.returncode, 9)
        self.assertEqual(got.exception.stdout, out)
        self.assertEqual(got.exception.stderr, err)
        self.assertEqual(G.service_api_key_findings(repr(got.exception)), [])
        self.marker('nonzero', out, err)

    def test_timeout_retains_same_exception_and_filters_partial_public_captures(self):
        out = b'partial\xff ' + service_bytes();err = b'error\xfe ' + key()
        error = subprocess.TimeoutExpired(['adb'], 30, output=out, stderr=err)
        with patch.object(RUNNER.subprocess, 'run', side_effect=error), self.assertRaises(subprocess.TimeoutExpired) as got:
            RUNNER.capture_logcat('adb', 'controlled', stem='timeout-key')
        self.assertIs(got.exception, error)
        self.assertEqual(error.stdout, out);self.assertEqual(error.stderr, err)
        self.assertTrue(self.marker('timeout-key', out, err)['timedOut'])

    def test_failed_derivative_check_retains_timeout_without_public_raw_fallback(self):
        error = subprocess.TimeoutExpired(['adb'], 30, output=service_bytes(), stderr=key())
        with patch.object(RUNNER.subprocess, 'run', side_effect=error), patch.object(P, 'checked_text', side_effect=ValueError('fixed refusal')), self.assertRaises(subprocess.TimeoutExpired) as got:
            RUNNER.capture_logcat('adb', 'controlled', stem='refused-timeout')
        self.assertIs(got.exception, error)
        self.assertEqual(list(RUNNER.OUT.iterdir()), [])

    def test_counterfeit_marker_or_remaining_supported_key_is_rejected_before_storage(self):
        original = b'unknown=' + key()
        final, marker = G.redact_service_api_keys('benign')
        forged = copy.deepcopy(marker)
        text = original.decode()
        forged.update(originalBytes=len(original), finalBytes=len(original),
                      originalSha256=hashlib.sha256(original).hexdigest(), finalSha256=hashlib.sha256(original).hexdigest())
        for value, metadata in [(text, forged), (final, dict(marker, finalSha256='0' * 64))]:
            with self.subTest(remaining=value == text), patch.object(RUNNER.subprocess, 'run', return_value=subprocess.CompletedProcess(['adb'], 0, original, b'')), patch.object(P, 'redact_service_api_keys', return_value=(value, metadata)), self.assertRaises(ValueError):
                RUNNER.capture_logcat('adb', 'controlled', stem='refused')
            self.assertEqual(list(RUNNER.OUT.iterdir()), [])
        for invalid in [None, 'not bytes', bytearray(b'bad')]:
            with self.assertRaises(ValueError):P.checked_bytes(invalid)
        with self.assertRaises(ValueError):P.checked_text('x' * (G.PRIVACY_MAX_BYTES + 1))
        with patch.object(P, 'checked_text') as text_adapter:
            with self.assertRaises(ValueError):P.checked_bytes(b'x' * (G.PRIVACY_MAX_BYTES + 1))
            text_adapter.assert_not_called()

    def test_secondary_error_repr_is_filtered_and_unavailable_repr_is_fixed(self):
        server = self.root / 'server.json';server.write_text('{"kept":true}')
        error = OSError(service_bytes().decode())
        with patch.object(RUNNER, 'capture_logcat', side_effect=error):
            RUNNER.save_failure_diagnostics('adb', 'controlled', server)
        self.assertEqual(error.args, (service_bytes().decode(),))
        self.public_files_have_no_supported_keys()
        self.assertEqual(json.loads((RUNNER.OUT / 'network-source-route-diagnostic-errors.json').read_text())['errors'][0]['stage'], 'logcat')
        class BadRepr:
            def __repr__(self):raise OSError('unavailable')
        self.assertEqual(P.safe_error_text(BadRepr()), 'Diagnostic error text unavailable')

    def test_real_main_fatal_text_is_filtered_before_raise_and_failure_files(self):
        scenario = HOST.MainScenario(log=service_bytes() + b'noise\xff\nFATAL EXCEPTION\n' + HOST.COMPLETE)
        with self.assertRaises(AssertionError) as got:scenario.execute()
        self.assertEqual(scenario.provider_reads, 0);self.assertEqual(scenario.verify_calls, 0)
        self.assertIn('FATAL EXCEPTION', str(got.exception))
        self.assertEqual(G.service_api_key_findings(str(got.exception)), [])
        self.public_files_have_no_supported_keys()
        self.assertNotIn('"status": "passed"', scenario.stdout.getvalue())


    def test_all_eight_producers_inverse_to_full_original_source(self):
        for path, expected in PRODUCER_PINS.items():
            current = (ROOT / path).read_text()
            if path == 'tests/gecko/run_network_settings_internal.py':
                current = INTERNAL46.require_runner_source(current.encode()).decode()
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(original_additional_producer(path, current).encode()).hexdigest(), expected)
                for previous, added in PRODUCER_HUNKS[path]:
                    modified = current.replace(added, previous, 1)
                    try:
                        restored = original_additional_producer(path, modified)
                    except ValueError:
                        continue
                    self.assertNotEqual(hashlib.sha256(restored.encode()).hexdigest(), expected)

    def nested_adb(self, relative):
        source = (ROOT / relative).read_text()
        main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        node = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'adb')
        directory = self.root / relative.split('/')[-1]
        directory.mkdir()
        records = []
        namespace = dict(args=types.SimpleNamespace(adb='fake-adb', serial='controlled'),
                         records=records, commands=records, out=directory, OUT=directory,
                         checked_bytes=P.checked_bytes, hashlib=hashlib, subprocess=subprocess,
                         digest=lambda b: hashlib.sha256(b).hexdigest())
        exec(compile(textwrap.dedent(ast.get_source_segment(source, node)), '<actual-producer-adb>', 'exec'), namespace)
        return namespace['adb'], records, directory

    def test_actual_nested_adb_changes_only_logcat_bytes_and_keeps_primary_proofs_exact(self):
        for relative in ['tests/gecko/run_network_client_binding.py', 'tests/gecko/run_appearance_web.py']:
            with self.subTest(runner=relative):
                adb, records, directory = self.nested_adb(relative)
                primary = b'{"value":"' + key() + b'"}'
                error = b'unchanged-stderr'
                with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess(['fake-adb'], 0, primary, error)):
                    for parts in [('exec-out', 'content', 'read', '--uri', 'content://fixture'),
                                  ('exec-out', 'screencap', '-p'), ('shell', 'getprop', 'fixture')]:
                        returned = adb(*parts, binary=True)
                        self.assertEqual(returned, primary)
                        for label, raw in [('stdout', primary), ('stderr', error)]:
                            row = records[-1]['streams'][label]
                            self.assertEqual(set(row), {'path', 'bytes', 'sha256'})
                            self.assertEqual((directory / row['path']).read_bytes(), raw)
                            self.assertEqual(row['sha256'], hashlib.sha256(raw).hexdigest())
                raw = b'prefix\xff ' + service_bytes() + b' tail\xc2'
                with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess(['fake-adb'], 0, raw, raw)):
                    returned = adb('logcat', '-d', binary=True)
                self.assertEqual(returned, expected_plain(raw))
                for label in ['stdout', 'stderr']:
                    row = records[-1]['streams'][label]
                    stored = (directory / row['path']).read_bytes()
                    self.assertEqual(stored, expected_plain(raw))
                    self.assertEqual(row['bytes'], len(stored))
                    self.assertEqual(row['sha256'], hashlib.sha256(stored).hexdigest())
                    self.assertEqual(row['capturePrivacy']['originalSha256'], hashlib.sha256(raw).hexdigest())
                    self.assertEqual(row['capturePrivacy']['storedSha256'], row['sha256'])
                    self.assertTrue(G.verify_capture_privacy(row['capturePrivacy']['projectionPrivacy'], stored.decode('latin1')))
        # The original strict three-key raw proof contract remains authoritative.
        sys.path.insert(0, str(ROOT / 'tools/gecko'))
        from network_client_binding_contract import raw_value
        proof = dict(rawUtf8=primary.decode(), utf8Bytes=len(primary), sha256=hashlib.sha256(primary).hexdigest())
        self.assertEqual(raw_value(proof), json.loads(primary))
        with self.assertRaises(ValueError):raw_value(dict(proof, capturePrivacy={}))

    def test_actual_plain_diagnostic_write_expressions_use_checked_text(self):
        relative_names = ['run_network_safe_idle.py', 'run_network_settings_application.py',
                          'run_network_settings_retry.py', 'run_ui_fixes.py', 'run_native_probe.py']
        count = 0
        raw = service_bytes().decode()
        for name in relative_names:
            source = (ROOT / 'tests/gecko' / name).read_text()
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):continue
                call = node.value
                if not isinstance(call.func, ast.Attribute) or call.func.attr != 'write_text':continue
                if not any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == 'adb'
                           and c.args and isinstance(c.args[0], ast.Constant) and c.args[0].value == 'logcat' for c in ast.walk(call)):continue
                directory = self.root / ('plain-' + str(count));directory.mkdir()
                namespace = dict(OUT=directory, out=directory, key='controlled', checked_text=P.checked_text,
                                 adb=lambda *args, **kwargs: raw)
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-diagnostic-write>', 'exec'), namespace)
                files = list(directory.iterdir());self.assertEqual(len(files), 1)
                self.assertEqual(files[0].read_bytes(), expected_plain(service_bytes()))
                count += 1
        self.assertEqual(count, 7)
        source = (ROOT / 'tests/gecko/run_network_settings_internal.py').read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.IfExp) and 'destination.write_bytes' in ast.get_source_segment(source, n))
        destination = self.root / 'internal-log.txt'
        namespace = dict(binary=False, value=raw, destination=destination, checked_text=P.checked_text)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-internal-diagnostic-write>', 'exec'), namespace)
        self.assertEqual(destination.read_bytes(), expected_plain(service_bytes()))
        namespace.update(binary=True, value=b'PNG-primary' + key())
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-internal-primary-write>', 'exec'), namespace)
        self.assertEqual(destination.read_bytes(), b'PNG-primary' + key())

    def test_zero_hit_text_bytes_and_secondary_error_formats_remain_exact(self):
        text = '中文🙂\r\nbenign cookie=fixture password=controlled\n'
        stored, metadata = P.checked_text(text)
        self.assertEqual(stored, text);self.assertFalse(metadata['changed'])
        original = text.encode() + b'\xff\xc2'
        stored, metadata = P.checked_bytes(original)
        self.assertEqual(stored, original);self.assertFalse(metadata['changed'])
        error = OSError('ordinary diagnostic')
        self.assertEqual(P.safe_error_text(error), repr(error))
        self.assertEqual(P.safe_error_text(error, use_repr=False), str(error))


if __name__ == '__main__':
    unittest.main()
