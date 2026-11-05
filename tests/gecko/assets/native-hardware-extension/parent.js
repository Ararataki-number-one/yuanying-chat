'use strict';
var { ExtensionCommon } = ChromeUtils.importESModule('resource://gre/modules/ExtensionCommon.sys.mjs');
var { ExtensionUtils } = ChromeUtils.importESModule('resource://gre/modules/ExtensionUtils.sys.mjs');
const HardwareError = ExtensionUtils.ExtensionError;

// App-owned capability probe only. The native preference is the sole mutable
// setting; no navigator property, Worker constructor or privacy policy is replaced.
this.pocketNativeHardware = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    if (context.envType !== 'addon_parent' || context.extension.id !== 'hardware-probe@pocketchat.local' ||
        context.extension.isPrivileged !== true) throw new HardwareError('probe-native-hardware-api-only');
    const CPU = 'dom.maxHardwareConcurrency';
    const RFP = 'privacy.resistFingerprinting';
    const token = value => {
      if (typeof value !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value)) {
        throw new HardwareError('invalid-hardware-request-token');
      }
    };
    const branch = () => {
      try {
        const prefs = Cc['@mozilla.org/preferences-service;1'].getService(Ci.nsIPrefBranch);
        if (prefs.getPrefType(CPU) !== Ci.nsIPrefBranch.PREF_INT) throw new Error();
        return prefs;
      } catch (_) { throw new HardwareError('native-hardware-pref-unavailable'); }
    };
    const snapshot = prefs => {
      try {
        const configuredCap = prefs.getIntPref(CPU);
        const hasUserValue = prefs.prefHasUserValue(CPU);
        const rfpEnabled = prefs.getBoolPref(RFP, false);
        if (!Number.isSafeInteger(configuredCap) || configuredCap < 1 || configuredCap > 65536 ||
            typeof hasUserValue !== 'boolean' || typeof rfpEnabled !== 'boolean') throw new Error();
        return {configuredCap, hasUserValue, rfpEnabled};
      } catch (_) { throw new HardwareError('native-hardware-readback-unavailable'); }
    };
    const receipt = (value, operation, status, requestedCap, requestToken) => ({
      schema: 1, status, operation, requestToken, requestedCap, ...value,
      nativePreferenceReadback: true, scope: 'runtime-native-pref',
      workerCoverageVerified: false, fingerprintProtectionVerified: false
    });
    const change = (operation, cap, requestToken) => {
      token(requestToken);
      if (operation === 'set' && (!Number.isSafeInteger(cap) || ![1, 2].includes(cap))) {
        throw new HardwareError('invalid-hardware-cap');
      }
      const prefs = branch(), before = snapshot(prefs);
      try {
        if (operation === 'set') prefs.setIntPref(CPU, cap);
        else if (operation === 'reset') prefs.clearUserPref(CPU);
        else throw new Error();
      } catch (_) { throw new HardwareError('native-hardware-setting-failed'); }
      const after = snapshot(prefs);
      if (before.rfpEnabled !== after.rfpEnabled) throw new HardwareError('native-rfp-policy-changed');
      if (operation === 'set' && (after.configuredCap !== cap || !after.hasUserValue) ||
          operation === 'reset' && after.hasUserValue) throw new HardwareError('native-hardware-readback-mismatch');
      return receipt(after, operation, operation === 'set' ? 'applied' : 'reset', cap, requestToken);
    };
    return {pocketNativeHardware: {
      async read(requestToken) { token(requestToken); return receipt(snapshot(branch()), 'read', 'read', null, requestToken); },
      async setCap(cap, requestToken) { return change('set', cap, requestToken); },
      async reset(requestToken) { return change('reset', null, requestToken); }
    }};
  }
};
