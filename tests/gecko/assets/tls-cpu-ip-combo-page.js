/* Integration-only FIRST inline getters. No Date, Intl or navigator mutation. */
(function () {
  'use strict';
  if (window.parent !== window) return;
  const fixture = __WORKER_POLICY_FIXTURE__;
  const hardwareConcurrency = navigator.hardwareConcurrency;
  function sample(month) {
    const value = new Date(Date.UTC(2026, month, 15, 12, 0, 0));
    return {offsetMinutes: value.getTimezoneOffset(), year: value.getFullYear(),
      month: value.getMonth() + 1, day: value.getDate(), hour: value.getHours(), minute: value.getMinutes()};
  }
  const nativeTimeZone = {timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    january: sample(0), july: sample(6)};
  let holder = navigator, descriptor = null;
  for (let depth = 0; holder && depth < 5; depth++, holder = Object.getPrototypeOf(holder)) {
    descriptor = Object.getOwnPropertyDescriptor(holder, 'hardwareConcurrency');
    if (descriptor) break;
  }
  const page = {schema: 1, firstInline: document.currentScript === document.scripts[0]
      && document.readyState === 'loading', secure: isSecureContext,
    sourceCommit: fixture.sourceCommit, runNonce: fixture.runNonce,
    documentId: crypto.randomUUID(), origin: location.origin,
    phase: new URL(location.href).searchParams.get('phase'), hardwareConcurrency,
    nativeGetter: !!descriptor && typeof descriptor.get === 'function'
      && /\[native code\]/.test(Function.prototype.toString.call(descriptor.get)),
    nativeTimeZone, markerComplete: false, networkAllowed: false};
  function publish() {
    const raw = JSON.stringify(page);
    if (new TextEncoder().encode(raw).length > 8192) throw Error('Combined observer bound');
    document.documentElement.setAttribute('data-gecko-cpu-ip-combo', raw);
  }
  document.addEventListener("DOMContentLoaded", () => { document.title = "TLS CPU IP:" + fixture.runNonce; }, {once: true});
  publish();
  let timer;
  const url = '/worker-probe?' + new URLSearchParams({phase: page.phase,
    realm: 'document', documentId: page.documentId});
  Promise.race([fetch(url, {cache: 'no-store', credentials: 'omit', redirect: 'error'})
    .then(async response => response.ok && (await response.text()) === 'worker-network-synthetic-v1'),
    new Promise(resolve => { timer = setTimeout(() => resolve(false), 8000); })])
    .then(allowed => { page.networkAllowed = allowed === true; })
    .catch(() => { page.networkAllowed = false; })
    .finally(() => { clearTimeout(timer); page.markerComplete = true; publish(); });
}());
