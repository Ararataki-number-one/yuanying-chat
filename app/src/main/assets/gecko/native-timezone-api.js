'use strict';

// Installed solely by this APK's privileged built-in integration extension.
// Settings use the existing native BrowsingContext property. Page prototypes,
// global Android time settings and the engine's RFP policy are untouched.
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
    if (context.envType !== 'addon_parent' || extension.id !== 'browser@pocketchat.local' ||
        extension.isPrivileged !== true) {
      throw new TimezoneError('app-bundled-timezone-api-only');
    }
    const boundedIdentity = (value, kind) => {
      if (typeof value !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value)) {
        throw new TimezoneError('invalid-timezone-' + kind);
      }
      return value;
    };
    const nativeContext = sessionId => {
      boundedIdentity(sessionId, 'session');
      let match = null;
      let count = 0;
      try {
        const mediator = Cc['@mozilla.org/appshell/window-mediator;1']
          .getService(Ci.nsIWindowMediator);
        const windows = mediator.getEnumerator(null);
        while (windows.hasMoreElements()) {
          if (++count > 128) throw new TimezoneError('timezone-window-enumeration-bound');
          const window = windows.getNext();
          if (window.name !== sessionId) continue;
          if (match) throw new TimezoneError('timezone-session-ambiguous');
          const type = window.document?.documentElement?.getAttribute('windowtype');
          if (window.closed !== false || !['navigator:geckoview', 'navigator:popup'].includes(type)) {
            throw new TimezoneError('timezone-session-unavailable');
          }
          const browser = window.browser;
          const top = browser?.browsingContext?.top;
          if (!top || !('timezoneOverride' in top) || !/^[1-9][0-9]{0,23}$/.test(String(top.id))) {
            throw new TimezoneError('native-timezone-property-unavailable');
          }
          match = {window, browser, top};
        }
      } catch (error) {
        const known = new Set(['timezone-window-enumeration-bound', 'timezone-session-ambiguous',
          'timezone-session-unavailable', 'native-timezone-property-unavailable']);
        throw new TimezoneError(known.has(error?.message) ? error.message : 'timezone-window-enumeration-unavailable');
      }
      if (!match) throw new TimezoneError('timezone-session-unavailable');
      return match;
    };
    const zone = value => {
      if (typeof value !== 'string' || value.length > 80 ||
          value && !/^[A-Za-z0-9_+\/-]+$/.test(value)) throw new TimezoneError('invalid-timezone-id');
      if (value) {
        try { new Intl.DateTimeFormat('en-US', {timeZone: value}); }
        catch (_) { throw new TimezoneError('invalid-timezone-id'); }
      }
      return value;
    };
    const receipt = (match, sessionId, requestToken, requestedZoneId, status) => {
      const {window, browser, top} = match;
      if (window.closed !== false || window.name !== sessionId || window.browser !== browser ||
          browser.browsingContext?.top !== top) throw new TimezoneError('timezone-session-replaced');
      const nativeZoneId = top.timezoneOverride;
      if (typeof nativeZoneId !== 'string') throw new TimezoneError('native-timezone-readback-unavailable');
      return {schema: 1, status, requestToken, sessionId, requestedZoneId, nativeZoneId,
        contextId: String(top.id), nativeSettingReadback: true,
        scope: 'top-browsing-context', workerCoverageVerified: false,
        serviceWorkerCoverageVerified: false};
    };
    return {pocketNativeTimezone: {
      async applySession(sessionId, zoneId, requestToken) {
        boundedIdentity(requestToken, 'request-token'); zone(zoneId);
        const match = nativeContext(sessionId);
        // A context may already inherit this override after a COOP transition.
        // Reconfirm its actual value without an unnecessary native setter,
        // which can reload the current document even for an unchanged zone.
        if (match.top.timezoneOverride !== zoneId) match.top.timezoneOverride = zoneId;
        return receipt(match, sessionId, requestToken, zoneId, 'applied');
      },
      async readSession(sessionId, requestToken) {
        boundedIdentity(requestToken, 'request-token');
        const match = nativeContext(sessionId);
        return receipt(match, sessionId, requestToken, match.top.timezoneOverride, 'read');
      }
    }};
  }
};
