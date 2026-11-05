// Appended to the existing controlled Gecko first-inline/Worker observation.
// Date, Intl, native identity and Worker constructors are never replaced.
(function () {
  'use strict';
  if (window.parent !== window) return;
  const source = 'https://ipwho.is/?fields=success,ip,timezone.id';
  const report = window.__geckoEnvironmentPolicy;
  if (!report || !report.page || !report.page.firstInline) throw Error('Controlled first-inline observer absent');
  let running = false;
  const options = {credentials: 'omit', redirect: 'error', cache: 'no-store'};
  function publish(value) {
    const raw = JSON.stringify(value);
    if (new TextEncoder().encode(raw).length > 8192) throw Error('Bounded isolation observer overflow');
    document.documentElement.setAttribute('data-gecko-ip-timezone-isolation', raw);
  }
  function bounded(promise) {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error('controlled-realm-timeout')), 5500);
    })]).finally(() => clearTimeout(timer));
  }
  async function page() {
    const row = {available: true, created: true, executed: true, networkAllowed: false};
    try { const response = await bounded(fetch(source, options)); row.networkAllowed = response.ok; }
    catch (_) { row.networkAllowed = false; }
    return row;
  }
  async function worker(shared) {
    const available = typeof (shared ? SharedWorker : Worker) === 'function';
    const row = {available, created: false, executed: false, networkAllowed: false};
    if (!available) return row;
    const code = (shared ? "onconnect=e=>{const port=e.ports[0];port.onmessage=async()=>{" : "onmessage=async()=>{")
      + "let allowed=false;try{const r=await fetch(" + JSON.stringify(source)
      + ",{credentials:'omit',redirect:'error',cache:'no-store'});allowed=r.ok;}catch(_){}"
      + (shared ? "port.postMessage({executed:true,networkAllowed:allowed});};port.start();};"
                : "postMessage({executed:true,networkAllowed:allowed});};");
    const url = URL.createObjectURL(new Blob([code], {type: 'text/javascript'}));
    let native;
    try {
      native = shared ? new SharedWorker(url, 'ip-timezone-bound-' + report.page.documentId) : new Worker(url);
      row.created = true;
      const port = shared ? native.port : native;
      const value = await bounded(new Promise((resolve, reject) => {
        port.onmessage = event => resolve(event.data);
        native.onerror = () => reject(Error('controlled-worker-error'));
        if (shared) port.start();
        port.postMessage({});
      }));
      if (value && value.executed === true && typeof value.networkAllowed === 'boolean') {
        row.executed = true; row.networkAllowed = value.networkAllowed;
      }
    } catch (_) { /* Creation failure is recorded separately from an executed fetch. */ }
    finally { if (native) { if (shared) native.port.close(); else native.terminate(); } URL.revokeObjectURL(url); }
    return row;
  }
  async function service() {
    const row = {available: 'serviceWorker' in navigator, created: false, executed: false, networkAllowed: false};
    if (!row.available) return row;
    let channel;
    try {
      const registration = await bounded(navigator.serviceWorker.getRegistration('/sw-scope/'));
      const active = registration && registration.active;
      row.created = !!active;
      if (!active) return row;
      channel = new MessageChannel();
      const value = await bounded(new Promise(resolve => {
        channel.port1.onmessage = event => resolve(event.data);
        channel.port1.start();
        active.postMessage({action: 'fixed-ip-bootstrap', runNonce: report.page.runNonce}, [channel.port2]);
      }));
      if (value && value.executed === true && typeof value.networkAllowed === 'boolean') {
        row.executed = true; row.networkAllowed = value.networkAllowed;
      }
    } catch (_) { /* An unavailable receipt never becomes an executed denial. */ }
    finally { if (channel) channel.port1.close(); }
    return row;
  }
  document.addEventListener('pocketchat-ip-bootstrap-denial', async event => {
    if (running || event.detail !== report.page.runNonce) return;
    running = true;
    const value = {schema: 1, runNonce: report.page.runNonce, sourceCommit: report.page.sourceCommit,
      documentId: report.page.documentId, source, started: true, complete: false, roles: {}};
    publish(value);
    try {
      const rows = await Promise.all([page(), worker(false), worker(true), service()]);
      ['page', 'dedicated', 'shared', 'service'].forEach((name, i) => { value.roles[name] = rows[i]; });
      value.complete = true;
    } finally { publish(value); }
  });
}());
