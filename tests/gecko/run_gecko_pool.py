#!/usr/bin/env python3
"""Observe real Gecko HTTP/2 sockets over actual managed two-hop Mihomo on Android."""
import argparse
import hashlib
import json
import pathlib
import select
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'tools'))
from gecko.chain_runtime_contract import verify_gecko_pool
from gecko.site_permission_evidence import permission_tap_command, verify_site_permission_evidence
from gecko.caret_ime_guard import redact_service_api_keys, verify_capture_privacy, diagnostic_privacy_summary

OUT = ROOT / 'work/gecko-integration'
PORT = 9877
PACKAGE = 'local.pocketchat.test'
PAYLOAD = 'pool-payload-' * 700

# Node's actual TLS/HTTP2 implementation supplies negotiated ALPN, TCP connection
# identity and HTTP2 stream IDs. No browser responses are mocked or substituted.
NODE = r'''
'use strict';
const fs=require('node:fs'),http2=require('node:http2'),crypto=require('node:crypto');
const [key,cert,report]=process.argv.slice(2),port=9877;
const sockets=new Set(),connectionIds=new Map();let next=0;
const evidence={protocol:'h2',requests:[],connections:[],webSockets:[],publicTraffic:false};
function save(){const temporary=report+'.tmp';fs.writeFileSync(temporary,JSON.stringify(evidence,null,2)+'\n');fs.renameSync(temporary,report)}
const server=http2.createSecureServer({key:fs.readFileSync(key),cert:fs.readFileSync(cert),allowHTTP1:true});
server.on('secureConnection',socket=>{
  const id=++next;connectionIds.set(socket.remotePort,id);sockets.add(socket);
  evidence.connections.push({connection:id,alpn:socket.alpnProtocol,remote:socket.remoteAddress,remotePort:socket.remotePort,tls:socket.getProtocol()});save();
  socket.on('close',()=>sockets.delete(socket));
});
server.on('session',session=>session.on('error',()=>{}));
server.on('stream',(stream,headers)=>{
  stream.on('error',()=>{});const socket=stream.session.socket;
  const address=new URL(headers[':path'],'https://127.0.0.1:'+port);
  const connection=connectionIds.get(socket.remotePort)||0;
  const record={method:headers[':method'],path:address.pathname,id:address.searchParams.get('id')||'',protocol:socket.alpnProtocol,connection,streamId:stream.id};
  evidence.requests.push(record);
  let body,type;
  if(address.pathname==='/pool'){
    type='text/html; charset=utf-8';
    body=Buffer.from('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Controlled HTTP2 pool fixture</title>'+
      '<h1 id="pool-ready">Real HTTP/2 connection pool fixture</h1><textarea id="prompt-textarea">unsent pool draft</textarea><output id="send-count">0</output>');
  }else if(address.pathname==='/bytes'){
    type='application/json';
    body=Buffer.from(JSON.stringify({id:record.id,protocol:socket.alpnProtocol,connection,streamId:stream.id,body:'pool-payload-'.repeat(700)}));
  }else{
    stream.respond({':status':404,'content-length':'0'});stream.end();save();return;
  }
  record.responseBytes=body.length;record.responseSha256=crypto.createHash('sha256').update(body).digest('hex');
  stream.respond({':status':200,'content-type':type,'content-length':String(body.length),'cache-control':'no-store'});stream.end(body);
  stream.on('close',()=>{record.closed=true;save()});save();
});
server.on('request',(request,response)=>{
  if(request.httpVersionMajor===2)return;
  evidence.requests.push({method:request.method,path:request.url,protocol:'http/1.1',unexpectedHttp1:true});
  response.writeHead(400,{'content-length':'0'});response.end();save();
});
server.on('upgrade',(request,socket,head)=>{
  if(request.url!=='/ws'||!request.headers['sec-websocket-key']){socket.destroy();return}
  const connection=connectionIds.get(socket.remotePort)||0;
  const record={connection,protocol:socket.alpnProtocol||'http/1.1',frames:0,payloads:[],closed:false};evidence.webSockets.push(record);
  const accept=crypto.createHash('sha1').update(request.headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\n\r\n');
  let buffered=head;
  function parse(){
    while(buffered.length>=2){
      const opcode=buffered[0]&15,size=buffered[1]&127;
      if(!(buffered[0]&128)||!(buffered[1]&128)||size>=126){socket.destroy();return}
      if(buffered.length<6+size)return;
      const mask=buffered.subarray(2,6),body=Buffer.from(buffered.subarray(6,6+size));buffered=buffered.subarray(6+size);
      for(let i=0;i<body.length;i++)body[i]^=mask[i%4];
      if(opcode===8){socket.end();return}if(opcode!==1){socket.destroy();return}
      const payload=body.toString(),reply=Buffer.from(JSON.stringify({connection,payload}));
      if(reply.length>=126){socket.destroy();return}
      record.frames++;if(record.payloads.length<300)record.payloads.push(payload);
      socket.write(Buffer.concat([Buffer.from([0x81,reply.length]),reply]));save();
    }
  }
  socket.on('data',bytes=>{buffered=Buffer.concat([buffered,bytes]);parse()});socket.on('error',()=>{});socket.on('close',()=>{record.closed=true;save()});parse();save();
});
server.on('error',error=>{console.error(error);process.exitCode=1});
server.listen(port,'127.0.0.1',()=>{save();console.log(JSON.stringify({ready:true,port,protocol:'h2'}))});
process.on('SIGTERM',()=>{for(const socket of sockets)socket.destroy();server.close(()=>process.exit(0))});
'''


def verify(report, server):
    return verify_gecko_pool(report, server)


def capture_diagnostic_text(value):
    """Return a verified derivative capture before parsing, raising or storing it."""
    sanitized, metadata = redact_service_api_keys(value)
    if not verify_capture_privacy(metadata, sanitized):
        raise ValueError('Diagnostic capture privacy: invalid derivative metadata')
    return sanitized, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    privacy_captures = []
    def capture_text(value):
        sanitized, metadata = capture_diagnostic_text(value)
        if len(privacy_captures) >= 4096:
            raise ValueError('Diagnostic capture privacy: capture-count bound')
        privacy_captures.append(metadata)
        return sanitized

    def adb(*parts, binary=False):
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=not binary, timeout=30)

    def log():
        return capture_text(adb('logcat', '-d', '-s', 'PocketGeckoPool:I', 'AndroidRuntime:E', '*:S'))

    with tempfile.TemporaryDirectory(prefix='gecko-pool-') as temporary:
        directory = pathlib.Path(temporary)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '1',
                        '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
                        '-keyout', str(directory / 'key.pem'), '-out', str(directory / 'cert.pem')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (directory / 'fixture.js').write_text(NODE)
        process = subprocess.Popen(['node', str(directory / 'fixture.js'), str(directory / 'key.pem'),
                                    str(directory / 'cert.pem'), str(directory / 'server.json')],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        report = None
        permission_gestures = []
        permission_taps = {}
        try:
            ready, _, _ = select.select([process.stdout], [], [], 10)
            assert ready and json.loads(process.stdout.readline()) == {'ready': True, 'port': PORT, 'protocol': 'h2'}
            adb('reverse', 'tcp:' + str(PORT), 'tcp:' + str(PORT))
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'pm', 'clear', PACKAGE)
            adb('logcat', '-c')
            adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.GeckoConnectionPoolIntegrationActivity')
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                raw = log()
                if 'FATAL EXCEPTION' in raw:
                    raise AssertionError(raw)
                done = []
                for line in raw.splitlines():
                    if TAG_IN_LINE(line):
                        value = json.loads(line[line.index('{'):])
                        if value.get('kind') == 'permissionTapNeeded':
                            bounds = value['value']
                            key = (bounds.get('nonce'), bounds.get('stage'))
                            if key in permission_taps:
                                assert permission_taps[key] == bounds, 'Permission gesture changed after its one attempt'
                            else:
                                command = permission_tap_command(bounds, [row['stage'] for row in permission_gestures])
                                adb(*command)
                                permission_taps[key] = bounds
                                permission_gestures.append(dict(nonce=bounds['nonce'], stage=bounds['stage'], command=command,
                                                                bounds=bounds, oneAttempt=True))
                        if value.get('kind') == 'report':
                            done.append(value['value'])
                if done:
                    report = json.loads(adb('exec-out', 'content', 'read', '--uri',
                        'content://local.pocketchat.test.evidence/gecko-pool'))
                    assert done[-1]['status'] == report['status'] and done[-1]['checkCount'] == len(report['checks'])
                    break
                time.sleep(1)
            if report is None:
                raise TimeoutError('No actual Gecko connection-pool result')
            report['sourceCommit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            report['androidSdk'] = int(adb('shell', 'getprop', 'ro.build.version.sdk').strip())
            server = json.loads((directory / 'server.json').read_text())
            report['server'] = server
            report['sitePermissionsGestures'] = permission_gestures
            report['capturePrivacy'] = diagnostic_privacy_summary(privacy_captures)
            (OUT / 'gecko-pool-results.json').write_text(json.dumps(report, indent=2) + '\n')
            (OUT / 'gecko-pool-log.txt').write_text(raw)
            verify(report, server)
            permission_result = verify_site_permission_evidence(report['sitePermissions'], permission_gestures)
            (OUT / 'site-permission-sdk-results.json').write_text(json.dumps(dict(evidence=report['sitePermissions'], gestures=permission_gestures,
                                                                             verification=permission_result,
                                                                             sourceCommit=report['sourceCommit']), indent=2) + '\n')
            print(json.dumps({'status': report['status'], 'checks': len(report['checks']),
                              'actualHttp2Requests': len([r for r in server['requests'] if r['path'] == '/bytes']),
                              'webSocketFrames': server['webSockets'][0]['frames'], 'sourceCommit': report['sourceCommit']}), flush=True)
        except BaseException:
            (OUT / 'gecko-pool-failure-log.txt').write_text(capture_text(adb('logcat', '-d')))
            if (directory / 'server.json').exists():
                (OUT / 'gecko-pool-server-failure.json').write_bytes((directory / 'server.json').read_bytes())
            raise
        finally:
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('reverse', '--remove', 'tcp:' + str(PORT))
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


def TAG_IN_LINE(line):
    return 'PocketGeckoPool' in line and '{' in line


if __name__ == '__main__':
    main()
