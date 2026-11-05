(function () {
  'use strict';
  const fixture = __WORKER_POLICY_FIXTURE__;
  const phases = new Set(['gecko-native', 'gecko-system', 'gecko-new-york', 'gecko-kathmandu',
    'gecko-desktop', 'gecko-restored', 'gecko-reload', 'gecko-reopen', 'gecko-private',
    'gecko-popup', 'gecko-rfp-conflict', 'gecko-system-mobile', 'gecko-ny-mobile',
    'gecko-kathmandu-mobile', 'gecko-restore', 'gecko-mobile-restored', 'gecko-coop']);
  const pageUrl = new URL(location.href);
  const phase = pageUrl.searchParams.get('phase');
  if (!phases.has(phase) || pageUrl.searchParams.getAll('phase').length !== 1
      || Array.from(pageUrl.searchParams.keys()).length !== 1) throw Error('Unknown Gecko fixture phase');
  const origins = new Set(fixture.origins);
  if (origins.size !== 2 || !origins.has(location.origin)) throw Error('Gecko fixture origin differs');
  function nativeZone() {
    function sample(month) {
      const value = new Date(Date.UTC(2026, month, 15, 12, 0, 0));
      return {offsetMinutes: value.getTimezoneOffset(), year: value.getFullYear(),
        month: value.getMonth() + 1, day: value.getDate(), hour: value.getHours(), minute: value.getMinutes()};
    }
    return {timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone, january: sample(0), july: sample(6)};
  }
  // This synchronous observation precedes promises, frame messages and Worker creation.
  const early = {schema: 1,
    firstInline: document.currentScript === document.scripts[0] && document.readyState === 'loading',
    secure: isSecureContext, runNonce: fixture.runNonce, sourceCommit: fixture.sourceCommit,
    phase, origin: location.origin, documentId: crypto.randomUUID(),
    nativeUserAgent: navigator.userAgent, nativeTimeZone: nativeZone()};
  const report = {page: early, frames: [], workers: {started: false, complete: false, cases: {}}};
  window.__geckoEnvironmentPolicy = report;
  function publish() {
    let value = JSON.stringify(report);
    if (new TextEncoder().encode(value).length > 100000) value = JSON.stringify({
      page: {schema: early.schema, runNonce: early.runNonce, sourceCommit: early.sourceCommit,
        phase: early.phase, origin: early.origin, documentId: early.documentId}, frames: [],
      workers: {started: report.workers.started, complete: false, cases: {},
        error: 'Synthetic native observation exceeds the 100000-byte DOM snapshot bound'},
      publicationError: 'oversized-native-observation'});
    document.documentElement.setAttribute('data-gecko-environment-policy', value);
  }
  const errorText = error => (String(error && error.name || 'Error') + ': ' + String(error && error.message || error)).slice(0, 500);
  function timed(promise, label) {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error(label + ' exceeded the 8-second fixture deadline')), 8000);
    })]).finally(() => clearTimeout(timer));
  }
  early.markerComplete = false; early.networkAllowed = false;
  publish();
  const documentMarker = (async () => {
    try {
      early.networkAllowed = await timed((async () => {
        const response = await fetch('/worker-probe?' + new URLSearchParams({phase, realm: 'document', documentId: early.documentId}), {cache: 'no-store'});
        return response.ok && (await response.text()) === 'worker-network-synthetic-v1';
      })(), 'native document network marker');
      if (!early.networkAllowed) early.markerError = 'Synthetic document network marker failed';
    } catch (error) { early.markerError = errorText(error); }
    finally { early.markerComplete = true; publish(); }
  })();
  if (window.parent !== window) {
    let topOrigin = fixture.origins[0];
    try { const referrer = new URL(document.referrer).origin; if (origins.has(referrer)) topOrigin = referrer; } catch (_) {}
    documentMarker.then(() => parent.postMessage(early, topOrigin));
    return;
  }

  const framePath = pageUrl.pathname === '/gecko-environment-policy' ? '/gecko-environment-frame' : '/env-frame';
  const seenFrames = new Set();
  let framesResolve;
  const framesReady = new Promise(resolve => { framesResolve = resolve; });
  addEventListener('message', event => {
    const value = event.data;
    if (!origins.has(event.origin) || !value || value.schema !== 1
        || value.runNonce !== fixture.runNonce || value.sourceCommit !== fixture.sourceCommit
        || value.phase !== phase || value.origin !== event.origin
        || value.markerComplete !== true || typeof value.networkAllowed !== 'boolean'
        || typeof value.firstInline !== 'boolean' || typeof value.secure !== 'boolean'
        || typeof value.nativeUserAgent !== 'string' || !value.nativeTimeZone
        || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.documentId)
        || value.documentId === early.documentId || seenFrames.has(event.source)
        || report.frames.some(row => row.origin === event.origin || row.documentId === value.documentId)) return;
    const iframe = Array.from(document.querySelectorAll('iframe')).find(node => node.contentWindow === event.source);
    if (!iframe) return;
    let source;
    try { source = new URL(iframe.src, location.href); } catch (_) { return; }
    if (source.origin !== event.origin || source.pathname !== framePath
        || source.searchParams.get('phase') !== phase || source.searchParams.getAll('phase').length !== 1
        || Array.from(source.searchParams.keys()).length !== 1 || source.hash) return;
    seenFrames.add(event.source); report.frames.push(value); publish();
    if (report.frames.length === 2) framesResolve();
  });

  const parameters = realm => new URLSearchParams({phase, realm, documentId: early.documentId}).toString();
  function resultFor(name, available) {
    const result = {available, created: false, executed: false, networkAllowed: false,
      nativeUserAgent: null, nativeTimeZone: null};
    report.workers.cases[name] = result; publish(); return result;
  }
  function observed(result, value, realm) {
    if (value && typeof value === 'object') {
      if ('nativeUserAgent' in value) result.nativeUserAgent = value.nativeUserAgent;
      if ('nativeTimeZone' in value) result.nativeTimeZone = value.nativeTimeZone;
    }
    if (!value || value.executed !== true || typeof value.networkAllowed !== 'boolean'
        || value.sourceRole !== realm || typeof value.nativeUserAgent !== 'string'
        || !value.nativeTimeZone || typeof value.nativeTimeZone !== 'object') throw Error('Native Worker response incomplete: ' + realm);
    result.executed = value.executed; result.networkAllowed = value.networkAllowed; result.sourceRole = value.sourceRole; publish();
  }
  function blobSource() {
    return nativeZone.toString() + '\nself.onmessage=async()=>{let ok=false;try{const response=await fetch('
      + JSON.stringify(location.origin + '/worker-probe?' + parameters('dedicated-blob'))
      + ',{cache:"no-store"});ok=response.ok&&(await response.text())==="worker-network-synthetic-v1";}catch(_){}'
      + 'self.postMessage({executed:true,networkAllowed:ok,nativeUserAgent:navigator.userAgent,'
      + 'nativeTimeZone:nativeZone(),sourceRole:"dedicated-blob"});};';
  }
  async function dedicated(realm, path, module, blob) {
    const name = realm === 'dedicated-classic' ? 'classic' : module ? 'module' : 'blob';
    const result = resultFor(name, typeof Worker === 'function');
    if (!result.available) { result.reason = 'Worker API unavailable'; publish(); return result; }
    let worker, url;
    try {
      url = blob ? URL.createObjectURL(new Blob([blobSource()], {type: 'text/javascript'})) : path + '?' + parameters(realm);
      worker = new Worker(url, module ? {type: 'module'} : undefined); result.created = true; publish();
      const value = await timed(new Promise((resolve, reject) => {
        worker.onmessage = event => resolve(event.data);
        worker.onerror = () => reject(Error('Native Dedicated Worker failed: ' + realm));
        worker.onmessageerror = () => reject(Error('Native Dedicated Worker message failed: ' + realm));
        worker.postMessage('native-observation');
      }), realm);
      observed(result, value, realm);
    } catch (error) { result.error = errorText(error); publish(); }
    finally { if (worker) worker.terminate(); if (blob && url) URL.revokeObjectURL(url); }
    return result;
  }
  async function shared() {
    const result = resultFor('shared', typeof SharedWorker === 'function');
    if (!result.available) { result.reason = 'SharedWorker API unavailable'; publish(); return result; }
    let worker;
    try {
      worker = new SharedWorker('/shared.js?' + parameters('shared-worker'), {name: early.documentId + '-native-shared'});
      result.created = true; publish();
      const value = await timed(new Promise((resolve, reject) => {
        worker.onerror = () => reject(Error('Native Shared Worker failed'));
        worker.port.onmessage = event => resolve(event.data);
        worker.port.onmessageerror = () => reject(Error('Native Shared Worker message failed'));
        worker.port.start(); worker.port.postMessage('native-observation');
      }), 'shared-worker');
      observed(result, value, 'shared-worker');
    } catch (error) { result.error = errorText(error); publish(); }
    finally { if (worker && worker.port) worker.port.close(); }
    return result;
  }
  async function service() {
    const result = resultFor('service', 'serviceWorker' in navigator);
    if (!result.available) { result.reason = 'ServiceWorker API unavailable'; publish(); return result; }
    let live = true, removeStateListener, channel;
    try {
      const value = await timed((async () => {
        const registration = await navigator.serviceWorker.register('/service.js?' + parameters('service-worker'),
          {scope: '/sw-scope/', updateViaCache: 'none'});
        if (!live) throw Error('Service Worker observation retired');
        result.created = !!registration; publish();
        if (!registration) throw Error('Native Service Worker registration missing');
        let active = registration.installing || registration.waiting || registration.active;
        if (!active) throw Error('Native Service Worker instance missing');
        if (active.state !== 'activated') await new Promise((resolve, reject) => {
          const changed = () => {
            if (active.state === 'activated') resolve();
            else if (active.state === 'redundant') reject(Error('Native Service Worker became redundant'));
          };
          active.addEventListener('statechange', changed);
          removeStateListener = () => active.removeEventListener('statechange', changed); changed();
        });
        if (!live) throw Error('Service Worker observation retired');
        channel = new MessageChannel();
        return new Promise((resolve, reject) => {
          channel.port1.onmessage = event => resolve(event.data);
          channel.port1.onmessageerror = () => reject(Error('Native Service Worker message failed'));
          channel.port1.start();
          active.postMessage({action: 'network', phase, documentId: early.documentId}, [channel.port2]);
        });
      })(), 'service-worker');
      observed(result, value, 'service-worker');
    } catch (error) { result.error = errorText(error); publish(); }
    finally { live = false; if (removeStateListener) removeStateListener(); if (channel) channel.port1.close(); }
    return result;
  }

  let run;
  window.__runGeckoEnvironmentWorkers = function () {
    if (run) return run;
    report.workers.started = true; publish();
    run = (async () => {
      await Promise.all([
        ['classic', dedicated('dedicated-classic', '/dedicated.js', false, false)],
        ['module', dedicated('dedicated-module', '/module.js', true, false)],
        ['blob', dedicated('dedicated-blob', '', false, true)],
        ['shared', shared()], ['service', service()],
      ].map(async ([name, promise]) => { report.workers.cases[name] = await promise; publish(); }));
      await documentMarker;
      if (!early.networkAllowed || early.markerError) throw Error('Native document network marker incomplete; see page');
      try { await timed(framesReady, 'two native frame observations'); }
      catch (error) { report.framesError = errorText(error); publish(); throw error; }
      const cases = report.workers.cases;
      if (Object.values(cases).some(row => row.error)
          || ['classic', 'module', 'blob'].some(name => !cases[name].available || !cases[name].created || !cases[name].executed))
        throw Error('Native Worker observations incomplete; see cases');
      report.workers.complete = true; publish();
      return report.workers;
    })().catch(error => { report.workers.error = errorText(error); publish(); return report.workers; });
    return run;
  };
  document.addEventListener('pocketchat-gecko-env-run-workers', event => {
    if (event.detail === fixture.runNonce) window.__runGeckoEnvironmentWorkers();
  });
})();
