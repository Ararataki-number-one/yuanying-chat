package org.pocketchat.synthetic;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;

/**
 * One default-data initialization on the fixed, fresh CI emulator.
 *
 * This tool is compiled outside both APKs and runs as the existing adb shell
 * UID. It uses the device's own named ISub interface, not a locally generated
 * AIDL proxy or numeric Binder transaction. It never changes permissions,
 * hidden-API policy, mobile-data enablement, provisioning or input settings.
 * A successful result is only a subscription readback, never network proof.
 */
public final class EmulatorDataSubscription {
    private static final String KIND = "synthetic-default-data-subscription";
    private static int setCalls;
    private static String nonce = "";
    private static Object subscription;
    private static Method activeIds;
    private static Method defaultId;
    private static Method phoneId;
    private static Method slotId;
    private static Method setDefaultId;

    private static final class Rejected extends Exception {
        Rejected(String reason) { super(reason); }
    }

    private static void require(boolean condition, String reason) throws Rejected {
        if (!condition) throw new Rejected(reason);
    }

    private static Object call(Method method, Object receiver, Object... args) throws Exception {
        try {
            return method.invoke(receiver, args);
        } catch (InvocationTargetException error) {
            // Do not leak framework exception messages or attempt another API.
            throw new Rejected(error.getCause() instanceof SecurityException
                    ? "permission-denied" : "binder-call-failed");
        }
    }

    private static String property(String key) throws Exception {
        Class<?> properties = Class.forName("android.os.SystemProperties");
        Object value = call(properties.getMethod("get", String.class), null, key);
        require(value instanceof String, "invalid-runtime-property");
        return (String) value;
    }

    private static void guardRuntime() throws Exception {
        Object uid = call(Class.forName("android.os.Process").getMethod("myUid"), null);
        require(uid instanceof Integer && ((Integer) uid).intValue() == 2000,
                "shell-uid-required");
        require("1".equals(property("ro.kernel.qemu"))
                && "35".equals(property("ro.build.version.sdk"))
                && "x86_64".equals(property("ro.product.cpu.abi"))
                && "ranchu".equals(property("ro.hardware")), "fixed-qemu-required");
    }

    private static void connect() throws Exception {
        Class<?> binderType = Class.forName("android.os.IBinder");
        Object binder = call(Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class), null, "isub");
        require(binder != null, "subscription-service-unavailable");
        require("com.android.internal.telephony.ISub".equals(call(
                binderType.getMethod("getInterfaceDescriptor"), binder)),
                "unexpected-binder-interface");
        Class<?> api = Class.forName("com.android.internal.telephony.ISub");
        Class<?> stub = Class.forName("com.android.internal.telephony.ISub$Stub");
        subscription = call(stub.getMethod("asInterface", binderType), null, binder);
        require(subscription != null && api.isInstance(subscription),
                "subscription-interface-unavailable");
        // Invoke public interface methods even when the framework Proxy class
        // itself is private. The bootclasspath supplies the complete real ABI.
        activeIds = api.getMethod("getActiveSubIdList", boolean.class);
        defaultId = api.getMethod("getDefaultDataSubId");
        phoneId = api.getMethod("getPhoneId", int.class);
        slotId = api.getMethod("getSubId", int.class);
        setDefaultId = api.getMethod("setDefaultDataSubId", int.class);
    }

    private static int integer(Method method, Object... arguments) throws Exception {
        Object value = call(method, subscription, arguments);
        require(value instanceof Integer, "invalid-subscription-value");
        return ((Integer) value).intValue();
    }

    private static final class Snapshot {
        final int[] active;
        final int data;
        final int phone;
        final int slot;

        Snapshot(int[] active, int data, int phone, int slot) {
            this.active = active.clone();
            this.data = data;
            this.phone = phone;
            this.slot = slot;
        }

        String json() {
            return "{\"activeSubscriptionIds\":[" + active[0]
                    + "],\"defaultDataSubId\":" + data
                    + ",\"phoneId\":" + phone
                    + ",\"slotSubscriptionId\":" + slot + "}";
        }
    }

    private static Snapshot snapshot() throws Exception {
        // false includes opportunistic/hidden active entries: never hide a
        // second subscription merely to make the single-subscription gate pass.
        Object observed = call(activeIds, subscription, Boolean.FALSE);
        require(observed instanceof int[], "invalid-active-subscriptions");
        int[] ids = ((int[]) observed).clone();
        require(ids.length == 1 && ids[0] > 0 && ids[0] != Integer.MAX_VALUE,
                "single-active-subscription-required");
        int data = integer(defaultId);
        int phone = integer(phoneId, Integer.valueOf(ids[0]));
        int slot = integer(slotId, Integer.valueOf(0));
        require(phone == 0 && slot == ids[0], "single-slot-mapping-required");
        require(data == -1 || data == ids[0], "different-default-subscription");
        return new Snapshot(ids, data, phone, slot);
    }

    private static void sameMapping(Snapshot first, Snapshot second) throws Rejected {
        require(Arrays.equals(first.active, second.active)
                && first.phone == second.phone && first.slot == second.slot,
                "subscription-mapping-changed");
    }

    private static void execute() throws Exception {
        guardRuntime();
        connect();
        Snapshot initial = snapshot();
        guardRuntime();
        Snapshot before = snapshot();
        sameMapping(initial, before);
        require(before.data == initial.data
                || (initial.data == -1 && before.data == initial.active[0]),
                "default-subscription-changed");
        if (before.data == -1) {
            // This is not a general atomic compare-and-set API. The caller
            // permits only a fresh one-slot QEMU and this invocation performs
            // at most one setter, followed by a new complete actual readback.
            require(setCalls == 0, "initialization-already-attempted");
            setCalls++;
            call(setDefaultId, subscription, Integer.valueOf(before.active[0]));
        }
        guardRuntime();
        Snapshot after = snapshot();
        sameMapping(initial, after);
        require(after.data == initial.active[0], "default-subscription-not-confirmed");
        System.out.println("{\"schema\":1,\"kind\":\"" + KIND
                + "\",\"runNonce\":\"" + nonce + "\",\"status\":\"passed\""
                + ",\"uid\":2000,\"androidSdk\":35,\"qemu\":true"
                + ",\"abi\":\"x86_64\",\"hardware\":\"ranchu\""
                + ",\"initial\":" + initial.json()
                + ",\"beforeWrite\":" + before.json()
                + ",\"after\":" + after.json()
                + ",\"setCalls\":" + setCalls
                + ",\"applicationAcceptance\":false,\"physicalPhoneAcceptance\":false"
                + ",\"networkAcceptance\":false}");
    }

    public static void main(String[] args) {
        String reason;
        try {
            require(args.length == 1 && args[0].matches("[0-9a-f]{32}"), "invalid-invocation");
            nonce = args[0];
            execute();
            return;
        } catch (Rejected failure) {
            reason = failure.getMessage();
        } catch (SecurityException failure) {
            reason = "permission-denied";
        } catch (Exception failure) {
            reason = "named-api-unavailable";
        } catch (LinkageError failure) {
            reason = "named-api-unavailable";
        }
        System.out.println("{\"schema\":1,\"kind\":\"" + KIND
                + "\",\"runNonce\":\"" + nonce + "\",\"status\":\"failed\""
                + ",\"reason\":\"" + reason + "\",\"setCalls\":" + setCalls
                + ",\"applicationAcceptance\":false,\"physicalPhoneAcceptance\":false"
                + ",\"networkAcceptance\":false}");
        System.exit(1);
    }
}
