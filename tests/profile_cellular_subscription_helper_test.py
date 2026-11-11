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
    private final String name;
    Binder(String name) { this.name = name; }
    public String getInterfaceDescriptor() {
      if (name.equals("isub")) return System.getProperty("descriptor", "com.android.internal.telephony.ISub");
      if (name.equals("phone")) return System.getProperty("phoneDescriptor", "com.android.internal.telephony.ITelephony");
      return System.getProperty("carrierDescriptor", "com.android.internal.telephony.ICarrierConfigLoader");
    }
  }
  public static IBinder getService(String name) {
    String option;
    if (name.equals("isub")) option = "serviceAbsent";
    else if (name.equals("phone")) option = "phoneServiceAbsent";
    else if (name.equals("carrier_config")) option = "carrierServiceAbsent";
    else throw new AssertionError("Unapproved service");
    return Boolean.getBoolean(option) ? null : new Binder(name);
  }
}
''',
    'android/os/PersistableBundle.java': r'''
package android.os;
public final class PersistableBundle {
  private final Object value;
  private final boolean present;
  public PersistableBundle(Object value, boolean present) { this.value = value; this.present = present; }
  public boolean containsKey(String key) {
    if (!key.equals("carrier_config_applied_bool")) throw new AssertionError("Unapproved config key");
    return present;
  }
  public Object get(String key) {
    if (!key.equals("carrier_config_applied_bool")) throw new AssertionError("Unapproved config key");
    return value;
  }
}
''',
    'com/android/internal/telephony/ITelephony.java': r'''
package com.android.internal.telephony;
import android.os.IBinder;
import java.io.FileWriter;
import java.io.IOException;
public interface ITelephony {
  int getSimStateForSlotIndex(int slot);
  public static final class Stub {
    public static ITelephony asInterface(IBinder binder) {
      return Boolean.getBoolean("phoneInterfaceAbsent") ? null : new Proxy();
    }
    private static final class Proxy implements ITelephony {
      private int reads;
      public int getSimStateForSlotIndex(int slot) {
        if (slot != 0) throw new AssertionError("Unapproved SIM slot");
        reads++;
        try (FileWriter out = new FileWriter(System.getProperty("trace"), true)) {
          out.write("sim-read:" + slot + ":" + reads + "\n");
        } catch (IOException failure) { throw new AssertionError(failure); }
        if (Boolean.getBoolean("simReadDenied")) throw new SecurityException("private SIM detail");
        return Integer.getInteger("sim" + reads, Integer.getInteger("simState", 10));
      }
    }
  }
}
''',
    'com/android/internal/telephony/ICarrierConfigLoader.java': r'''
package com.android.internal.telephony;
import android.os.IBinder;
import android.os.PersistableBundle;
import java.io.FileWriter;
import java.io.IOException;
public interface ICarrierConfigLoader {
  PersistableBundle getConfigForSubIdWithFeature(int subId, String callingPackage, String feature);
  void notifyConfigChangedForSubId(int subId);
  public static final class Stub {
    public static ICarrierConfigLoader asInterface(IBinder binder) {
      return Boolean.getBoolean("carrierInterfaceAbsent") ? null : new Proxy();
    }
    private static final class Proxy implements ICarrierConfigLoader {
      private int reads;
      private void trace(String event) {
        try (FileWriter out = new FileWriter(System.getProperty("trace"), true)) {
          out.write(event + "\n");
        } catch (IOException failure) { throw new AssertionError(failure); }
      }
      public PersistableBundle getConfigForSubIdWithFeature(int subId, String callingPackage, String feature) {
        if (subId != 1 || !"com.android.shell".equals(callingPackage) || feature != null)
          throw new AssertionError("Unapproved config caller/subscription");
        trace("carrier-read:" + subId);
        reads++;
        if (Boolean.getBoolean("carrierReadDenied")) throw new SecurityException("private config detail");
        String value = System.getProperty(reads == 1 ? "carrierBefore" : "carrierAfter", "false");
        if (value.equals("absent")) return null;
        if (value.equals("missing")) return new PersistableBundle(Boolean.FALSE, false);
        if (value.equals("null")) return new PersistableBundle(null, true);
        if (value.equals("true") || value.equals("false"))
          return new PersistableBundle(Boolean.valueOf(value), true);
        return new PersistableBundle(value, true);
      }
      public void notifyConfigChangedForSubId(int subId) {
        if (subId != 1) throw new AssertionError("Unapproved refresh subscription");
        trace("carrier-refresh-attempt:" + subId);
        if (Boolean.getBoolean("carrierRefreshDenied")) throw new SecurityException("private refresh detail");
        if (Boolean.getBoolean("carrierRefreshFailure")) throw new IllegalStateException("private failure detail");
        trace("carrier-refresh-returned:" + subId);
      }
    }
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
        if (snapshot >= 5) value = System.getProperty("finalActive", value);
        if (value.isEmpty()) return new int[0];
        String[] fields = value.split(",");
        int[] result = new int[fields.length];
        for (int i = 0; i < fields.length; i++) result[i] = Integer.parseInt(fields[i]);
        return result;
      }
      public int getDefaultDataSubId() {
        if (snapshot == 2) return Integer.getInteger("beforeDefault", data);
        if (snapshot >= 5) return Integer.getInteger("finalDefault", Integer.getInteger("afterDefault", data));
        if (snapshot == 4) return Integer.getInteger("refreshDefault", Integer.getInteger("afterDefault", data));
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
        self.assertLessEqual(sum(row.startswith('carrier-refresh-attempt:') for row in calls), 1)
        return result.returncode, value, calls

    def test_invalid_default_is_initialized_once_and_read_back(self):
        code, value, calls = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(value['status'], 'passed')
        self.assertEqual(set(value), {'schema', 'kind', 'runNonce', 'status', 'uid', 'androidSdk',
                                     'qemu', 'abi', 'hardware', 'initial', 'beforeWrite', 'after',
                                     'setCalls', 'carrierConfig', 'applicationAcceptance', 'physicalPhoneAcceptance', 'networkAcceptance'})
        self.assertEqual(value['schema'], 2)
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

    def test_real_carrier_entry_is_requested_only_for_observed_missing_state(self):
        cases = [({'carrierBefore': 'false'}, 1, 1),
                 ({'carrierBefore': 'true'}, 1, 1),
                 ({'default': 1, 'carrierBefore': 'false'}, 0, 1),
                 ({'default': 1, 'carrierBefore': 'true'}, 0, 0),
                 ({'beforeDefault': 1, 'afterDefault': 1, 'carrierBefore': 'true'}, 0, 1)]
        for properties, writes, refreshes in cases:
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 0)
                self.assertEqual(value['setCalls'], writes)
                carrier = value['carrierConfig']
                self.assertEqual(set(carrier), {'subscriptionId', 'slotIndex', 'simStateBefore',
                                               'simStateAfter', 'appliedBefore', 'appliedAfter',
                                               'refreshCalls', 'asynchronous'})
                self.assertEqual(carrier['subscriptionId'], 1)
                self.assertEqual(carrier['slotIndex'], 0)
                self.assertEqual(carrier['simStateBefore'], 10)
                self.assertEqual(carrier['simStateAfter'], 10)
                self.assertIs(type(carrier['appliedBefore']), bool)
                self.assertIs(type(carrier['appliedAfter']), bool)
                self.assertIs(carrier['asynchronous'], True)
                self.assertEqual(carrier['refreshCalls'], refreshes)
                self.assertEqual(sum(x.startswith('carrier-refresh-attempt:') for x in calls), refreshes)
                self.assertEqual(sum(x.startswith('carrier-refresh-returned:') for x in calls), refreshes)

    def test_asynchronous_config_flag_is_only_observed_not_declared_network_acceptance(self):
        for after in ('false', 'true'):
            with self.subTest(after=after):
                code, value, calls = self.execute({'carrierAfter': after})
                self.assertEqual(code, 0)
                self.assertIs(value['carrierConfig']['appliedAfter'], after == 'true')
                self.assertEqual(value['carrierConfig']['refreshCalls'], 1)
                self.assertIs(value['networkAcceptance'], False)
                self.assertEqual(sum(x.startswith('carrier-read:') for x in calls), 2)

    def test_missing_or_mistyped_config_is_not_fabricated_or_retried(self):
        for field in ('carrierBefore', 'carrierAfter'):
            for invalid in ('absent', 'missing', 'null', 'wrong', '1'):
                with self.subTest(field=field, invalid=invalid):
                    code, value, calls = self.execute({field: invalid})
                    self.assertEqual(code, 1)
                    self.assertEqual(value['setCalls'], 0 if field == 'carrierBefore' else 1)
                    self.assertEqual(value['carrierRefreshCalls'], 0 if field == 'carrierBefore' else 1)

    def test_actual_sim_and_subscription_changes_do_not_allow_another_mutation(self):
        for properties, writes, refreshes in [({'simState': 0}, 0, 0), ({'simState': 5}, 0, 0),
                ({'sim2': 5}, 0, 0), ({'sim3': 5}, 1, 0), ({'sim4': 5}, 1, 1),
                ({'refreshDefault': -1}, 1, 0), ({'finalDefault': -1}, 1, 1),
                ({'finalActive': '2'}, 1, 1)]:
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], writes)
                self.assertEqual(value['carrierRefreshCalls'], refreshes)

    def test_new_named_services_and_permission_failures_remain_failures(self):
        for properties in ({'phoneServiceAbsent': 'true'}, {'carrierServiceAbsent': 'true'},
                           {'phoneInterfaceAbsent': 'true'}, {'carrierInterfaceAbsent': 'true'},
                           {'phoneDescriptor': 'wrong'}, {'carrierDescriptor': 'wrong'},
                           {'simReadDenied': 'true'}, {'carrierReadDenied': 'true'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 0)
                self.assertEqual(value['carrierRefreshCalls'], 0)
        for properties in ({'carrierRefreshDenied': 'true'}, {'carrierRefreshFailure': 'true'}):
            with self.subTest(properties=properties):
                code, value, calls = self.execute(properties)
                self.assertEqual(code, 1)
                self.assertEqual(value['setCalls'], 1)
                self.assertEqual(value['carrierRefreshCalls'], 1)
                self.assertEqual(sum(x.startswith('carrier-refresh-returned:') for x in calls), 0)
                self.assertNotIn('private', json.dumps(value))


if __name__ == '__main__':
    unittest.main()
