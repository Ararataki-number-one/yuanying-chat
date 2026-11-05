"""Bounded loopback-only production CPU fixture; never forwards any request."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
from urllib.parse import parse_qs, urlsplit

GUEST_PORT=18766
HOST='fp-a.pocketchat.test'
ROLES=('page','dedicated','blob','shared','service')
ERRORS=('Unavailable','TimeoutError','WorkerError','InvalidReply')

def require(value,message):
    if not value:raise ValueError(message)

def strict_json(raw,limit=262144):
    require(type(raw) is bytes and len(raw)<=limit,'Bounded original JSON bytes required')
    def pairs(rows):
        result={}
        for key,value in rows:
            require(key not in result,'Duplicate JSON field');result[key]=value
        return result
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    require(type(value) is dict,'JSON object required');return value

class CpuAcceptanceServer:
    def __init__(self,page_script,worker_script,run_nonce,source,certificates=None):
        require(re.fullmatch('[0-9a-f]{32}',run_nonce) and re.fullmatch('[0-9a-f]{40}',source),'Exact fixture source/run binding required')
        self.certificates=certificates
        self.page=page_script;self.worker=worker_script;self.run=run_nonce;self.source=source
        self.lock=threading.Lock();self.cases={};self.events=[];self.requests=0;self.control_requests=0;self.rejected=0;self.tls_connections=0
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_CONNECT(self):
                if owner.certificates is None or self.path!=HOST+':443':
                    self.send_error(403);self.close_connection=True;return
                self.send_response(200,'Connection Established');self.end_headers();self.wfile.flush()
                self.connection=owner.certificates.context.wrap_socket(self.connection,server_side=True)
                with owner.lock:owner.tls_connections+=1
                self.rfile=self.connection.makefile('rb',-1);self.wfile=self.connection.makefile('wb',0)
                self.cpu_tls=True;self.close_connection=False
                self.handle_one_request();self.close_connection=True
            def do_GET(self):self.serve('GET')
            def do_POST(self):self.serve('POST')
            def serve(self,method):
                self.connection.settimeout(5)
                try:status,kind,raw=owner.response(method,self.path,self.headers,self.rfile,getattr(self,'cpu_tls',False))
                except Exception:status,kind,raw=400,'text/plain',b''
                self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff');self.send_header('Connection','close');self.end_headers();self.wfile.write(raw)
                self.close_connection=True
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.daemon_threads=True
        self.thread=threading.Thread(target=self.http.serve_forever,name='production-cpu-fixture',daemon=True)
    @property
    def port(self):return self.http.server_address[1]
    def start(self):self.thread.start();return self
    def close(self):self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
    def begin(self,slot,case_nonce):
        require(type(slot) is int and slot in (1,2) and re.fullmatch('[0-9a-f]{32}',case_nonce),'Bounded slot/case required')
        with self.lock:
            require(case_nonce not in self.cases,'Fresh case nonce required')
            self.cases[case_nonce]={'binding':dict(runNonce=self.run,caseNonce=case_nonce,sourceCommit=self.source,slot=slot),'roles':{}}
    def evidence(self,case_nonce):
        with self.lock:
            case=self.cases[case_nonce]
            return dict(schema=1,binding=copy.deepcopy(case['binding']),observations=[copy.deepcopy(case['roles'][r]) for r in ROLES if r in case['roles']])
    def snapshot(self):
        with self.lock:return dict(schema=1,requests=self.requests,controlRequests=self.control_requests,rejectedRequests=self.rejected,tlsConnections=self.tls_connections,upstreamConnections=0,forwardingImplemented=False,events=copy.deepcopy(self.events),eventsTruncated=self.requests>len(self.events),certificateExceptionUsed=False,trustMethod='domain-scoped-user-ca' if self.certificates else 'host-control-only',cases={nonce:dict(binding=copy.deepcopy(case['binding']),observations=[copy.deepcopy(case['roles'][role]) for role in ROLES if role in case['roles']]) for nonce,case in self.cases.items()})
    def response(self,method,target,headers,stream,secure=False):
        parsed=urlsplit(target);path=parsed.path
        with self.lock:
            if method=='GET' and path=='/__cpu-evidence':
                require(self.control_requests<100000,'Bounded control polling exceeded');self.control_requests+=1
            else:
                self.requests+=1
                if len(self.events)<512:self.events.append(dict(method=method,path=path if re.fullmatch('/cpu/slot[12]/(page|worker.js|service.js|report)',path) else 'other'))
        if (parsed.scheme and (parsed.scheme!='http' or parsed.netloc!='127.0.0.1:'+str(GUEST_PORT))) or parsed.fragment:
            with self.lock:self.rejected+=1
            return 403,'text/plain',b''
        if self.certificates is not None and path!='/__cpu-evidence':
            require(secure and headers.get('Host') in (HOST,HOST+':443'),'Actual controlled TLS origin required')
        query=parse_qs(parsed.query,keep_blank_values=True,strict_parsing=True)
        if method=='GET' and re.fullmatch('/cpu/slot[12]/(worker.js|service.js)',path):
            require(not query,'Persistent worker script must have a stable path')
            return 200,'application/javascript',self.worker.encode()
        require(set(query)=={'run','case'} and all(len(v)==1 for v in query.values()) and query['run'][0]==self.run,'Bound fixture query required')
        case_nonce=query['case'][0]
        with self.lock:
            require(case_nonce in self.cases,'Unknown fixture case');binding=dict(self.cases[case_nonce]['binding'])
        prefix='/cpu/slot'+str(binding['slot'])+'/'
        if method=='GET' and path=='/__cpu-evidence':return 200,'application/json',json.dumps(self.evidence(case_nonce),separators=(',',':')).encode()
        if method=='GET' and path==prefix+'page':
            config=json.dumps(binding,separators=(',',':'))
            raw='<!doctype html><meta charset=utf-8><title>CPU production first inline</title><script>globalThis.__cpuAcceptance='+config+';\n'+self.page+'</script><p>Controlled production CPU workload</p>'
            return 200,'text/html',raw.encode()
        require(method=='POST' and path==prefix+'report','Controlled route required')
        length=headers.get('Content-Length','');require(re.fullmatch('[0-9]{1,5}',length) and 0<int(length)<=8192,'Bound report length required')
        value=strict_json(stream.read(int(length)),8192)
        require(set(value)=={'schema','runNonce','caseNonce','sourceCommit','slot','role','status','observation','error','service'},'Exact role packet required')
        require(type(value['schema']) is int and value['schema']==1 and all(type(value[k]) is type(v) and value[k]==v for k,v in binding.items()),'Role source/run/case/slot differs')
        require(value['role'] in ROLES and value['status'] in ('observed','failed','unsupported'),'Unknown role outcome')
        if value['status']=='observed':
            row=value['observation'];require(type(row) is dict and set(row)=={'hardwareConcurrency','nativeGetter','firstInline','bootNonce'} and value['error'] is None,'Exact first-inline observation required')
            require(type(row['hardwareConcurrency']) is int and 1<=row['hardwareConcurrency']<=65536 and type(row['nativeGetter']) is bool and row['firstInline'] is True and re.fullmatch('[0-9a-f]{32}',row['bootNonce']),'Typed first-inline native sample required')
        else:require(value['observation'] is None and value['error'] in ERRORS,'Bound role failure required')
        service=value['service']
        if value['role']=='service' and value['status']=='observed':
            require(type(service) is dict and set(service)=={'existingRegistration','controlledBeforeRegistration','scriptPath','scopePath'} and type(service['existingRegistration']) is bool and type(service['controlledBeforeRegistration']) is bool and service['scriptPath']==prefix+'service.js' and service['scopePath']==prefix,'Bound persistent service worker required')
        else:require(service is None,'Unexpected service worker metadata')
        with self.lock:
            require(value['role'] not in self.cases[case_nonce]['roles'],'Role replay rejected')
            self.cases[case_nonce]['roles'][value['role']]=value
        return 200,'text/plain',b'ok'
