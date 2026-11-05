(function () {
  'use strict';
  const fixture = __WORKER_POLICY_FIXTURE__;
  const frame = window.parent !== window;
  const requested = new URL(location.href).searchParams.get('phase');
  const observe = globalThis.__pocketchatChromiumFingerprintObserve;
  const observation = typeof observe === 'function' ? observe() : null;
  const mode = observation && observation.workerCreation && observation.workerCreation.mode;
  // A production policy edit reloads the same URL. Label the fresh document by
  // its actual injected policy, retaining the requested URL separately.
  const phase = requested === 'gecko-native' ? 'gecko-native' : mode === 'restrict' ? requested === 'restrict-route' ? 'restrict-route' : 'restrict' : requested === 'allow' ? 'allow' : 'restore';
  const report = {schema: 1, runNonce: fixture.runNonce, sourceCommit: fixture.sourceCommit,
    firstInline: true, secure: isSecureContext, documentId: crypto.randomUUID(), origin: location.origin,
    requestedPhase: requested, phase, mode, frame, nativeUserAgent: navigator.userAgent,
    documentGuard: globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')] === true,
    workerCoverageVerified: false, existingExecutionControlled: false, cases: {}, complete: false};
  window.__workerPolicyPage = report;
  window.__workerPolicyFrames = [];
  if (!frame) addEventListener('message', event => {
    if (!fixture.origins.includes(event.origin) || !event.data || event.data.scope !== 'worker-policy-frame'
        || event.data.value.runNonce !== fixture.runNonce || event.data.value.phase !== phase) return;
    if (!window.__workerPolicyFrames.some(value => value.origin === event.origin)) window.__workerPolicyFrames.push(event.data.value);
  });
  const timed = promise => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error('Synthetic Worker did not complete')), 6000))]);
  const parameters = realm => new URLSearchParams({phase, realm, documentId: report.documentId}).toString();
  const workerSource = realm => `onmessage=async()=>{let ok=false;try{const response=await fetch(${JSON.stringify(location.origin + '/worker-probe?' + parameters(realm))},{cache:'no-store'});ok=response.ok&&(await response.text())==='worker-network-synthetic-v1';}catch(_){}postMessage({executed:true,networkAllowed:ok,nativeUserAgent:navigator.userAgent,documentGuard:globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')]===true,auditAvailable:typeof globalThis.__pocketchatChromiumFingerprintObserve==='function'});}`;
  async function dedicated(realm, path, module, blob) {
    const result = {available: typeof Worker === 'function', created: false, executed: false, denied: false, networkAllowed: false};
    if (!result.available) return result;
    let worker, url;
    try {
      url = blob ? URL.createObjectURL(new Blob([workerSource(realm)], {type: 'text/javascript'})) : path + '?' + parameters(realm);
      worker = new Worker(url, module ? {type: 'module'} : undefined);result.created = true;
      const value = await timed(new Promise((resolve, reject) => {worker.onmessage = event => resolve(event.data);worker.onerror = () => reject(new Error('Synthetic Dedicated Worker failed'));worker.postMessage('probe');}));
      Object.assign(result, value);
    } catch (error) { if (error.name !== 'SecurityError') throw error;result.denied = true; }
    finally { if (worker) worker.terminate();if (blob && url) URL.revokeObjectURL(url); }
    return result;
  }
  async function shared(blob) {
    const result = {available: typeof SharedWorker === 'function', created: false, executed: false, denied: false, networkAllowed: false};
    if (!result.available) return result;
    const realm = blob ? 'shared-blob' : 'shared-worker';let worker, url;
    try {
      const code = `onconnect=event=>{const port=event.ports[0];port.onmessage=async()=>{let ok=false;try{const response=await fetch(${JSON.stringify(location.origin + '/worker-probe?' + parameters(realm))},{cache:'no-store'});ok=response.ok&&(await response.text())==='worker-network-synthetic-v1';}catch(_){}port.postMessage({executed:true,networkAllowed:ok,nativeUserAgent:navigator.userAgent,documentGuard:globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')]===true,auditAvailable:typeof globalThis.__pocketchatChromiumFingerprintObserve==='function'});};port.start();};`;
      url = blob ? URL.createObjectURL(new Blob([code], {type: 'text/javascript'})) : '/shared.js?' + parameters(realm);
      worker = new SharedWorker(url, {name: report.documentId + realm});result.created = true;
      const value = await timed(new Promise((resolve, reject) => {worker.onerror = () => reject(new Error('Synthetic Shared Worker failed'));worker.port.onmessage = event => resolve(event.data);worker.port.start();worker.port.postMessage('probe');}));Object.assign(result, value);
    } catch (error) { if (error.name !== 'SecurityError') throw error;result.denied = true; }
    finally {if (worker) worker.port.close();if (blob && url) URL.revokeObjectURL(url);}
    return result;
  }
  async function message(worker, action) {
    const channel = new MessageChannel();
    try {return await timed(new Promise(resolve => {channel.port1.onmessage = event => resolve(event.data);channel.port1.start();worker.postMessage({action, phase, documentId: report.documentId}, [channel.port2]);}));}
    finally {channel.port1.close();}
  }
  async function service() {
    const result = {available: 'serviceWorker' in navigator, registrationDenied: false, registered: false, existingExecution: false, cacheRead: false, networkAllowed: false};
    if (!result.available) return result;
    try {const registration = await timed(navigator.serviceWorker.register('/service.js?' + parameters('service-worker'), {scope: '/sw-scope/'}));result.registered = !!registration;}
    catch (error) {if (error.name !== 'SecurityError') throw error;result.registrationDenied = true;}
    let registration = await navigator.serviceWorker.getRegistration('/sw-scope/');
    if (!registration) throw new Error('Existing synthetic Service Worker missing');
    const pending = registration.installing || registration.waiting;
    if (pending) await timed(new Promise((resolve, reject) => {function changed(){if(pending.state === 'activated')resolve();else if(pending.state === 'redundant')reject(new Error('Synthetic Service Worker became redundant'));}pending.addEventListener('statechange', changed);changed();}));
    registration = await navigator.serviceWorker.getRegistration('/sw-scope/');
    if (!registration || !registration.active) throw new Error('Synthetic Service Worker not active');
    const cached = await message(registration.active, 'cached');
    result.existingExecution = cached.executed === true;result.cacheRead = cached.cacheRead === true;
    const network = await message(registration.active, 'network');
    if (network.executed !== true || typeof network.networkAllowed !== 'boolean') throw new Error('Actual Service Worker outcome missing');
    result.networkAllowed = network.networkAllowed;result.nativeUserAgent = network.nativeUserAgent;
    result.workerFingerprintProtected = false;return result;
  }
  (async () => {
    const marker = await fetch('/worker-probe?' + parameters('document'), {cache: 'no-store'});
    if (!marker.ok) throw new Error('Synthetic document network marker failed');
    report.cases.dedicated = await dedicated(frame ? 'frame-dedicated' : 'dedicated-classic', '/dedicated.js', false, false);
    if (!frame) {
      report.cases.module = await dedicated('dedicated-module', '/module.js', true, false);
      report.cases.blob = await dedicated('dedicated-blob', '', false, true);
      report.cases.shared = await shared(false);report.cases.sharedBlob = await shared(true);
      report.serviceWorker = await service();
    }
    await Promise.resolve();report.observation = observe ? observe().workerCreation : null;report.complete = true;
    if (frame) parent.postMessage({scope: 'worker-policy-frame', value: report}, fixture.origins[0]);
  })().catch(error => {report.error = String(error.name) + ': ' + String(error.message);report.complete = true;if (frame) parent.postMessage({scope: 'worker-policy-frame', value: report}, fixture.origins[0]);});
})();
