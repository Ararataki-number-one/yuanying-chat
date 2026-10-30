'use strict';

// User-operated HTTPS detector. No accounts, cookies, chat text or identity settings
// are accepted. The Android app separately collects this server's request records.
const https = require('node:https');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

const PROTOCOL = 'pocketchat-request-identity-v1';
const DEFAULT_BASE = '/pocketchat-identity/v1/';
const NONCE = /^[a-f0-9]{32}$/;
const SOURCES = ['document', 'worker-script', 'worker-fetch'];
const WORKER_RESPONSE_BYTES = 8192;
const headerText = value => typeof value === 'string' ? value : '';

function canonicalEndpoint(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== DEFAULT_BASE) return '';
    return url.href;
  } catch (_) {return '';}
}
function canonicalOrigin(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || !['', '/'].includes(url.pathname)) return '';
    return url.origin;
  } catch (_) {return '';}
}

function javascriptObservation() {
  const text = value => typeof value === 'string' ? value.slice(0, 2048) : '';
  return {ua: text(navigator.userAgent), language: text(navigator.language),
    languages: Array.from(navigator.languages || []).slice(0, 8).map(text)};
}

function documentScript() {
  const current = document.currentScript;
  const token = current.dataset.nonce;
  const protocol = current.dataset.protocol;
  const observe = javascriptObservation;
  const frameEndpoint = current.dataset.frameEndpoint || '';
  let worker, frame, ended = false, result = null, workerResult = null, frameResult = null;
  let frameDone = !frameEndpoint, frameTimer;
  const emit = () => {if (result) window.postMessage(result, location.origin);};
  // Native collection can start after the Worker has completed. Keep the exact
  // result for this document and only re-emit it for its own bounded nonce.
  addEventListener('message', event => {
    if (event.source === window && event.origin === location.origin && event.data?.pocketRequestIdentityCancel === token) {
      ended = true;result = null;clearTimeout(timer);clearTimeout(frameTimer);worker?.terminate();frame?.remove();worker = frame = null;return;
    }
    if (event.source === window && event.origin === location.origin &&
        event.data?.pocketRequestIdentityCollect === token) emit();
  });
  const finish = (status, workerValue, error) => {
    if (ended) return;
    ended = true; clearTimeout(timer); clearTimeout(frameTimer); worker?.terminate();frame?.remove();
    result = {pocketRequestIdentity: token, schema: 1, nonce: token,
      protocol, status, source: 'controlled-top-level-document', document: observe(),
      worker: workerValue || {}, ...(error ? {error} : {}), ...(frameEndpoint ? {crossOriginFrame: frameResult || {status: 'uncovered', nonce: token, source: 'controlled-cross-origin-iframe', reason: 'frame-not-completed'}} : {})};
    emit();
  };
  const maybeFinish = () => {if (workerResult && frameDone) finish(workerResult.status, workerResult.js, workerResult.error);};
  const timer = setTimeout(() => finish('failed', {}, 'worker-timeout'), 7000);
  addEventListener('pagehide', () => {ended = true; clearTimeout(timer); clearTimeout(frameTimer);worker?.terminate();frame?.remove();}, {once: true});
  if (frameEndpoint) {
    let frameOrigin = '';
    const finishFrame = value => {if (frameDone || ended) return;frameDone = true;frameResult = value;clearTimeout(frameTimer);frame?.remove();maybeFinish();};
    addEventListener('message', event => {
      const value = event.data;
      if (!frame || event.source !== frame.contentWindow || event.origin !== frameOrigin || !value || value.pocketRequestIdentityFrame !== token || value.nonce !== token || value.schema !== 1 || value.protocol !== protocol || value.source !== 'controlled-cross-origin-iframe' || value.origin !== frameOrigin) return;
      finishFrame({status: 'complete', nonce: token, source: 'controlled-cross-origin-iframe', origin: frameOrigin, apiChecks: value.apiChecks});
    });
    try {
      const target = new URL('frame', frameEndpoint);frameOrigin = target.origin;target.search = '?nonce=' + token;
      frame = document.createElement('iframe');frame.hidden = true;frame.sandbox = 'allow-scripts allow-same-origin';frame.referrerPolicy = 'no-referrer';frame.src = target.href;
      frameTimer = setTimeout(() => finishFrame({status: 'uncovered', nonce: token, source: 'controlled-cross-origin-iframe', origin: frameOrigin, reason: 'frame-timeout-or-csp'}), 3000);
      (document.body || document.documentElement).appendChild(frame);
    } catch (_) {finishFrame({status: 'uncovered', nonce: token, source: 'controlled-cross-origin-iframe', reason: 'frame-unavailable'});}
  }
  try {
    const target = new URL('worker.js', location.href); target.search = '?nonce=' + token;
    worker = new Worker(target, {credentials: 'omit', name: 'pocketchat-identity'});
    worker.onmessage = event => {
      const value = event.data;
      if (!value || value.schema !== 1 || value.nonce !== token || value.protocol !== protocol) return;
      workerResult = {status: value.status === 'complete' ? 'complete' : 'failed', js: value.js,
        error: value.status === 'complete' ? '' : /^worker-response-[a-z0-9-]{1,64}$/.test(value.error || '') ? value.error : 'worker-request-failed'};
      maybeFinish();
    };
    worker.onerror = () => finish('failed', {}, 'worker-unavailable');
  } catch (_) {finish('failed', {}, 'worker-unavailable');}
}

function workerScript(nonce, protocol) {
  const js = javascriptObservation();
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {timedOut = true;controller.abort();}, 5000);
  const limit = 8192;
  const fail = error => {throw new Error(error);};
  const read = async response => {
    if (!response.ok) fail('worker-response-http-failed');
    if (!response.body || typeof response.body.getReader !== 'function') fail('worker-response-stream-unavailable');
    const declared = response.headers?.get?.('content-length');
    if (declared && !/^\d+$/.test(declared)) {controller.abort();fail('worker-response-invalid-length');}
    if (declared && Number(declared) > limit) {controller.abort();fail('worker-response-too-large');}
    const reader = response.body.getReader(), chunks = [];let bytes = 0;
    try {
      for (;;) {
        const value = await reader.read();if (value.done) break;
        if (!(value.value instanceof Uint8Array)) fail('worker-response-invalid-stream');
        bytes += value.value.byteLength;
        if (bytes > limit) {controller.abort();fail('worker-response-too-large');}
        chunks.push(value.value);
      }
      const joined = new Uint8Array(bytes);let offset = 0;for (const chunk of chunks) {joined.set(chunk, offset);offset += chunk.byteLength;}
      let text;try {text = new TextDecoder('utf-8', {fatal: true}).decode(joined);} catch (_) {fail('worker-response-invalid-utf8');}
      try {return JSON.parse(text);} catch (_) {fail('worker-response-invalid-json');}
    } finally {try {await reader.cancel();} catch (_) {}try {reader.releaseLock();} catch (_) {}}
  };
  const target = new URL('observe', location.href);
  target.search = '?nonce=' + nonce + '&source=worker';
  fetch(target, {credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error',
    cache: 'no-store', mode: 'same-origin', signal: controller.signal})
    .then(async response => {
      const value = await read(response);
      const ok = response.ok && value && typeof value === 'object' && !Array.isArray(value) && value.schema === 1 && value.protocol === protocol &&
        value.nonce === nonce && value.source === 'worker-fetch' && value.ok === true;
      postMessage({schema: 1, protocol, nonce, status: ok ? 'complete' : 'failed', js,
        ...(ok ? {} : {error: 'worker-response-protocol-mismatch'})});
    }).catch(error => postMessage({schema: 1, protocol, nonce, status: 'failed', js,
      error: timedOut ? 'worker-response-timeout' : /^worker-response-[a-z0-9-]{1,64}$/.test(error?.message || '') ? error.message : 'worker-response-transport-failed'}))
    .finally(() => clearTimeout(timer));
}

function frameScript(nonce, protocol, parentOrigin) {
  let ended = false;addEventListener('pagehide', () => {ended = true;}, {once: true});
  controlledFrameGraphics().then(apiChecks => {
    if (!ended) parent.postMessage({pocketRequestIdentityFrame: nonce, schema: 1, protocol, nonce,
      source: 'controlled-cross-origin-iframe', origin: location.origin, apiChecks}, parentOrigin);
  });
}

function createIdentityService(options) {
  const base = options.basePath || DEFAULT_BASE;
  if (!/^\/(?:[A-Za-z0-9_-]+\/)+$/.test(base)) throw Error('Invalid detector base path');
  const ttlMs = options.ttlMs ?? 30000;
  const maxChecks = options.maxChecks ?? 64;
  const maxLogEvents = options.maxLogEvents ?? 4096;
  const frameEndpoint = options.frameEndpoint ? canonicalEndpoint(options.frameEndpoint) : '';
  const frameParentOrigin = options.frameParentOrigin ? canonicalOrigin(options.frameParentOrigin) : '';
  if (options.frameEndpoint && !frameEndpoint || options.frameParentOrigin && !frameParentOrigin) throw Error('Invalid explicit frame endpoint or parent origin');
  const controlledFrameGraphics = frameParentOrigin ? require('./context_graphics_probe.cjs').controlledFrameGraphics : null;
  if (frameParentOrigin && typeof controlledFrameGraphics !== 'function') throw Error('Controlled frame graphics implementation unavailable');
  if (!Number.isInteger(ttlMs) || ttlMs < 1000 || ttlMs > 30000 ||
      !Number.isInteger(maxChecks) || maxChecks < 1 || maxChecks > 64 ||
      !Number.isInteger(maxLogEvents) || maxLogEvents < 1 || maxLogEvents > 4096)
    throw Error('Detector limits out of range');
  const outputs = [options.output, options.rawLog].filter(Boolean).map(value => path.resolve(value));
  if (new Set(outputs).size !== outputs.length) throw Error('Distinct output paths required');
  if (outputs.some(value => fs.existsSync(value) || fs.existsSync(value + '.partial')))
    throw Error('Output already exists; choose a new evidence path');
  const checks = new Map();
  const frameChecks = new Map();
  const log = {schema: 1, protocol: PROTOCOL, scope: 'Independent controlled HTTPS arrivals; not browser or anonymity acceptance',
    startedAt: Date.now(), basePath: base, events: [], dropped: 0};
  const sockets = new Set();
  let eventSerial = 0;
  function save() {
    if (options.output) {
      fs.writeFileSync(options.output + '.partial', JSON.stringify(log, null, 2) + '\n');
      fs.renameSync(options.output + '.partial', options.output);
    }
  }
  function prune() {const now = Date.now(); for (const values of [checks, frameChecks]) for (const [nonce, state] of values) if (state.expiresAt <= now) values.delete(nonce);}
  function emit(nonce, event) {
    const row = {sequence: ++eventSerial, nonce, ...event};
    if (log.events.length >= maxLogEvents) log.dropped++;
    else {log.events.push(row); if (options.rawLog) fs.appendFileSync(options.rawLog, JSON.stringify(row) + '\n');}
    save();
  }
  function snapshot(nonce, state) {
    return {schema: 1, protocol: PROTOCOL, nonce,
      status: state?.reason ? 'rejected' : state && SOURCES.every(source => state.events.some(e => e.source === source)) ? 'ready' : 'pending',
      createdAt: state?.createdAt || 0, expiresAt: state?.expiresAt || 0,
      credentialObserved: state?.credentialObserved || false, reason: state?.reason || '',
      events: state?.events || [],
      source: 'independent-https-server-records',
      peerMeaning: 'Direct TLS socket peer only; forwarded headers are not trusted',
      scope: 'Controlled top-level detector document and Dedicated Worker requests, not ChatGPT or an account document'};
  }
  const server = https.createServer({key: options.key, cert: options.cert, minVersion: 'TLSv1.2', maxHeaderSize: 8192}, (request, response) => {
    const headers = {'Cache-Control': 'no-store', 'Pragma': 'no-cache', 'Referrer-Policy': 'no-referrer',
      'X-Content-Type-Options': 'nosniff', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'};
    const reply = (status, body, type = 'application/json') => {
      response.writeHead(status, {...headers, 'Content-Type': type + '; charset=utf-8'});
      response.end(typeof body === 'string' ? body : JSON.stringify(body));
    };
    if (request.method !== 'GET' || request.url.length > 2048 || request.headers['transfer-encoding'] ||
        (request.headers['content-length'] && request.headers['content-length'] !== '0')) {
      request.resume(); response.setHeader('Connection', 'close'); reply(400, {error: 'invalid-request'}); return;
    }
    let url;
    try {url = new URL(request.url, 'https://detector.invalid');} catch (_) {reply(400, {error: 'invalid-url'}); return;}
    const operation = url.pathname.startsWith(base) ? url.pathname.slice(base.length) : '';
    if (!['document', 'worker.js', 'observe', 'result', 'capabilities', 'frame'].includes(operation)) {
      // Optional host integration is server-operator code, never a protocol or
      // request parameter. It cannot override any detector endpoint.
      const extra = options.onUnhandled || options.extraHandler;
      if (typeof extra === 'function' && extra(request, response) === true) return;
      reply(404, {error: 'not-found'}); return;
    }
    const nonce = url.searchParams.get('nonce');
    const frameRequested = operation === 'document' && url.searchParams.has('frame');
    const permitted = operation === 'observe' ? ['nonce', 'source'] : operation === 'document' ? ['nonce', 'frame'] : ['nonce'];
    if (!NONCE.test(nonce || '') || url.searchParams.getAll('nonce').length !== 1 ||
        [...url.searchParams.keys()].some(key => !permitted.includes(key)) ||
        (operation === 'observe' && (url.searchParams.getAll('source').length !== 1 || url.searchParams.get('source') !== 'worker')) ||
        (frameRequested && (url.searchParams.getAll('frame').length !== 1 || url.searchParams.get('frame') !== '1'))) {
      reply(400, {error: 'invalid-check-identity'}); return;
    }
    prune();
    let state = checks.get(nonce);
    const sensitiveHeaders = {cookie: request.headers.cookie !== undefined, authorization: request.headers.authorization !== undefined,
      proxyAuthorization: request.headers['proxy-authorization'] !== undefined, referer: request.headers.referer !== undefined,
      origin: request.headers.origin !== undefined};
    const credentialObserved = Object.values(sensitiveHeaders).some(Boolean);
    const headerLimits = {'user-agent': 2048, 'accept-language': 1024, 'sec-fetch-dest': 64, 'sec-fetch-site': 64};
    const longFields = Object.keys(headerLimits).filter(name => typeof request.headers[name] === 'string' && request.headers[name].length > headerLimits[name]);
    const headerValueTooLong = longFields.length > 0;
    const requestOrigin = canonicalOrigin('https://' + request.headers.host);
    const crossOriginFrame = !!(frameEndpoint && requestOrigin && new URL(frameEndpoint).origin !== requestOrigin);
    if (operation === 'capabilities' || operation === 'frame') {
      const source = operation === 'capabilities' ? 'controlled-service-capabilities' : 'controlled-cross-origin-iframe';
      const reject = (status, reason) => reply(status, {schema: 1, protocol: PROTOCOL, nonce, source, status: 'unavailable', reason,
        ...(credentialObserved ? {credentialObserved: true} : {})});
      if (credentialObserved) {reject(403, 'credential-header-observed');return;}
      if (headerValueTooLong) {reject(409, 'header-value-too-long');return;}
      if (operation === 'capabilities') {
        if (checks.size + frameChecks.size >= maxChecks) {reject(429, 'detector-capacity');return;}
        reply(200, {schema: 1, protocol: PROTOCOL, nonce, source, status: 'ready',
          backgroundCoverage: {sharedWorker: false, serviceWorker: false},
          capabilities: {topLevelDocument: true, dedicatedWorker: true, boundedWorkerReply: true,
            crossOriginFrame, crossOriginFrameReceiver: !!frameParentOrigin,
            ...(crossOriginFrame ? {frameEndpoint, frameParentOrigin: requestOrigin} : {}),
            ...(frameParentOrigin ? {frameReceiverParentOrigin: frameParentOrigin} : {})},
          limits: {checkTtlMs: ttlMs, maxConcurrentChecks: maxChecks, maxCheckEvents: 12, workerResponseBytes: WORKER_RESPONSE_BYTES}});return;
      }
      if (!frameParentOrigin) {reject(404, 'frame-receiver-not-configured');return;}
      if (frameChecks.has(nonce)) {reject(409, 'duplicate-frame-probe');return;}
      if (checks.size + frameChecks.size >= maxChecks) {reject(429, 'detector-capacity');return;}
      frameChecks.set(nonce, {expiresAt: Date.now() + ttlMs});
      emit(nonce, {index: 1, source: 'cross-origin-frame', at: Date.now(), method: 'GET', path: url.pathname,
        headers: {userAgent: headerText(request.headers['user-agent']), acceptLanguage: headerText(request.headers['accept-language']),
          secFetchDest: headerText(request.headers['sec-fetch-dest']), secFetchSite: headerText(request.headers['sec-fetch-site'])},
        peer: {address: String(request.socket.remoteAddress || '').replace(/^::ffff:/, ''), source: 'socket-peer'}, sensitiveHeaders});
      const scriptNonce = crypto.randomBytes(18).toString('base64');
      headers['Content-Security-Policy'] = `default-src 'none'; script-src 'nonce-${scriptNonce}'; connect-src 'none'; frame-src 'none'; frame-ancestors ${frameParentOrigin}; base-uri 'none'; form-action 'none'; object-src 'none'`;
      reply(200, `<!doctype html><meta charset="utf-8"><title>Controlled frame graphics</title><script nonce="${scriptNonce}">\n${controlledFrameGraphics.toString()}\n(${frameScript.toString()})(${JSON.stringify(nonce)},${JSON.stringify(PROTOCOL)},${JSON.stringify(frameParentOrigin)});\n</script>`, 'text/html');return;
    }
    if (frameRequested && !crossOriginFrame) {reply(409, {schema: 1, protocol: PROTOCOL, nonce, status: 'rejected', reason: 'frame-endpoint-not-configured'});return;}
    if (!state && operation === 'document') {
      if (checks.size + frameChecks.size >= maxChecks) {reply(429, {schema: 1, protocol: PROTOCOL, nonce, error: 'detector-capacity'}); return;}
      state = {createdAt: Date.now(), expiresAt: Date.now() + ttlMs, events: [], credentialObserved: false, reason: ''}; checks.set(nonce, state);
    }
    if (!state) {
      if (credentialObserved) {reply(403, {...snapshot(nonce, null), status: 'rejected', credentialObserved: true, reason: 'credential-header-observed'}); return;}
      if (headerValueTooLong) {reply(409, {...snapshot(nonce, null), status: 'rejected', reason: 'header-value-too-long'}); return;}
      reply(operation === 'result' ? 202 : 409, {...snapshot(nonce, null), reason: 'document-not-observed'}); return;
    }
    const source = ({document: 'document', 'worker.js': 'worker-script', observe: 'worker-fetch', result: 'control-result'})[operation];
    const repeatedResult = source === 'control-result' && state.events.some(e => e.source === source);
    if (!repeatedResult || credentialObserved || headerValueTooLong) {
      if (state.events.length >= 12) state.reason = 'event-limit';
      else {
        const address = String(request.socket.remoteAddress || '').replace(/^::ffff:/, '');
        const event = {index: state.events.length + 1, source, at: Date.now(), method: request.method, path: url.pathname,
          headers: headerValueTooLong ? {userAgent: '', acceptLanguage: '', secFetchDest: '', secFetchSite: ''}
            : {userAgent: headerText(request.headers['user-agent']), acceptLanguage: headerText(request.headers['accept-language']),
              secFetchDest: headerText(request.headers['sec-fetch-dest']), secFetchSite: headerText(request.headers['sec-fetch-site'])},
          peer: {address, source: 'socket-peer'}, sensitiveHeaders,
          ...(headerValueTooLong ? {headerValueTooLong: true, rejectedHeaderFields: longFields, rejectionReason: 'header-value-too-long'} : {})};
        if (source !== 'control-result' && state.events.some(e => e.source === source)) state.reason = 'duplicate-probe-source';
        state.events.push(event); emit(nonce, event);
      }
    }
    if (headerValueTooLong) state.reason = 'header-value-too-long';
    if (credentialObserved) {state.credentialObserved = true; state.reason = 'credential-header-observed';}
    if (state.reason) {reply(credentialObserved ? 403 : 409, snapshot(nonce, state)); return;}
    if (operation === 'result') {const value = snapshot(nonce, state); reply(value.status === 'ready' ? 200 : 202, value); return;}
    if (operation === 'observe') {reply(200, {schema: 1, protocol: PROTOCOL, nonce, source, ok: true}); return;}
    if (operation === 'worker.js') {
      headers['Content-Security-Policy'] = "default-src 'none'; connect-src 'self'; script-src 'self'";
      reply(200, `'use strict';\n${javascriptObservation.toString()}\n(${workerScript.toString()})(${JSON.stringify(nonce)},${JSON.stringify(PROTOCOL)});\n`, 'application/javascript'); return;
    }
    const scriptNonce = crypto.randomBytes(18).toString('base64');
    headers['Content-Security-Policy'] = `default-src 'none'; script-src 'nonce-${scriptNonce}'; worker-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-src ${frameRequested ? new URL(frameEndpoint).origin : "'none'"}; object-src 'none'`;
    reply(200, '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>Controlled request identity check</title>' +
      '<h1>受控请求身份检测</h1><p>这是独立检测页面，不是 ChatGPT。请在应用的环境自检中查看并采集结果。</p>' +
      '<p>检测结束不会自动跳转。你可以使用浏览器返回原聊天；返回不会自动重发聊天消息。</p>' +
      `<script nonce="${scriptNonce}" data-nonce="${nonce}" data-protocol="${PROTOCOL}"${frameRequested ? ' data-frame-endpoint="' + frameEndpoint.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"' : ''}>\n${javascriptObservation.toString()}\n(${documentScript.toString()})();\n</script>`, 'text/html');
  });
  server.requestTimeout = 6000; server.headersTimeout = 6000; server.keepAliveTimeout = 1000;
  server.maxConnections = 128; server.maxRequestsPerSocket = 24;
  server.on('connection', socket => {sockets.add(socket); socket.on('close', () => sockets.delete(socket));});
  server.on('tlsClientError', () => {});
  const timer = setInterval(prune, 1000); timer.unref();
  return {server, log, snapshot: nonce => snapshot(nonce, checks.get(nonce)),
    close: () => new Promise(resolve => {clearInterval(timer); for (const socket of sockets) socket.destroy(); server.close(resolve);})};
}

if (require.main === module) {
  const args = process.argv.slice(2), values = {};
  for (let i = 0; i < args.length; i += 2) {
    if (!['--key', '--cert', '--host', '--port', '--base-path', '--output', '--raw-log', '--frame-endpoint', '--frame-parent-origin'].includes(args[i]) || !args[i + 1])
      throw Error('Usage: --key TLS_KEY_PATH --cert TLS_CERT_PATH [--host 127.0.0.1 --port 9889 --base-path /pocketchat-identity/v1/ --output REPORT_PATH --raw-log JSONL_PATH]');
    values[args[i]] = args[i + 1];
  }
  if (!values['--key'] || !values['--cert']) throw Error('TLS certificate and key paths required');
  const port = Number(values['--port'] || 9889);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('Invalid listen port');
  const service = createIdentityService({key: fs.readFileSync(values['--key']), cert: fs.readFileSync(values['--cert']),
    basePath: values['--base-path'], output: values['--output'], rawLog: values['--raw-log'],
    frameEndpoint: values['--frame-endpoint'], frameParentOrigin: values['--frame-parent-origin']});
  service.server.listen(port, values['--host'] || '127.0.0.1', () => {
    process.stdout.write(JSON.stringify({status: 'listening', protocol: PROTOCOL, port, host: values['--host'] || '127.0.0.1'}) + '\n');
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => service.close().then(() => process.exit(0)));
}

module.exports = {createIdentityService, createIdentityServer: createIdentityService, PROTOCOL, DEFAULT_BASE, WORKER_RESPONSE_BYTES};
