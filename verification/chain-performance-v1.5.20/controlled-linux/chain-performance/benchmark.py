#!/usr/bin/env python3
"""Local-only real Mihomo A/B: provider/listener route versus a simple Clash route.

This measures configuration overhead, not phone/Wi-Fi/provider speed. All destination
connections are enforced inside loopback fixture allowlists; no user subscription or
credentials are read. Artificial waits stand in for link RTT, shared by both variants.
"""
import concurrent.futures, hashlib, http.client, http.server, json, os
from pathlib import Path
import select, socket, socketserver, ssl, statistics, struct, subprocess, threading, time
import urllib.parse, urllib.request

ROOT = Path(__file__).resolve().parent
TCP = socketserver.ThreadingTCPServer
TCP.allow_reuse_address = True
TCP.daemon_threads = True
LOCK = threading.Lock()
EVENTS = []
HANDSHAKE_REPLY_WAIT = .020
FORWARD_WAIT = .010
HTTP_RESPONSE_WAIT = .020

def event(kind, **data):
    with LOCK:
        EVENTS.append(dict(kind=kind, at=time.monotonic(), **data))

def readn(s, n):
    result = b''
    while len(result) < n:
        chunk = s.recv(n-len(result))
        if not chunk:
            raise EOFError('socket ended')
        result += chunk
    return result

class Socks(socketserver.BaseRequestHandler):
    def handle(self):
        a = self.request
        a.settimeout(10)
        a.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        b = None
        try:
            assert readn(a, 1) == b'\x05'
            methods = readn(a, readn(a, 1)[0])
            assert 2 in methods
            time.sleep(HANDSHAKE_REPLY_WAIT)
            a.sendall(b'\x05\x02')
            assert readn(a, 1) == b'\x01'
            user = readn(a, readn(a, 1)[0])
            password = readn(a, readn(a, 1)[0])
            assert user == b'fixture' and password == b'local-only'
            time.sleep(HANDSHAKE_REPLY_WAIT)
            a.sendall(b'\x01\x00')
            ver, cmd, reserved, atyp = readn(a, 4)
            assert ver == 5 and cmd == 1 and reserved == 0
            if atyp == 1:
                host = socket.inet_ntoa(readn(a, 4))
            elif atyp == 3:
                host = readn(a, readn(a, 1)[0]).decode('ascii')
            else:
                raise ValueError('fixture only accepts IPv4 loopback')
            port = struct.unpack('!H', readn(a, 2))[0]
            permitted = host == '127.0.0.1' and port in self.server.allowed
            event('socksConnect', role=self.server.role, host=host, port=port,
                  permitted=permitted)
            if not permitted:
                a.sendall(b'\x05\x02\x00\x01'+b'\x00'*6)
                return
            b = socket.create_connection((host, port), 5)
            b.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            time.sleep(HANDSHAKE_REPLY_WAIT)
            a.sendall(b'\x05\x00\x00\x01'+b'\x00'*6)
            a.settimeout(None)
            b.settimeout(None)
            while True:
                ready, _, _ = select.select([a,b],[],[],10)
                if not ready:
                    return
                for source in ready:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    time.sleep(FORWARD_WAIT)
                    (b if source is a else a).sendall(chunk)
        except (OSError, EOFError):
            pass
        finally:
            if b:
                b.close()

class Probe(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_HEAD(self):
        time.sleep(HTTP_RESPONSE_WAIT)
        event('head', path=self.path, client=self.client_address,
              tls=isinstance(self.connection, ssl.SSLSocket))
        self.send_response(204)
        self.send_header('Content-Length', '0')
        if self.path == '/close':
            self.send_header('Connection', 'close')
            self.close_connection = True
        self.end_headers()
    def log_message(self, *args):
        pass

def serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]

def unused():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

def api(port, path, method='GET', data=None):
    req = urllib.request.Request('http://127.0.0.1:'+str(port)+path,
          data=None if data is None else json.dumps(data).encode(), method=method,
          headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=12) as response:
        body=response.read()
        return json.loads(body) if body else None

def socks_node(name, port):
    return {'name':name,'type':'socks5','server':'127.0.0.1','port':port,
            'username':'fixture','password':'local-only','udp':False}

def configuration(variant, directory, entry_port, exit_port, ca):
    proxy_port, controller = unused(), unused()
    fixed = socks_node('FixedExit', exit_port)
    fixed['dialer-proxy'] = 'EntryChoice'
    config = {'port':0,'socks-port':0,'mixed-port':0,'redir-port':0,'tproxy-port':0,
      'allow-lan':False,'bind-address':'127.0.0.1','mode':'rule',
      'unified-delay':True,'tcp-concurrent':True,'log-level':'silent','ipv6':False,
      'external-controller':'127.0.0.1:'+str(controller),'secret':'',
      'profile':{'store-selected':False,'store-fake-ip':False},
      'tun':{'enable':False},'sniffer':{'enable':False},'geo-auto-update':False,
      'tls':{'custom-certifactes':[ca]},
      'dns':{'enable':True,'listen':'127.0.0.1:0','ipv6':False,
             'enhanced-mode':'redir-host','cache-algorithm':'arc',
             'default-nameserver':['https://223.5.5.5/dns-query','https://223.6.6.6/dns-query'],
             'nameserver':['https://1.1.1.1/dns-query#FixedExit'],
             'proxy-server-nameserver':['https://dns.alidns.com/dns-query','https://doh.pub/dns-query']},
      'proxies':[fixed], 'proxy-groups':[]}
    if variant == 'app':
        entries = [socks_node('node-'+str(i),entry_port) for i in range(8)]
        (directory/'subscription.yaml').write_text(json.dumps({'proxies':entries}))
        config['proxy-providers'] = {'Subscription':{'type':'file','path':'./subscription.yaml',
          'health-check':{'enable':False},'override':{'additional-prefix':'Entry|'}}}
        def group(name, filt=None):
            g = {'name':name,'type':'select','proxies':['REJECT'],'use':['Subscription'],
                 'empty-fallback':'REJECT','interval':0,'hidden':True}
            if filt:
                g['filter'] = filt
            return g
        config['proxy-groups'] = [group('EntryChoice'),group('WebProbeEntry')]
        web = dict(fixed, name='WebProbeExit', **{'dialer-proxy':'WebProbeEntry'})
        config['proxies'].append(web)
        for i in range(8):
            config['proxy-groups'].append(group('ProbeEntry'+str(i),'^Entry\\|node-'+str(i)+'$'))
            config['proxies'].append(dict(fixed,name='ProbeExit'+str(i),
                 **{'dialer-proxy':'ProbeEntry'+str(i)}))
        config['rules']=['MATCH,REJECT']
        config['listeners']=[{'name':'PocketOnly','type':'mixed','listen':'127.0.0.1',
                              'port':proxy_port,'udp':False,'proxy':'FixedExit'}]
    else:
        config['proxies'].append(socks_node('Entry',entry_port))
        config['proxy-groups']=[{'name':'EntryChoice','type':'select','proxies':['Entry']}]
        config['mixed-port']=proxy_port
        config['rules']=['MATCH,FixedExit']
    (directory/'config.json').write_text(json.dumps(config))
    return proxy_port, controller

def head(port, target_port, https=False, client=None):
    own = client is None
    if own:
        if https:
            ctx = ssl.create_default_context(cafile=str(ROOT/'fixture.crt'))
            client = http.client.HTTPSConnection('127.0.0.1',port,timeout=10,context=ctx)
            client.set_tunnel('127.0.0.1',target_port)
        else:
            client = http.client.HTTPConnection('127.0.0.1',port,timeout=10)
    target = ('/' if https else 'http://127.0.0.1:'+str(target_port)+'/ok')
    start = time.perf_counter_ns()
    client.request('HEAD',target,headers={'Host':'127.0.0.1:'+str(target_port)})
    response = client.getresponse()
    response.read()
    assert response.status == 204
    duration = (time.perf_counter_ns()-start)/1e6
    if own:
        client.close()
    return duration

def sample(variant, entry_port, exit_port, http_port, https_port, ca, round_id):
    directory = ROOT/(variant+'-'+str(round_id))
    directory.mkdir(exist_ok=True)
    proxy, controller = configuration(variant,directory,entry_port,exit_port,ca)
    log = (directory/'core.log').open('w')
    process = subprocess.Popen([str(ROOT/'mihomo'),'-d',str(directory),'-f',str(directory/'config.json')],stdout=log,stderr=log)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError((directory/'core.log').read_text())
            try:
                current=api(controller,'/proxies/EntryChoice')
                if variant!='app' or 'Entry|node-0' in current.get('all',[]):
                    break
            except (OSError,urllib.error.URLError):
                time.sleep(.025)
        else:
            raise RuntimeError('core controller not ready')
        if variant == 'app':
            api(controller,'/proxies/EntryChoice','PUT',{'name':'Entry|node-0'})
        rows = []
        for scheme, target in [('http',http_port),('https',https_port)]:
            for i in range(8):
                rows.append({'measure':'coldHead','scheme':scheme,'ms':head(proxy,target,scheme=='https')})
            if scheme == 'https':
                ctx = ssl.create_default_context(cafile=str(ROOT/'fixture.crt'))
                client = http.client.HTTPSConnection('127.0.0.1',proxy,timeout=10,context=ctx)
                client.set_tunnel('127.0.0.1',target)
            else:
                client = http.client.HTTPConnection('127.0.0.1',proxy,timeout=10)
            try:
                rows.append({'measure':'persistentColdHead','scheme':scheme,'ms':head(proxy,target,scheme=='https',client)})
                for i in range(8):
                    rows.append({'measure':'warmHead','scheme':scheme,'ms':head(proxy,target,scheme=='https',client)})
            finally:
                client.close()
            for path in ['/ok','/close']:
                url = scheme+'://127.0.0.1:'+str(target)+path
                for i in range(6):
                    start = time.perf_counter_ns()
                    result = api(controller,'/proxies/FixedExit/delay?timeout=8000&expected=204&url='+urllib.parse.quote(url,safe=''))
                    total = (time.perf_counter_ns()-start)/1e6
                    state = api(controller,'/proxies/FixedExit')['extra'][url]
                    assert state['alive'] and state['history'][-1]['delay'] == result['delay']
                    rows.append({'measure':'unifiedDelay','scheme':scheme,'path':path,
                                 'ms':result['delay'],'totalMs':total})
        event('sampleComplete',variant=variant,round=round_id,pid=process.pid)
        return {'variant':variant,'round':round_id,'pid':process.pid,
                'configSha256':hashlib.sha256((directory/'config.json').read_bytes()).hexdigest(),'rows':rows}
    finally:
        process.terminate()
        process.wait(timeout=8)
        log.close()

def main():
    cert, key = ROOT/'fixture.crt',ROOT/'fixture.key'
    if not cert.exists():
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2',
          '-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1',
          '-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    http_s = http.server.ThreadingHTTPServer(('127.0.0.1',0),Probe)
    https_s = http.server.ThreadingHTTPServer(('127.0.0.1',0),Probe)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert,key)
    https_s.socket = ctx.wrap_socket(https_s.socket,server_side=True)
    hp, sp = serve(http_s),serve(https_s)
    exit_s = TCP(('127.0.0.1',0),Socks)
    exit_s.role='fixedExit';exit_s.allowed={hp,sp}; ep=serve(exit_s)
    entry_s = TCP(('127.0.0.1',0),Socks)
    entry_s.role='entry';entry_s.allowed={ep};np=serve(entry_s)
    samples = []
    try:
        for rid, order in enumerate([['app','clashEquivalent'],['clashEquivalent','app']]):
            for variant in order:
                current = sample(variant,np,ep,hp,sp,cert.read_text(),rid)
                samples.append(current)
                (ROOT/'partial-results.json').write_text(json.dumps(samples,indent=2)+'\n')
                print(variant, rid, 'completed',flush=True)
        summary={}
        for variant in ['app','clashEquivalent']:
            rows=[r for s in samples if s['variant']==variant for r in s['rows']]
            measures={}
            for r in rows:
                k = r['measure']+'-'+r['scheme']+('-'+r['path'] if 'path' in r else '')
                measures.setdefault(k,[]).append(r['ms'])
            summary[variant]={k:{'n':len(v),'medianMs':statistics.median(v),'minMs':min(v),'maxMs':max(v)} for k,v in measures.items()}
        assert not any(e['kind']=='socksConnect' and not e['permitted'] for e in EVENTS)
        assert all(e['host']=='127.0.0.1' for e in EVENTS if e['kind']=='socksConnect')
        counts={role:sum(e['kind']=='socksConnect' and e['role']==role for e in EVENTS) for role in ['entry','fixedExit']}
        assert counts['entry']==counts['fixedExit']
        result={'coreReceipt':json.loads((ROOT/'core-receipt.json').read_text()),
          'sourceTarSha256':hashlib.sha256((ROOT.parent.parent/'third-party/source/mihomo-v1.19.31.tar.gz').read_bytes()).hexdigest(),
          'method':'AB/BA same official Mihomo, same local authenticated two-hop SOCKS, same fixed exit, same targets, same artificial waits',
          'limits':['Linux loopback, not Android/device/provider throughput','No DNS workload: literal IP fixture endpoints','No actual Clash Verge GUI or browser engine','Controlled RTT adds waits per SOCKS reply and relay chunk, not packet-accurate WAN simulation'],
          'delaysMs':{'socksReply':HANDSHAKE_REPLY_WAIT*1000,'relayChunkOneWayPerHop':FORWARD_WAIT*1000,'httpResponse':HTTP_RESPONSE_WAIT*1000},
          'summary':summary,'routeConnectionCounts':counts,'samples':samples,'events':EVENTS}
        (ROOT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(summary,indent=2),flush=True)
    finally:
        for s in [entry_s,exit_s,http_s,https_s]:
            s.shutdown();s.server_close()

if __name__ == '__main__':
    main()
