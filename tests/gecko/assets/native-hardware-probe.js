/* Integration-only observation of untouched native navigator CPU getters. */
(() => {
  'use strict';
  const PHASES = ['baseline', 'cap2', 'cap1', 'reset'];
  const ROLES = ['page', 'dedicated', 'blob', 'shared', 'service'];
  function sample() {
    const value = navigator.hardwareConcurrency;
    let holder = navigator, descriptor = null;
    for (let depth = 0; holder && depth < 5; depth++, holder = Object.getPrototypeOf(holder)) {
      descriptor = Object.getOwnPropertyDescriptor(holder, 'hardwareConcurrency');
      if (descriptor) break;
    }
    const nativeGetter = !!descriptor && typeof descriptor.get === 'function' &&
      /\[native code\]/.test(Function.prototype.toString.call(descriptor.get));
    return {hardwareConcurrency: value, nativeGetter};
  }
  function answer(message) {
    if (!message || message.kind !== 'native-hardware-sample' || !/^[0-9a-f]{32}$/.test(message.nonce || '') ||
        !PHASES.includes(message.phase) || !ROLES.includes(message.role)) return null;
    return {schema: 1, kind: 'native-hardware-observation', nonce: message.nonce,
      phase: message.phase, role: message.role, status: 'observed', observation: sample()};
  }
  if (typeof window === 'undefined') {
    if (typeof ServiceWorkerGlobalScope !== 'undefined' && self instanceof ServiceWorkerGlobalScope) {
      self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
      self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
      self.addEventListener('message', event => {
        const value = answer(event.data); if (value && event.ports.length === 1) event.ports[0].postMessage(value);
      });
    } else if (typeof SharedWorkerGlobalScope !== 'undefined' && self instanceof SharedWorkerGlobalScope) {
      self.addEventListener('connect', event => {
        const port = event.ports[0]; port.onmessage = message => {const value = answer(message.data); if (value) port.postMessage(value);}; port.start();
      });
    } else self.onmessage = event => {const value = answer(event.data); if (value) self.postMessage(value);};
    return;
  }
  const config = globalThis.__nativeHardwareProbe;
  if (!config || config.schema !== 1 || !/^[0-9a-f]{32}$/.test(config.nonce) ||
      !/^[0-9a-f]{40}$/.test(config.source) || !PHASES.includes(config.phase)) throw new Error('Controlled hardware binding missing');
  const prefix = '/' + config.phase + '/', query = '?nonce=' + encodeURIComponent(config.nonce);
  async function report(role, value) {
    const packet = {schema: 1, nonce: config.nonce, sourceCommit: config.source, role, phase: config.phase,
      status: value.status, observation: value.observation || null, error: value.error || null};
    const response = await fetch(prefix + 'report' + query, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(packet), cache: 'no-store'});
    if (!response.ok) throw new Error('Controlled hardware report rejected');
  }
  const unsupported = () => ({status: 'unsupported', error: 'Unavailable'});
  function bounded(work) {
    return new Promise(resolve => {
      let done = false, dispose = () => {};
      const finish = value => {if (done) return; done = true; clearTimeout(timer); dispose(); resolve(value);};
      const timer = setTimeout(() => finish({status: 'failed', error: 'TimeoutError'}), 8000);
      try {dispose = work(finish) || dispose;} catch (_) {finish({status: 'failed', error: 'WorkerError'});}
    });
  }
  const message = role => ({kind: 'native-hardware-sample', nonce: config.nonce, phase: config.phase, role});
  const valid = (role, value) => value && value.schema === 1 && value.kind === 'native-hardware-observation' &&
    value.nonce === config.nonce && value.phase === config.phase && value.role === role && value.status === 'observed';
  function dedicated(role, url, revoke) {
    if (typeof Worker !== 'function') return Promise.resolve(unsupported());
    return bounded(finish => {
      const worker = new Worker(url);
      worker.onmessage = event => finish(valid(role, event.data) ? event.data : {status: 'failed', error: 'InvalidReply'});
      worker.onerror = () => finish({status: 'failed', error: 'WorkerError'}); worker.postMessage(message(role));
      return () => {worker.terminate(); if (revoke) URL.revokeObjectURL(url);};
    });
  }
  async function blob() {
    if (typeof Worker !== 'function') return unsupported();
    const response = await fetch(prefix + 'worker.js' + query, {cache: 'no-store'});
    if (!response.ok) throw new Error('Controlled worker script unavailable');
    return dedicated('blob', URL.createObjectURL(new Blob([await response.text()], {type: 'application/javascript'})), true);
  }
  function shared() {
    if (typeof SharedWorker !== 'function') return Promise.resolve(unsupported());
    return bounded(finish => {
      const worker = new SharedWorker(prefix + 'worker.js' + query, 'hardware-' + config.nonce + '-' + config.phase);
      worker.port.onmessage = event => finish(valid('shared', event.data) ? event.data : {status: 'failed', error: 'InvalidReply'});
      worker.onerror = () => finish({status: 'failed', error: 'WorkerError'}); worker.port.start(); worker.port.postMessage(message('shared'));
      return () => worker.port.close();
    });
  }
  async function service() {
    if (!isSecureContext || !('serviceWorker' in navigator)) return unsupported();
    let registration;
    try {
      registration = await navigator.serviceWorker.register(prefix + 'worker.js' + query, {scope: prefix});
      return await bounded(finish => {
        let channel, sent = false;
        const deliver = () => {
          const worker = registration.active;
          if (sent || !worker || worker.state !== 'activated') return; sent = true;
          channel = new MessageChannel(); channel.port1.onmessage = event => finish(valid('service', event.data) ?
            event.data : {status: 'failed', error: 'InvalidReply'});
          worker.postMessage(message('service'), [channel.port2]);
        };
        const worker = registration.installing || registration.waiting || registration.active;
        if (worker) worker.addEventListener('statechange', deliver); deliver();
        return () => {if (worker) worker.removeEventListener('statechange', deliver); if (channel) channel.port1.close();};
      });
    } finally {if (registration) await registration.unregister();}
  }
  async function execute(role, operation) {
    try {await report(role, await operation());} catch (_) {await report(role, {status: 'failed', error: 'WorkerError'});}
  }
  (async () => {
    await report('page', {status: 'observed', observation: sample()});
    await Promise.all([execute('dedicated', () => dedicated('dedicated', prefix + 'worker.js' + query)),
      execute('blob', blob), execute('shared', shared), execute('service', service)]);
  })().catch(() => {});
})();
