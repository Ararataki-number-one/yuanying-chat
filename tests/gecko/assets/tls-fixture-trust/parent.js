'use strict';

// Integration-only observation of NSS. No certificate is inserted, trusted,
// overridden or fetched here. The sole enable call remains the public Java SDK.
var { ExtensionCommon } = ChromeUtils.importESModule('resource://gre/modules/ExtensionCommon.sys.mjs');
var { ExtensionUtils } = ChromeUtils.importESModule('resource://gre/modules/ExtensionUtils.sys.mjs');
const TrustError = ExtensionUtils.ExtensionError;
const PREF = 'security.enterprise_roots.enabled';
const TOPIC = 'psm:enterprise-certs-imported';
const KEYS = ['sourceCommit', 'sourceTree', 'runNonce', 'caseNonce', 'bootCaseNonce',
  'runtimeNonce', 'processNonce', 'challengeNonce', 'expectedCaDerSha256', 'pid', 'slot'];
const BOOT_KEYS = KEYS.filter(key => !['caseNonce', 'challengeNonce'].includes(key));

this.pocketFixtureTrust = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    if (!context.extension.isPrivileged || context.extension.id !== 'tls-fixture-trust@pocketchat.local') {
      throw new TrustError('fixture-trust-builtin-only');
    }
    let state = null;
    const fail = reason => { throw new TrustError(reason); };
    const binding = value => {
      if (!value || typeof value !== 'object' || Object.keys(value).sort().join() !== [...KEYS].sort().join()) fail('fixture-trust-binding');
      for (const key of KEYS.filter(key => !['pid', 'slot'].includes(key))) {
        const size = ['sourceCommit', 'sourceTree'].includes(key) ? 40 : key === 'expectedCaDerSha256' ? 64 : 32;
        if (typeof value[key] !== 'string' || !new RegExp(`^[0-9a-f]{${size}}$`).test(value[key])) fail('fixture-trust-binding');
      }
      if (!Number.isSafeInteger(value.pid) || value.pid < 1 || ![1, 2, 6].includes(value.slot)) fail('fixture-trust-binding');
      return {...value};
    };
    const live = () => {
      if (!state || state.closed) fail('fixture-trust-retired');
      return state;
    };
    const nativePref = expected => {
      if (Services.prefs.getBoolPref(PREF, false) !== expected || Services.prefs.prefHasUserValue(PREF)) fail('fixture-trust-native-pref');
    };
    const removeObserver = value => {
      if (value.listening) { Services.obs.removeObserver(value.observer, TOPIC); value.listening = false; }
    };
    const readRoots = value => {
      nativePref(true);
      const roots = value.nss.getEnterpriseRoots();
      if (!Array.isArray(roots) || roots.length < 1 || roots.length > 1024) fail('fixture-trust-native-roots');
      let match = null, matches = 0, bytes = 0;
      for (const der of roots) {
        if (!der || !Number.isSafeInteger(der.length) || der.length < 1 || der.length > 65536 || (bytes += der.length) > 4194304) fail('fixture-trust-native-roots');
        const cert = value.certdb.constructX509(der);
        const sha = cert.sha256Fingerprint.replaceAll(':', '').toLowerCase();
        if (!/^[0-9a-f]{64}$/.test(sha)) fail('fixture-trust-native-root-digest');
        if (sha === value.boot.expectedCaDerSha256) { match = cert; matches++; }
      }
      if (matches !== 1) fail('fixture-trust-exact-root-missing');
      const notBefore = match.validity.notBefore / 1000, notAfter = match.validity.notAfter / 1000;
      const now = Date.now();
      if (![notBefore, notAfter, now].every(Number.isSafeInteger) || notBefore >= notAfter) fail('fixture-trust-native-validity');
      return {nativeEffective: true, nativeHasUserValue: false, nativeGetEnterpriseRoots: true,
        rootMatches: matches, caDerSha256: value.boot.expectedCaDerSha256,
        caNotBeforeMs: notBefore, caNotAfterMs: notAfter, nativeReadUtcMs: now};
    };
    const receipt = (value, request) => ({schema: 1, binding: request, importEventCount: value.events,
      importedEventObserved: true, importTopic: TOPIC, importedAtUtcMs: value.importedAt,
      ...readRoots(value)});
    const close = () => {
      if (!state || state.closed) return;
      state.closed = true; removeObserver(state);
      if (!state.completed) state.reject(new TrustError('fixture-trust-retired'));
    };
    context.callOnClose({close});
    return {pocketFixtureTrust: {
      async arm(input) {
        const request = binding(input);
        if (state || request.caseNonce !== request.bootCaseNonce) fail('fixture-trust-duplicate-arm');
        nativePref(false);
        const nss = Cc['@mozilla.org/psm;1'].getService(Ci.nsINSSComponent);
        const certdb = Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB);
        if (typeof nss.getEnterpriseRoots !== 'function' || typeof certdb.constructX509 !== 'function') fail('fixture-trust-native-api');
        const value = {boot: request, nss, certdb, closed: false, completed: false,
          listening: false, events: 0, importedAt: 0, cases: new Set([request.caseNonce]),
          challenges: new Set([request.challengeNonce])};
        value.promise = new Promise((resolve, reject) => { value.resolve = resolve; value.reject = reject; });
        // A native callback can arrive before waitImported gets its next task.
        // Keep the original rejection handled without replacing its result.
        value.promise.catch(() => {});
        value.observer = (_subject, topic) => {
          if (value.closed || state !== value) return;
          removeObserver(value);
          try {
            if (topic !== TOPIC || ++value.events !== 1) fail('fixture-trust-import-event');
            // In pinned Gecko 157 this notification follows BOTH ImportEnterpriseRoots
            // and UpdateCertVerifierWithEnterpriseRoots, unlike preference readback.
            nativePref(true); value.importedAt = Date.now();
            const actual = receipt(value, request);
            value.completed = true; value.resolve(actual);
          } catch (error) { value.reject(error); }
        };
        state = value;
        Services.obs.addObserver(value.observer, TOPIC); value.listening = true;
        nativePref(false);
        return {schema: 1, binding: request, observerRegistered: true,
          nativeEffective: false, nativeHasUserValue: false, importEventCount: 0};
      },
      async waitImported(input) {
        const request = binding(input), value = live();
        if (KEYS.some(key => request[key] !== value.boot[key])) fail('fixture-trust-binding');
        return value.promise;
      },
      async read(input) {
        const request = binding(input), value = live();
        if (!value.completed || BOOT_KEYS.some(key => request[key] !== value.boot[key]) ||
            value.cases.has(request.caseNonce) || value.challenges.has(request.challengeNonce) || value.cases.size >= 11) fail('fixture-trust-resample-binding');
        value.cases.add(request.caseNonce); value.challenges.add(request.challengeNonce);
        return receipt(value, request);
      },
      async close() { close(); }
    }};
  }
};
