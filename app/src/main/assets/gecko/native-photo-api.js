'use strict';

// RFP replaces unpermitted canvas exports with placeholder pixels. A user-chosen
// photo must be encoded by the page with its original pixels. This bundled API
// leases only the native canvas permission; it never changes the RFP preference.
// Gecko 157 consumes origin permissions for canvas, not tab-scoped permissions:
// same-origin tabs in the same origin-attributes namespace share a short lease.
var { ExtensionCommon } = ChromeUtils.importESModule('resource://gre/modules/ExtensionCommon.sys.mjs');
var { ExtensionUtils } = ChromeUtils.importESModule('resource://gre/modules/ExtensionUtils.sys.mjs');
var { setTimeout, clearTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
const PhotoError = ExtensionUtils.ExtensionError;

this.pocketNativePhoto = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    if (context.envType !== 'addon_parent' || context.extension.id !== 'browser@pocketchat.local' ||
        context.extension.isPrivileged !== true) throw new PhotoError('app-bundled-photo-api-only');
    const permissions = Cc['@mozilla.org/permissionmanager;1'].getService(Ci.nsIPermissionManager);
    const prefs = Cc['@mozilla.org/preferences-service;1'].getService(Ci.nsIPrefBranch);
    const captures = new Map(), groups = new Map();
    const LEASE_MS = 120000, PICKER_MS = 900000, MAX_CAPTURES = 32;
    const identity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,160}$/.test(value);
    const key = (sessionId, token) => sessionId + '\n' + token;
    const validate = (sessionId, token) => {
      if (!identity(sessionId) || !identity(token)) throw new PhotoError('invalid-photo-identity');
    };
    const nativeContext = (sessionId, expectedOrigin) => {
      const windows = Cc['@mozilla.org/appshell/window-mediator;1'].getService(Ci.nsIWindowMediator).getEnumerator(null);
      let match = null, count = 0;
      while (windows.hasMoreElements()) {
        if (++count > 128) throw new PhotoError('photo-window-enumeration-bound');
        const window = windows.getNext();
        if (window.name !== sessionId) continue;
        if (match) throw new PhotoError('photo-session-ambiguous');
        if (window.closed !== false || !['navigator:geckoview', 'navigator:popup'].includes(
            window.document?.documentElement?.getAttribute('windowtype'))) throw new PhotoError('photo-session-unavailable');
        const browser = window.browser, top = browser?.browsingContext?.top;
        const global = top?.currentWindowGlobal, principal = global?.documentPrincipal;
        // Native principals retain the actual private/container origin attributes.
        // HTTP is accepted only here for embedding test fixtures; the production
        // Java entry admits HTTPS and does not loosen navigation policy.
        if (!top || !global || !principal?.isContentPrincipal ||
            !['https', 'http'].includes(principal.URI?.scheme) || principal.originNoSuffix !== expectedOrigin ||
            !/^[1-9][0-9]{0,23}$/.test(String(global.innerWindowId)) || !browser.webProgress)
          throw new PhotoError('photo-document-unavailable');
        // Gecko 157 strips userContextId from canvas permissions by default.
        // This app isolates environments with separate native profiles; never
        // silently broaden an exception if a future embedding uses containers.
        if (principal.originAttributes.userContextId) throw new PhotoError('photo-container-permission-unavailable');
        match = {window, browser, top, global, principal, documentId: String(global.innerWindowId)};
      }
      if (!match) throw new PhotoError('photo-session-unavailable');
      return match;
    };
    const current = claim => {
      try {
        const live = nativeContext(claim.sessionId, claim.origin);
        return live.window === claim.window && live.browser === claim.browser && live.top === claim.top &&
          live.global === claim.global && live.documentId === claim.documentId && live.principal.equals(claim.principal);
      } catch (_) { return false; }
    };
    const record = principal => permissions.getPermissionObject(principal, 'canvas', true);
    const owned = group => {
      if (group.retired) return false;
      const value = record(group.principal);
      return value && value.capability === permissions.ALLOW_ACTION &&
        value.expireType === permissions.EXPIRE_SESSION && value.expireTime === group.expiresAt;
    };
    const receipt = (claim, status, reason = '') => ({schema: 1, status, requestToken: claim.requestToken,
      sessionId: claim.sessionId, origin: claim.origin, documentId: claim.documentId,
      expiresAt: status === 'granted' ? claim.expiresAt : 0, scope: 'origin-and-origin-attributes', reason});
    const forgetGroup = group => {
      if (groups.get(group.key) === group) groups.delete(group.key);
      group.retired = true;
      for (const claim of group.claims) claim.group = null;
      group.claims.clear();
    };
    const installGroup = (group, expiresAt) => {
      const previous = group.expiresAt; group.expiresAt = expiresAt;
      try {
        permissions.addFromPrincipal(group.principal, 'canvas', permissions.ALLOW_ACTION,
          permissions.EXPIRE_SESSION, expiresAt);
      } catch (error) {
        // A native setter failure does not establish whether it wrote. Track the
        // exact value that is actually present before cleanup touches anything.
        if (!owned(group)) group.expiresAt = previous;
        throw error;
      }
    };
    const updateGroup = group => {
      if (!owned(group)) { forgetGroup(group); return; }
      if (group.claims.size) {
        const expiresAt = Math.max(...Array.from(group.claims, claim => claim.expiresAt));
        if (expiresAt !== group.expiresAt) installGroup(group, expiresAt);
        return;
      }
      permissions.removeFromPrincipal(group.principal, 'canvas');
      // Never remove a pre-existing allow/deny. A prompt/default record, if any,
      // is restored only while the native permission still exactly belongs to us.
      const prior = group.prior;
      if (prior && (!prior.expireTime || prior.expireTime > Date.now()))
        permissions.addFromPrincipal(group.principal, 'canvas', prior.capability, prior.expireType, prior.expireTime);
      forgetGroup(group);
    };
    const release = claim => {
      if (!claim || captures.get(claim.key) !== claim) return;
      captures.delete(claim.key); clearTimeout(claim.timer);
      try { claim.browser.webProgress.removeProgressListener(claim.listener); } catch (_) {}
      try { claim.window.removeEventListener('unload', claim.leave); } catch (_) {}
      if (claim.group) {
        claim.group.claims.delete(claim);
        // The native EXPIRE_SESSION deadline remains effective even if teardown
        // cannot reach the permission service (including process shutdown).
        try { updateGroup(claim.group); } catch (_) {}
      }
    };
    const releaseAll = () => { for (const claim of Array.from(captures.values())) release(claim); };
    context.callOnClose({close: releaseAll});
    this.closePhotoPermissions = releaseAll;
    return {pocketNativePhoto: {
      async captureSession(sessionId, origin, requestToken) {
        validate(sessionId, requestToken);
        if (typeof origin !== 'string' || origin.length > 2048 || !/^https?:\/\/[^/?#]+$/.test(origin))
          throw new PhotoError('invalid-photo-origin');
        const id = key(sessionId, requestToken);
        if (captures.has(id) || captures.size >= MAX_CAPTURES) throw new PhotoError('photo-capture-bound');
        const match = nativeContext(sessionId, origin);
        const claim = {...match, key: id, sessionId, requestToken, origin, group: null, expiresAt: 0,
          captureExpiresAt: Date.now() + PICKER_MS};
        claim.leave = () => release(claim);
        claim.listener = {
          QueryInterface: ChromeUtils.generateQI(['nsIWebProgressListener', 'nsISupportsWeakReference']),
          onStateChange(progress, request, flags) {
            if (progress.isTopLevel && (flags & Ci.nsIWebProgressListener.STATE_START) &&
                (flags & Ci.nsIWebProgressListener.STATE_IS_DOCUMENT)) release(claim);
          },
          onLocationChange(progress) { if (progress.isTopLevel && !current(claim)) release(claim); },
          onProgressChange() {}, onStatusChange() {}, onSecurityChange() {}, onContentBlockingEvent() {}
        };
        captures.set(id, claim);
        try {
          match.browser.webProgress.addProgressListener(claim.listener,
            Ci.nsIWebProgress.NOTIFY_STATE_DOCUMENT | Ci.nsIWebProgress.NOTIFY_LOCATION);
          match.window.addEventListener('unload', claim.leave);
          claim.timer = setTimeout(claim.leave, PICKER_MS);
          if (!current(claim)) throw new PhotoError('photo-document-replaced');
          return receipt(claim, 'captured');
        } catch (error) { release(claim); throw error; }
      },
      async grantSession(sessionId, requestToken) {
        validate(sessionId, requestToken);
        const claim = captures.get(key(sessionId, requestToken));
        if (!claim || claim.group || Date.now() >= claim.captureExpiresAt || !current(claim)) {
          release(claim); throw new PhotoError('photo-capture-stale');
        }
        try {
          const rfp = prefs.getBoolPref('privacy.resistFingerprinting', false) ||
            claim.principal.originAttributes.privateBrowsingId > 0 && prefs.getBoolPref('privacy.resistFingerprinting.pbmode', false);
          if (!rfp) { const result = receipt(claim, 'not-required'); release(claim); return result; }
          const permission = permissions.testPermissionFromPrincipal(claim.principal, 'canvas');
          const previousRecord = record(claim.principal);
          if (previousRecord && !previousRecord.principal.equals(claim.principal))
            throw new PhotoError('photo-permission-namespace-unavailable');
          if (permission === permissions.DENY_ACTION) { const result = receipt(claim, 'denied', 'stored-canvas-denial'); release(claim); return result; }
          const groupKey = claim.principal.origin;
          let group = groups.get(groupKey);
          if (group && !owned(group)) { forgetGroup(group); group = null; }
          if (!group && permission === permissions.ALLOW_ACTION) {
            const result = receipt(claim, 'existing'); release(claim); return result;
          }
          if (!group) {
            const previous = previousRecord;
            group = {key: groupKey, principal: claim.principal, claims: new Set(), expiresAt: 0, retired: false,
              prior: previous ? {capability: previous.capability, expireType: previous.expireType, expireTime: previous.expireTime} : null};
          }
          claim.expiresAt = Date.now() + LEASE_MS;
          const expiresAt = Math.max(group.expiresAt, claim.expiresAt);
          group.claims.add(claim); claim.group = group; groups.set(groupKey, group);
          installGroup(group, expiresAt);
          if (!current(claim) || !owned(group) || !record(claim.principal)?.principal.equals(claim.principal))
            throw new PhotoError('photo-permission-unconfirmed');
          clearTimeout(claim.timer); claim.timer = setTimeout(claim.leave, LEASE_MS);
          return receipt(claim, 'granted');
        } catch (error) { release(claim); throw error; }
      },
      async releaseSession(sessionId, requestToken) {
        validate(sessionId, requestToken); release(captures.get(key(sessionId, requestToken))); return true;
      },
      async releaseAll() { releaseAll(); return true; }
    }};
  }
  onShutdown() { this.closePhotoPermissions?.(); }
};
