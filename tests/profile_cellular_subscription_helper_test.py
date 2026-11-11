"""Execute the real Java helper against counterfeit framework I/O, never Android acceptance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/gecko/EmulatorDataSubscription.java'
NONCE = '0123456789abcdef' * 2

FRAMEWORK = {
    'android/os/Process.java': r'''
package android.os;
public final class Process {
  public static int myUid() { return Integer.getInteger("uid", 2000); }
}
''',
    'android/os/SystemProperties.java': r'''
package android.os;
public final class SystemProperties {
  private static int guard;
  public static String get(String key) {
    if (key.equals("ro.kernel.qemu")) {
      guard++;
      if (Boolean.getBoolean("runtimeChange") && guard > 1) return "0";
      return System.getProperty("qemu", "1");
    }
    if (key.equals("ro.build.version.sdk")) return System.getProperty("sdk", "35");
    if (key.equals("ro.product.cpu.abi")) return System.getProperty("abi", "x86_64");
    if (key.equals("ro.hardware")) return System.getProperty("hardware", "ranchu");
    throw new AssertionError("Unapproved property");
  }
}
''',
    'android/os/IBinder.java': r'''
package android.os;
public interface IBinder { String getInterfaceDescriptor(); }
''',
    'android/os/ServiceManager.java': r'''
package android.os;
public final class ServiceManager {
  private static final class Binder implements IBinder {
    public String getInterfaceDescriptor() {
      return System.getProperty("descriptor", "com.android.internal.telephony.ISub");
    }
  }
  public static IBinder getService(String name) {
    if (!"isub".equals(name)) throw new AssertionError("Unapproved service");
    return Boolean.getBoolean("serviceAbsent") ? null : new Binder();
  }
}
''',
    'com/android/internal/telephony/ISub.java': r'''
package com.android.internal.telephony;
import android.os.IBinder;
import java.io.FileWriter;
import java.io.IOException;

public interface ISub {
  int[] getActiveSubIdList(boolean visibleOnly);
  int getDefaultDataSubId();
  int getPhoneId(int subId);
  int getSubId(int slot);
  void setDefaultDataSubId(int subId);

  public static final class Stub {
    public static ISub asInterface(IBinder binder) {
      return Boolean.getBoolean("interfaceAbsent") ? null : new Proxy();
    }
    // Deliberately private: production reflection must target public ISub.
    private static final class Proxy implements ISub {
      private int snapshot;
      private int data = Integer.getInteger("default", -1);
      private void trace(String event) {
        try (FileWriter out = new FileWriter(System.getProperty("trace"), true)) {
          out.write(event + "\n");
        } catch (IOException failure) { throw new AssertionError(failure); }
      }
      public int[] getActiveSubIdList(boolean visibleOnly) {
        trace("active:" + visibleOnly);
        if (visibleOnly) throw new AssertionError("Hidden active subscriptions omitted");
        if (Boolean.getBoolean("readDenied")) throw new SecurityException("private detail");
        snapshot++;
        String value = System.getProperty("active", "1");
        if (snapshot == 2) value = System.getProperty("beforeActive", value);
        if (snapshot >= 3) value = System.getProperty("afterActive", value);
        if (value.isEmpty()) return new int[0];
        String[] fields = value.split(",");
        int[] result = new int[fields.length];
        for (int i = 0; i < fields.length; i++) result[i] = Integer.parseInt(fields[i]);
        return result;
      }
      public int getDefaultDataSubId() {
        if (snapshot == 2) return Integer.getInteger("beforeDefault", data);
        if (snapshot >= 3) return Integer.getInteger("afterDefault", data);
        return data;
      }
      public int getPhoneId(int subId) { return Integer.getInteger("phone", 0); }
      public int getSubId(int slot) {
        if (slot != 0) throw new AssertionError("Unapproved slot");
        return Integer.getInteger("slotSub", 1);
      }
      public void setDefaultDataSubId(int subId) {
        trace("set-attempt:" + subId);
        if (Boolean.getBoolean("setDenied")) throw new SecurityException("private detail");
        trace("set-confirmed:" + subId);
        data = subId;
      }
    }
  }
}
''',
}


class SubscriptionHelperControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='cellular-subscription-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        cls.java = Path(home) / 'bin/java' if home else Path(shutil.which('java') or '')
        cls.javac = cls.java.with_name('javac')
        if not cls.java.is_file() or not cls.javac.is_file():
            raise AssertionError('The actual host JDK is required')
        sources = [SOURCE]
        for name, raw in FRAMEWORK.items():
            path = cls.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw)
            sources.append(path)
        result = subprocess.run([str(cls.javac), '--release', '8', '-encoding', 'UTF-8',
                                 '-d', str(cls.work), *map(str, sources)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr)

    def execute(self, properties=None, nonce=NONCE):
        trace = self.work / (self.id().split('.')[-1] + '.trace')
        if trace.exists():
            trace.unlink()
        command = [str(self.java), '-Dtrace=' + str(trace)]
        command += ['-D' + key + '=' + str(value) for key, value in (properties or {}).items()]
        command += ['-cp', str(self.work), 'org.pocketchat.synthetic.EmulatorDataSubscription', nonce]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.stderr, '')
        self.assertEqual(len(result.stdout.splitlines()), 1)
        value = json.loads(result.stdout)
        self.assertIs(value['applicationAcceptance'], False)
        self.assertIs(value['physicalPhoneAcceptance'], False)
        self.assertIs(value['networkAcceptance'], False)
        calls = trace.read_text().splitlines() if trace.exists() else []
        self.assertNotIn('active:true', calls)
        self.assertLessEqual(sum(row.startswith('set-attempt:') for row in calls), 1)
        return result.returncode, value, calls

    def test_invalid_default_is_initialized_once_and_read_back(self):
        code, value, calls = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(value['status'], 'passed')
        self.assertEqual(set(value), {'schema', 'kind', 'runNonce', 'status', 'uid', 'androidSdk',
                                     'qemu', 'abi', 'hardware', 'initial', 'beforeWrite', 'after',
                                     'setCalls', 'applicationAcceptance', 'physicalPhoneAcceptance', 'networkAcceptance'})
        self.assertEqual(value['initial']['defaultDataSubId'], -1)
        self.assertEqual(value['beforeWrite']['defaultDataSubId'], -1)
        self.assertEqual(value['after']['defaultDataSubId'], 1)
        self.assertEqual(value['setCalls'], 1)
        self.assertEqual([x for x in calls if x.startswith('set-')], ['set-attempt:1', 'set-confirmed:1'])

    def test_existing_default_and_automatic_initialization_do_not_write(self):
        for properties in ({'default': 1}, {'default': -1, 'beforeDefault': 1, 'afterDefault': 1}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 0)
                self.assertEqual(value['setCalls'], 0)
                self.assertFalse(any(x.startswith('set-') for x in calls))

    def test_physical_wrong_uid_or_wrong_image_is_refused_before_binder(self):
        for properties in ({'uid': 0}, {'uid': 1000}, {'qemu': 0}, {'sdk': 34},
                           {'sdk': 36}, {'abi': 'arm64-v8a'}, {'hardware': 'other'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertEqual(calls, [])

    def test_missing_ambiguous_or_invalid_subscription_never_writes(self):
        for active in ('', '1,2', '1,1', '-1', '0', '2147483647'):
            with self.subTest(active=active):
                code, value, calls = self.execute({'active': active})
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertFalse(any(x.startswith('set-') for x in calls))

    def test_existing_different_default_and_wrong_slot_never_write(self):
        for properties in ({'default': 2}, {'default': 0}, {'default': 2147483647},
                           {'phone': 1}, {'phone': -1}, {'slotSub': 2}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertFalse(any(x.startswith('set-') for x in calls))

    def test_subscription_or_runtime_change_before_write_is_refused(self):
        for properties in ({'beforeActive': '2'}, {'beforeActive': '1,2'},
                           {'beforeDefault': 2}, {'default': 1, 'beforeDefault': -1},
                           {'runtimeChange': 'true'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertFalse(any(x.startswith('set-') for x in calls))

    def test_actual_readback_failure_never_becomes_success_or_second_write(self):
        for properties in ({'afterDefault': -1}, {'afterDefault': 2},
                           {'afterActive': '2'}, {'afterActive': '1,2'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 1)
                self.assertEqual(sum(x.startswith('set-attempt:') for x in calls), 1)

    def test_permission_refusal_is_preserved_without_fallback_or_exception_detail(self):
        for properties, count in (({'readDenied': 'true'}, 0), ({'setDenied': 'true'}, 1)):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['reason'], 'permission-denied')
                self.assertEqual(value['setCalls'], count)
                self.assertFalse(any(x.startswith('set-confirmed:') for x in calls))
                self.assertNotIn('private detail', json.dumps(value))

    def test_service_interface_and_invocation_fail_closed(self):
        for properties in ({'serviceAbsent': 'true'}, {'interfaceAbsent': 'true'},
                           {'descriptor': 'different.interface'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertFalse(any(x.startswith('set-') for x in calls))
        code, value, calls = self.execute(nonce='not-a-nonce')
        self.assertEqual(code, 1)
        self.assertEqual(value['reason'], 'invalid-invocation')
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
