/* Integration-only native Date/Intl observations. No timezone API is replaced. */
(() => {
  'use strict';
  const JAN = Date.UTC(2026, 0, 15, 12, 0, 0);
  const JULY = Date.UTC(2026, 6, 15, 12, 0, 0);
  function sample() {
    const jan = new Date(JAN), july = new Date(JULY);
    return {timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      janOffsetMinutes: jan.getTimezoneOffset(), julyOffsetMinutes: july.getTimezoneOffset(),
      janHour: jan.getHours(), janMinute: jan.getMinutes(),
      julyHour: july.getHours(), julyMinute: july.getMinutes(),
      janEpochMillis: jan.getTime(), julyEpochMillis: july.getTime()};
  }
  function answer(message) {
    if (!message || message.kind !== 'native-timezone-sample' ||
        typeof message.nonce !== 'string' || !/^[0-9a-f]{32}$/.test(message.nonce)) return null;
    return {schema: 1, kind: 'native-timezone-observation', nonce: message.nonce,
      role: message.role, status: 'observed', observation: sample()};
  }
  if (typeof window === 'undefined') {
    if (typeof ServiceWorkerGlobalScope !== 'undefined' && self instanceof ServiceWorkerGlobalScope) {
      self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
      self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
      self.addEventListener('message', event => {
        const value = answer(event.data);
        if (value && event.ports.length === 1) event.ports[0].postMessage(value);
      });
    } else if (typeof SharedWorkerGlobalScope !== 'undefined' && self instanceof SharedWorkerGlobalScope) {
      self.addEventListener('connect', event => {
        const port = event.ports[0];
        port.onmessage = message => {const value = answer(message.data); if (value) port.postMessage(value);};
        port.start();
      });
    } else {
      self.onmessage = event => {const value = answer(event.data); if (value) self.postMessage(value);};
    }
    return;
  }
  const config = globalThis.__nativeTimezoneProbe;
  if (!config || config.schema !== 1 || !/^[0-9a-f]{32}$/.test(config.nonce) ||
      !/^[0-9a-f]{40}$/.test(config.source)) throw new Error('Missing controlled probe binding');
  const query = '?nonce=' + encodeURIComponent(config.nonce);
  async function report(role, value) {
    const packet = {schema: 1, nonce: config.nonce, sourceCommit: config.source,
      role, status: value.status, observation: value.observation || null,
      error: value.error || null};
    const response = await fetch('/report' + query, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(packet), cache: 'no-store'});
    if (!response.ok) throw new Error('Controlled report rejected');
  }
  function unavailable() {return {status: 'unsupported', error: 'Unavailable'};}
  function bounded(work) {
    return new Promise(resolve => {
      let done = false, dispose = () => {};
      const finish = value => {if (!done) {done = true; clearTimeout(timer); dispose(); resolve(value);}};
      const timer = setTimeout(() => finish({status: 'failed', error: 'TimeoutError'}), 8000);
      try {dispose = work(finish) || dispose;}
      catch (error) {finish({status: 'failed', error: String(error && error.name || 'Error')});}
    });
  }
  function validReply(role, data) {
    return data && data.schema === 1 && data.kind === 'native-timezone-observation' &&
      data.nonce === config.nonce && data.role === role && data.status === 'observed';
  }
  function dedicated(role, url, revoke) {
    if (typeof Worker !== 'function') return Promise.resolve(unavailable());
    return bounded(finish => {
      const worker = new Worker(url);
      worker.onmessage = event => finish(validReply(role, event.data) ? event.data :
        {status: 'failed', error: 'InvalidReply'});
      worker.onerror = () => finish({status: 'failed', error: 'WorkerError'});
      worker.postMessage({kind: 'native-timezone-sample', nonce: config.nonce, role});
      return () => {worker.terminate(); if (revoke) URL.revokeObjectURL(url);};
    });
  }
  async function blob() {
    if (typeof Worker !== 'function') return unavailable();
    const response = await fetch('/worker.js' + query, {cache: 'no-store'});
    if (!response.ok) throw new Error('Controlled worker script missing');
    return dedicated('blob', URL.createObjectURL(new Blob([await response.text()],
      {type: 'application/javascript'})), true);
  }
  function shared() {
    if (typeof SharedWorker !== 'function') return Promise.resolve(unavailable());
    return bounded(finish => {
      const worker = new SharedWorker('/worker.js' + query, 'timezone-' + config.nonce);
      worker.port.onmessage = event => finish(validReply('shared', event.data) ? event.data :
        {status: 'failed', error: 'InvalidReply'});
      worker.onerror = () => finish({status: 'failed', error: 'WorkerError'});
      worker.port.start();
      worker.port.postMessage({kind: 'native-timezone-sample', nonce: config.nonce, role: 'shared'});
      return () => worker.port.close();
    });
  }
  async function service() {
    if (!isSecureContext || !('serviceWorker' in navigator)) return unavailable();
    let registration;
    try {
      registration = await navigator.serviceWorker.register('/worker.js' + query, {scope: '/'});
      return await bounded(finish => {
        let channel;
        const deliver = () => {
          const worker = registration.active;
          if (!worker || worker.state !== 'activated') return;
          channel = new MessageChannel();
          channel.port1.onmessage = event => finish(validReply('service', event.data) ? event.data :
            {status: 'failed', error: 'InvalidReply'});
          worker.postMessage({kind: 'native-timezone-sample', nonce: config.nonce, role: 'service'}, [channel.port2]);
        };
        const worker = registration.installing || registration.waiting || registration.active;
        if (worker) worker.addEventListener('statechange', deliver);
        deliver();
        return () => {if (worker) worker.removeEventListener('statechange', deliver);
          if (channel) channel.port1.close();};
      });
    } finally {if (registration) await registration.unregister();}
  }
  async function execute(role, operation) {
    try {await report(role, await operation());}
    catch (error) {await report(role, {status: 'failed', error: String(error && error.name || 'Error')});}
  }
  (async () => {
    await report('page', {status: 'observed', observation: sample()});
    await Promise.all([
      execute('dedicated', () => dedicated('dedicated', '/worker.js' + query)),
      execute('blob', blob), execute('shared', shared), execute('service', service)]);
  })().catch(() => {});
})();
