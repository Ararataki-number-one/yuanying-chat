'use strict';
// Diagnostic-only HTTPS/WSS observer. It forwards no traffic and uses no account.
const fs = require('node:fs');
const https = require('node:https');
const crypto = require('node:crypto');
const [key, certificate, output, nonce, rawLog] = process.argv.slice(2);
if (!/^[a-f0-9]{32}$/.test(nonce)) throw Error('Exact diagnostic nonce required');
const port = 9889, phases = ['warmup', 'full-vpn', 'split-vpn', 'vpn-removed'];
let sequence = 0, connectionSerial = 0, dropped = 0;
const sockets = new Set(), ids = new WeakMap();
const report = {schema: 1, runNonce: nonce, port, bindAddress: '0.0.0.0', events: [], dropped: 0,
  scope: 'Independent controlled HTTPS/WSS server; arrivals are observations, not protection acceptance'};
function save() {
  report.dropped = dropped;
  fs.writeFileSync(output + '.partial', JSON.stringify(report, null, 2) + '\n');
  fs.renameSync(output + '.partial', output);
}
function event(kind, value) {
  const row = {index: ++sequence, kind, atUnixMs: Date.now(), atMonotonicNs: process.hrtime.bigint().toString(), ...value};
  if (report.events.length >= 2048) dropped++;
  else {report.events.push(row); fs.appendFileSync(rawLog, JSON.stringify(row) + '\n');}
  save(); return row;
}
function target(request) {
  const url = new URL(request.url, 'https://10.0.2.2:' + port);
  if (url.searchParams.get('runNonce') !== nonce || url.searchParams.getAll('runNonce').length !== 1) return null;
  const phase = url.searchParams.get('phase');
  if (url.pathname !== '/page' && !phases.includes(phase)) return null;
  return {path: url.pathname, phase, requestKind: url.searchParams.get('kind') || '',
    serial: url.searchParams.get('serial') || '', runNonce: nonce};
}
function page() {
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controlled network protection observation</title><h1>Controlled VPN route fixture</h1>
<p>No account, ChatGPT, public-network, physical-phone or complete leak-free acceptance.</p>
<pre id="network-probe-ready"></pre><pre id="network-probe-result"></pre>
<script>(${pageScript.toString()})(${JSON.stringify(nonce)});</script>`;
}
function pageScript(runNonce) {
  'use strict';
  const phases = ['warmup', 'full-vpn', 'split-vpn', 'vpn-removed'];
  let serial = 0, existing = null, inFlight = false, next = 0, generation = 0, establishedPhase = '', existingServerConnection = null;
  window.probeResults = Object.create(null);
  const url = (path, phase, kind) => {
    const value = new URL(path, location.origin);
    for (const [key, data] of Object.entries({runNonce, phase, kind, serial: String(++serial)})) value.searchParams.set(key, data);
    return value;
  };
  const errorText = error => String(error && (error.name + ': ' + error.message) || error).slice(0, 300);
  async function fetchProbe(phase) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch(url('/probe', phase, 'fetch'), {cache: 'no-store', signal: controller.signal});
      const data = await response.json();
      return {ok: response.ok && data.runNonce === runNonce && data.phase === phase && data.kind === 'fetch', status: response.status, value: data};
    } catch (error) {return {ok: false, error: errorText(error)};}
    finally {clearTimeout(timer);}
  }
  function echo(socket, phase, kind, closeAfter) {
    const payload = [runNonce, phase, kind, ++serial].join('|');
    return new Promise(resolve => {
      let done = false;
      const finish = value => {
        if (done) return; done = true; clearTimeout(timer);
        for (const [name, callback] of listeners) socket.removeEventListener(name, callback);
        const result = {payload, readyState: socket.readyState, ...value};
        if (closeAfter) try {socket.close();} catch (_) {}
        resolve(result);
      };
      const send = () => {try {socket.send(payload);} catch (error) {finish({ok: false, error: errorText(error)});}};
      const message = e => {
        let value; try {value = JSON.parse(e.data);} catch (_) {return;}
        if (value.payload === payload) finish({ok: true, echo: value, trustedMessage: e.isTrusted});
      };
      const listeners = [['open', send], ['message', message],
        ['error', () => finish({ok: false, error: 'websocket-error'})],
        ['close', e => finish({ok: false, error: 'websocket-closed', closeCode: e.code})]];
      const timer = setTimeout(() => finish({ok: false, error: 'timeout'}), 2500);
      for (const [name, callback] of listeners) socket.addEventListener(name, callback);
      if (socket.readyState === WebSocket.OPEN) send();
      else if (socket.readyState !== WebSocket.CONNECTING) finish({ok: false, error: 'not-open'});
    });
  }
  async function websocket(phase, permanent) {
    const kind = permanent ? 'existing' : 'new';
    try {
      if (permanent && !existing) {
        if (phase !== 'warmup') return {ok: false, error: 'warmup-socket-absent', automaticallyRecreated: false};
        const target = url('/ws', phase, kind); target.protocol = 'wss:';
        existing = new WebSocket(target); generation = 1; establishedPhase = phase;
      }
      let socket = existing;
      if (!permanent) {const target = url('/ws', phase, kind); target.protocol = 'wss:'; socket = new WebSocket(target);}
      const result = await echo(socket, phase, kind, !permanent);
      if (permanent && result.ok) existingServerConnection = result.echo.connection;
      return {...result, permanent, automaticallyRecreated: false,
        socketGeneration: permanent ? generation : null, establishedPhase: permanent ? establishedPhase : phase,
        serverConnection: permanent ? existingServerConnection : result.echo?.connection || null};
    } catch (error) {return {ok: false, error: errorText(error), permanent, automaticallyRecreated: false,
      socketGeneration: permanent ? generation : null, establishedPhase: permanent ? establishedPhase : phase,
      serverConnection: permanent ? existingServerConnection : null};}
  }
  function worker(phase) {
    return new Promise(resolve => {
      let instance, done = false;
      const finish = result => {if (done) return; done = true; clearTimeout(timer); if (instance) instance.terminate(); resolve(result);};
      const timer = setTimeout(() => finish({ok: false, error: 'timeout'}), 2500);
      try {
        instance = new Worker(url('/worker.js', phase, 'worker-script'));
        instance.onmessage = e => finish({ok: e.data.ok === true && e.data.runNonce === runNonce && e.data.phase === phase, value: e.data, trustedMessage: e.isTrusted});
        instance.onerror = e => {e.preventDefault(); finish({ok: false, error: String(e.message || 'worker-error'), trustedError: e.isTrusted});};
      } catch (error) {finish({ok: false, error: errorText(error)});}
    });
  }
  window.probe = async phase => {
    if (inFlight || phase !== phases[next] || Object.hasOwn(window.probeResults, phase)) return false;
    inFlight = true; next++;
    // Deliberate positive-control seed, exactly once before STOP. This is not
    // an automatic fault/recovery reconnect; vpn-removed reuses generation2.
    if (phase === 'split-vpn') {
      if (existing) try {existing.close();} catch (_) {}
      const target = url('/ws', phase, 'existing'); target.protocol = 'wss:';
      existing = new WebSocket(target); generation = 2; establishedPhase = phase; existingServerConnection = null;
    }
    const startedAt = performance.now();
    const [fetchResult, newWebSocket, existingWebSocket, dedicatedWorker] = await Promise.all([
      fetchProbe(phase), websocket(phase, false), websocket(phase, true), worker(phase)]);
    const result = {phase, runNonce, done: true, startedAt, endedAt: performance.now(),
      fetch: fetchResult, newWebSocket, existingWebSocket, dedicatedWorker,
      documentUrl: location.href, timeOrigin: performance.timeOrigin, noAutomaticReconnect: true,
      explicitPositiveControlReseed: phase === 'split-vpn', existingGeneration: generation};
    window.probeResults[phase] = result;
    document.getElementById('network-probe-result').textContent = JSON.stringify(result);
    inFlight = false; return result;
  };
  document.addEventListener('pocket-network-probe', e => {if (typeof e.detail === 'string' && phases.includes(e.detail)) window.probe(e.detail);});
  window.probeReady = true;
  document.getElementById('network-probe-ready').textContent = runNonce;
}
const server = https.createServer({key: fs.readFileSync(key), cert: fs.readFileSync(certificate), ALPNProtocols: ['http/1.1']}, (request, response) => {
  const found = target(request), connection = ids.get(request.socket) || 0;
  response.shouldKeepAlive = false; response.setHeader('Connection', 'close'); response.setHeader('Cache-Control', 'no-store');
  if (!found || request.method !== 'GET') {response.writeHead(403); response.end(); return;}
  event('http', {connection, ...found, method: request.method, host: request.headers.host,
    userAgent: request.headers['user-agent'] || '', acceptLanguage: request.headers['accept-language'] || '',
    hasCookie: !!request.headers.cookie, hasAuthorization: !!request.headers.authorization});
  let body, type;
  if (found.path === '/page') {body = page(); type = 'text/html; charset=utf-8';}
  else if (found.path === '/worker.js') {
    const next = '/worker-probe?' + new URLSearchParams({runNonce: nonce, phase: found.phase, kind: 'worker-fetch', serial: found.serial});
    body = `const c=new AbortController(),t=setTimeout(()=>c.abort(),2200);fetch(${JSON.stringify(next)},{cache:'no-store',signal:c.signal}).then(async r=>({ok:r.ok,status:r.status,...await r.json()})).then(v=>postMessage(v),e=>postMessage({ok:false,error:String(e.name+': '+e.message),runNonce:${JSON.stringify(nonce)},phase:${JSON.stringify(found.phase)}})).finally(()=>clearTimeout(t));`;
    type = 'application/javascript';
  } else if (found.path === '/probe' || found.path === '/worker-probe') {
    body = JSON.stringify({runNonce: nonce, phase: found.phase, kind: found.path === '/probe' ? 'fetch' : 'worker', connection, serial: found.serial}); type = 'application/json';
  } else {response.writeHead(404); response.end(); return;}
  response.writeHead(200, {'content-type': type, 'content-length': Buffer.byteLength(body)}); response.end(body);
});
server.on('secureConnection', socket => {
  const connection = ++connectionSerial; ids.set(socket, connection); sockets.add(socket);
  event('tls-open', {connection, remoteAddress: socket.remoteAddress, remotePort: socket.remotePort,
    localAddress: socket.localAddress, localPort: socket.localPort, tls: socket.getProtocol(), alpn: socket.alpnProtocol || ''});
  socket.on('error', error => event('socket-error', {connection, code: error.code || ''}));
  socket.on('close', () => {sockets.delete(socket); event('tls-close', {connection});});
});
server.on('tlsClientError', error => event('tls-client-error', {code: error.code || ''}));
server.on('upgrade', (request, socket, head) => {
  const found = target(request), connection = ids.get(socket) || 0;
  if (!found || found.path !== '/ws' || !request.headers['sec-websocket-key']) {socket.destroy(); return;}
  event('ws-open', {connection, ...found});
  const accept = crypto.createHash('sha1').update(request.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + '\r\n\r\n');
  let buffered = head;
  const parse = () => {
    while (buffered.length >= 2) {
      const opcode = buffered[0] & 15, length = buffered[1] & 127;
      if (!(buffered[0] & 128) || !(buffered[1] & 128) || length >= 126) {socket.destroy(); return;}
      if (buffered.length < 6 + length) return;
      const mask = buffered.subarray(2, 6), body = Buffer.from(buffered.subarray(6, 6 + length)); buffered = buffered.subarray(6 + length);
      for (let i = 0; i < body.length; i++) body[i] ^= mask[i % 4];
      if (opcode === 8) {socket.end(Buffer.from([0x88, 0])); return;}
      if (opcode !== 1) {socket.destroy(); return;}
      const payload = body.toString(), parts = payload.split('|');
      if (parts.length !== 4 || parts[0] !== nonce || !phases.includes(parts[1]) || !['existing', 'new'].includes(parts[2]) || !/^\d+$/.test(parts[3])) {socket.destroy(); return;}
      event('ws-frame', {connection, runNonce: nonce, phase: parts[1], requestKind: parts[2], serial: parts[3], payload});
      const reply = Buffer.from(JSON.stringify({connection, payload}));
      if (reply.length >= 126) {socket.destroy(); return;}
      socket.write(Buffer.concat([Buffer.from([0x81, reply.length]), reply]));
    }
  };
  socket.on('data', bytes => {buffered = Buffer.concat([buffered, bytes]); parse();}); parse();
});
server.on('error', error => {event('server-error', {code: error.code || '', message: error.message}); process.exitCode = 1;});
server.listen(port, '0.0.0.0', () => {event('listening', {port, bindAddress: '0.0.0.0'}); console.log(JSON.stringify({ready: true, port, runNonce: nonce}));});
process.on('SIGTERM', () => {event('stopping', {}); for (const socket of sockets) socket.destroy(); server.close(() => process.exit(0));});
