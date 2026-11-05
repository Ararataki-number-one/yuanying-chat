/* Synthetic first-inline observer. No account, cookie, storage or document text reads. */
(function () {
  'use strict';
  function hash(a) { let h = 2166136261; for (const b of a) h = Math.imul(h ^ b, 16777619); return (h >>> 0).toString(16).padStart(8, '0'); }
  const canvas = document.createElement('canvas'); canvas.width = 32; canvas.height = 32;
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#123456'; ctx.fillRect(0, 0, 32, 32);
  const second = document.createElement('canvas'); second.width = 33; second.height = 31;
  const secondContext = second.getContext('2d'); secondContext.fillStyle = '#123456'; secondContext.fillRect(0, 0, 33, 31);
  // Two dimensions avoid treating an occasional one-pixel position collision as an origin leak.
  const expected = new Uint8Array((32 * 32 + 33 * 31) * 4); for (let i = 0; i < expected.length; i += 4) expected.set([18, 52, 86, 255], i);
  const sample = () => { const result = new Uint8Array(expected.length); result.set(ctx.getImageData(0, 0, 32, 32).data); result.set(secondContext.getImageData(0, 0, 33, 31).data, 32 * 32 * 4); return result; };
  const pixels = sample();
  const e = window.__fixtureEarly = {schema: 1, documentId: crypto.randomUUID ? crypto.randomUUID() : String(Math.random()), firstInline: true, secure: isSecureContext, origin: location.origin,
    ua: navigator.userAgent, platform: navigator.platform, canvas: hash(pixels), baseline: hash(expected),
    repeat: hash(sample()),
    documentGuard: globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')] === true,
    auditAvailable: typeof __pocketchatChromiumFingerprintObserve === 'function',
    low: navigator.userAgentData ? navigator.userAgentData.toJSON() : null,
    gpt: {reply: typeof window.__pocketWebReplyObserver, performance: typeof window.__pocketWebPerformance},
    workerCoverageVerified: false, serviceWorkerCoverageVerified: false};
  window.__fixtureFrames = [];
  addEventListener('message', event => {
    if (event.source !== window && event.data && event.data.kind === 'fixture-frame' &&
        ['https://fp-a.pocketchat.test', 'https://fp-b.pocketchat.test'].includes(event.origin))
      window.__fixtureFrames.push(event.data.observation);
  });
  const finish = async () => {
    try {
      e.high = navigator.userAgentData ? await navigator.userAgentData.getHighEntropyValues(['architecture', 'bitness', 'model', 'platformVersion', 'fullVersionList', 'wow64']) : null;
      if (window === top) {
        const response = await fetch('/hints?case=' + encodeURIComponent(new URL(location.href).searchParams.get('case') || 'primary'), {cache: 'no-store'});
        e.hintsFetched = response.ok;
        e.worker = {available: typeof Worker === 'function', actualExecution: false, protected: false};
        if (e.worker.available) await new Promise((resolve, reject) => {
          const worker = new Worker('/worker.js'); const timer = setTimeout(() => {worker.terminate(); reject(Error('worker timeout'));}, 10000);
          worker.onmessage = message => {clearTimeout(timer); e.worker.actualExecution = true; e.worker.documentGuard = message.data.documentGuard; e.worker.auditAvailable = message.data.auditAvailable; worker.terminate(); resolve();};
          worker.onerror = () => {clearTimeout(timer); worker.terminate(); reject(Error('worker error'));};
        });
        e.serviceWorker = {available: 'serviceWorker' in navigator, actualExecution: false, protected: false, scope: 'unsupported'};
      }
      e.complete = true;
      if (window !== top) parent.postMessage({kind: 'fixture-frame', observation: e}, '*');
    } catch (_) { e.error = 'controlled-observation-failed'; e.complete = true; }
  };
  finish();
})();
