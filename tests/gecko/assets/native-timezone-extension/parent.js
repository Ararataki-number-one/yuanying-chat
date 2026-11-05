'use strict';

// This file runs in the app-bundled extension's privileged parent context.
// The setter below is the existing engine's native BrowsingContext property.
// It neither modifies Date/Intl nor starts a debugging or WebDriver endpoint.
var { ExtensionCommon } = ChromeUtils.importESModule(
  'resource://gre/modules/ExtensionCommon.sys.mjs'
);
var { ExtensionUtils } = ChromeUtils.importESModule(
  'resource://gre/modules/ExtensionUtils.sys.mjs'
);
const TimezoneError = ExtensionUtils.ExtensionError;

this.pocketNativeTimezone = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    const extension = context.extension;
    if (!extension.isPrivileged || !new Set([
      'timezone-probe@pocketchat.local', 'browser@pocketchat.local'
    ]).has(extension.id)) throw new TimezoneError('app-bundled-timezone-api-only');

    const token = value => {
      if (typeof value !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value)) {
        throw new TimezoneError('invalid-timezone-request-token');
      }
      return value;
    };
    const nativeContext = tabId => {
      if (!Number.isSafeInteger(tabId) || tabId < 0) throw new TimezoneError('invalid-timezone-tab');
      const tab = extension.tabManager.get(tabId);
      if (!tab || !extension.tabManager.canAccessTab(tab.nativeTab)) {
        throw new TimezoneError('timezone-tab-unavailable');
      }
      const top = tab.browser?.browsingContext?.top;
      if (!top || !('timezoneOverride' in top) || !/^\d+$/.test(String(top.id))) {
        throw new TimezoneError('native-timezone-property-unavailable');
      }
      return top;
    };
    const zone = value => {
      if (typeof value !== 'string' || value.length > 80 ||
          value && !/^[A-Za-z0-9_+\/-]+$/.test(value)) throw new TimezoneError('invalid-timezone-id');
      // Empty string is the native API's reset-to-system value. Validate all
      // other IDs in this privileged realm before mutating the native setting.
      if (value) {
        try { new Intl.DateTimeFormat('en-US', {timeZone: value}); }
        catch (_) { throw new TimezoneError('invalid-timezone-id'); }
      }
      return value;
    };
    const receipt = (top, requestToken, requestedZoneId, status) => {
      const nativeZoneId = top.timezoneOverride;
      if (typeof nativeZoneId !== 'string') throw new TimezoneError('native-timezone-readback-unavailable');
      return {schema: 1, status, requestToken, requestedZoneId, nativeZoneId,
        contextId: String(top.id), nativeSettingReadback: true,
        scope: 'top-browsing-context', workerCoverageVerified: false,
        serviceWorkerCoverageVerified: false};
    };
    return {pocketNativeTimezone: {
      async apply(tabId, zoneId, requestToken) {
        token(requestToken); zone(zoneId);
        const top = nativeContext(tabId);
        top.timezoneOverride = zoneId;
        return receipt(top, requestToken, zoneId, 'applied');
      },
      async read(tabId, requestToken) {
        token(requestToken);
        const top = nativeContext(tabId);
        return receipt(top, requestToken, top.timezoneOverride, 'read');
      }
    }};
  }
};
