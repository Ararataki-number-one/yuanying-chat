/* Only background native-host messages reach this adapter; no page listener. */
(() => {
  'use strict';
  const identity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,160}$/.test(value);
  const failure = () => ({schema:1,status:'failed',reason:'native-photo-permission-unavailable'});
  globalThis.PocketNativePhotoBridge = Object.freeze({
    async handle(message) {
      if (!message || typeof message !== 'object' || Array.isArray(message)) return failure();
      const request = {kind:message.kind,id:message.id,sessionId:message.sessionId,requestToken:message.requestToken};
      const capture = request.kind === 'photoCanvasCapture', grant = request.kind === 'photoCanvasGrant';
      if (!capture && !grant && request.kind !== 'photoCanvasRelease' ||
          !Number.isInteger(request.id) || request.id < 1 || request.id > 2147483647 ||
          !identity(request.sessionId) || !identity(request.requestToken)) return failure();
      const keys = ['kind','id','sessionId','requestToken'];
      if (capture) { keys.push('origin'); request.origin = message.origin;
        if (typeof request.origin !== 'string' || request.origin.length > 2048) return failure(); }
      if (Object.keys(message).sort().join(',') !== keys.sort().join(',')) return failure();
      try {
        const api = browser.pocketNativePhoto;
        if (!capture && !grant) return {schema:1,status:await api.releaseSession(request.sessionId,request.requestToken) === true ? 'released' : 'failed'};
        const value = capture ? await api.captureSession(request.sessionId,request.origin,request.requestToken)
          : await api.grantSession(request.sessionId,request.requestToken);
        if (!value || value.schema !== 1 || value.sessionId !== request.sessionId || value.requestToken !== request.requestToken ||
            value.scope !== 'origin-and-origin-attributes' || typeof value.documentId !== 'string' ||
            !/^[1-9][0-9]{0,23}$/.test(value.documentId) || typeof value.origin !== 'string' ||
            capture && (value.status !== 'captured' || value.origin !== request.origin) ||
            grant && !['granted','existing','not-required','denied'].includes(value.status) ||
            !Number.isSafeInteger(value.expiresAt) || value.expiresAt < 0) return failure();
        return value;
      } catch (_) { return failure(); }
    },
    async clear() { try { await browser.pocketNativePhoto?.releaseAll(); } catch (_) {} }
  });
})();
