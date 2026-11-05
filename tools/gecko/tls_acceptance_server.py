"""Upstream-free product TLS peers; originals survive until post-cleanup freeze."""
import copy
import hashlib
import json
import re
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import parse_qs, urlsplit
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'browser'))
from native_tls_probe_server import peek_client_hello
from fingerprint_fixture_server import HOSTS,read_header

GUEST_PORT=18786
HOST=HOSTS[0]
CASE_SPECS=(
 ('default-tls12',1,'default',False,False,False,False,'TLSv1.2',True,False),
 ('strict-tls12',1,'tls13',False,False,False,False,'TLSv1.2',False,False),
 ('strict-tls13',1,'tls13',False,False,False,True,'TLSv1.3',True,False),
 ('pending-default-tls12',1,'tls13',False,False,False,True,'TLSv1.2',False,False),
 ('restored-default-tls12',1,'default',False,True,True,False,'TLSv1.2',True,False),
 ('rfp-strict-tls13',1,'tls13',True,False,False,False,'TLSv1.3',True,False),
 ('persistent-before',1,'tls13',False,False,False,False,'TLSv1.3',True,True),
 ('persistent-after',1,'tls13',False,True,False,False,'TLSv1.3',True,True),
 ('concurrent-strict-tls13',1,'tls13',False,False,False,False,'TLSv1.3',True,False),
 ('concurrent-default-tls12',2,'default',False,False,False,False,'TLSv1.2',True,False),
 ('concurrent-strict-resample-tls12',1,'tls13',False,False,False,True,'TLSv1.2',False,False))

def require(value,message):
    if not value:raise ValueError('Product TLS fixture: '+message)

def strict_json(raw,maximum=262144):
    require(type(raw) is bytes and 0<len(raw)<=maximum,'bounded original JSON')
    def pairs(rows):
        result={}
        for key,value in rows:
            require(key not in result,'duplicate key');result[key]=value
        return result
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    require(type(value) is dict,'JSON object');return value

def read_application_header(stream):
    # Exactly through the header; an allowed POST body remains unread.
    raw=bytearray()
    while not raw.endswith(b'\r\n\r\n'):
        chunk=stream.recv(1);require(chunk,'complete application header');raw+=chunk;require(len(raw)<=16384,'application header bound')
    rows=raw[:-4].decode('iso-8859-1').split('\r\n');parts=rows[0].split(' ')
    require(len(parts)==3 and parts[2] in ('HTTP/1.0','HTTP/1.1'),'application request line')
    headers={}
    for line in rows[1:]:
        require(':' in line and not line.startswith((' ','\t')),'application header shape');key,value=line.split(':',1);key=key.lower();value=value.strip()
        require(re.fullmatch('[a-z0-9-]+',key) and key not in headers and '\0' not in value and len(value)<=2048,'application duplicate/header bound');headers[key]=value
    require('transfer-encoding' not in headers,'chunked body unsupported')
    require(re.fullmatch('[0-9]{1,4}',headers.get('content-length','0')) and int(headers.get('content-length','0'))<=8192,'application body bound')
    require(parts[0]=='POST' or headers.get('content-length','0')=='0','GET body unsupported')
    return parts[0],parts[1],headers

class TlsAcceptanceServer:
    def __init__(self,certificates,run,source,page_script,worker_script):
        require(re.fullmatch('[0-9a-f]{32}',run) and re.fullmatch('[0-9a-f]{40}',source),'source/run binding')
        self.certificates,self.run,self.source=certificates,run,source
        self.page,self.worker=page_script,worker_script
        self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.socket.listen(24);self.socket.settimeout(.2)
        self.port=self.socket.getsockname()[1];self.lock=threading.RLock();self.closed=False
        self.threads=[];self.connections=set();self.records=[];self.records_bytes=0;self.overflow=False;self.joined=False
        self.cases={};self.peers={};self.epoch=0;self.controls=0;self.rejected=0
    def start(self):
        t=threading.Thread(target=self._accept,name='product-tls-listener',daemon=True);self.threads.append(t);t.start();return self
    def begin(self,label,case):
        spec=next((row for row in CASE_SPECS if row[0]==label),None)
        require(spec is not None and re.fullmatch('[0-9a-f]{32}',case),'known fresh workload')
        with self.lock:
            require(case not in self.cases,'case replay')
            self.epoch+=1
            if label=='persistent-after':
                before=next((row for row in self.cases.values() if row['label']=='persistent-before'),None);require(before is not None,'persistent origin missing');port=before['port']
            else:
                candidates=set(range(42000,62000))-set(self.peers)-{self.port,GUEST_PORT};port=secrets.choice(tuple(candidates))
            if port not in self.peers:
                context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);version=getattr(ssl.TLSVersion,spec[7].replace('.','_'))
                context.minimum_version=context.maximum_version=version;context.options|=ssl.OP_NO_TICKET;context.num_tickets=0
                context.set_alpn_protocols(['http/1.1']);context.load_cert_chain(self.certificates.leaf,self.certificates.directory/'leaf.key')
                self.peers[port]={'context':context,'version':spec[7],'slot':spec[1]}
            require(self.peers[port]['version']==spec[7] and self.peers[port]['slot']==spec[1],'persistent peer differs')
            binding=dict(label=label,caseNonce=case,slot=spec[1],port=port,epoch=self.epoch,service=spec[9],serverOnlyVersion=spec[7])
            self.cases[case]={**binding,'serviceObservation':None};return copy.deepcopy(binding)
    def _accept(self):
        while not self.closed:
            try:connection,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:return
            with self.lock:
                if self.closed:connection.close();return
                self.connections.add(connection);t=threading.Thread(target=self._serve,args=(connection,),daemon=True);self.threads.append(t);t.start()
    def _serve(self,connection):
        original=connection;record=None
        try:
            connection.settimeout(12);method,target,headers=read_header(connection)
            if method=='GET':
                path=urlsplit(target);query=parse_qs(path.query,strict_parsing=True)
                require(not path.scheme and not path.netloc and not path.fragment and headers.get('host')=='127.0.0.1:'+str(GUEST_PORT) and path.path=='/__tls_product_evidence' and set(query)=={'run','case'} and query['run']==[self.run] and len(query['case'])==1,'fixed control endpoint')
                case=query['case'][0]
                with self.lock:require(case in self.cases and self.controls<10000,'known bounded control case');self.controls+=1;raw=json.dumps(self.cases[case],sort_keys=True).encode()
                self._http(connection,'application/json',raw);return
            require(method=='CONNECT','CONNECT only')
            match=re.fullmatch(re.escape(HOST)+':([0-9]{4,5})',target);require(match is not None,'fixed origin only');port=int(match[1])
            with self.lock:require(port in self.peers,'registered peer only');peer=self.peers[port];epoch=self.epoch
            record=dict(schema=1,epoch=epoch,destinationPort=port,slot=peer['slot'],serverOnlyVersion=peer['version'],clientHello=None,tlsNegotiated=False,httpReceived=False)
            connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n');record['clientHello']=peek_client_hello(connection)
            wrapped=peer['context'].wrap_socket(connection,server_side=True);connection=wrapped
            with self.lock:self.connections.discard(original);self.connections.add(wrapped)
            record.update(tlsNegotiated=True,negotiatedVersion=wrapped.version(),negotiatedAlpn=wrapped.selected_alpn_protocol(),sessionReused=wrapped.session_reused)
            method,target,headers=read_application_header(wrapped);parsed=urlsplit(target)
            require(not parsed.scheme and not parsed.netloc and not parsed.fragment,'origin-form controlled application target')
            require(headers.get('host')==HOST+':'+str(port),'exact HTTP authority')
            prefix='/tls-product/slot'+str(peer['slot'])+'/'
            if method=='GET' and parsed.path==prefix+'service.js':
                require(not parsed.query,'stable worker script path');record.update(httpReceived=True,requestRole='service-script',caseNonce=None)
                self._http(wrapped,'application/javascript',self.worker.encode(),extra=b'Service-Worker-Allowed: '+prefix.encode()+b'\r\n');return
            query=parse_qs(parsed.query,strict_parsing=True);require(set(query)=={'run','case','source'} or set(query)=={'run','case','source','boot'},'exact workload query')
            require(query['run']==[self.run] and query['source']==[self.source] and len(query['case'])==1,'request source/run');case=query['case'][0]
            with self.lock:require(case in self.cases and self.cases[case]['port']==port,'case authority');binding=copy.deepcopy(self.cases[case])
            record.update(httpReceived=True,caseNonce=case)
            if method=='GET' and parsed.path==prefix+'page':
                require(set(query)=={'run','case','source'},'page query');record['requestRole']='page'
                config=dict(runNonce=self.run,caseNonce=case,sourceCommit=self.source,slot=peer['slot'],service=binding['service'])
                raw=('<!doctype html><meta charset=utf-8><link rel=icon href=data:,><title>TLS product:'+case+'</title><script>globalThis.__tlsProduct='+json.dumps(config,separators=(',',':'))+';\n'+self.page+'</script><p>Controlled product TLS workload</p>').encode()
                self._http(wrapped,'text/html',raw);return
            if method=='GET' and parsed.path==prefix+'sw-fetch':
                require(binding['service'] and set(query)=={'run','case','source','boot'} and len(query['boot'])==1 and re.fullmatch('[0-9a-f]{32}',query['boot'][0]),'actual worker fetch binding')
                record.update(requestRole='service-fetch',serviceBootNonce=query['boot'][0]);self._http(wrapped,'text/plain',case.encode());return
            require(method=='POST' and parsed.path==prefix+'service-report' and binding['service'] and set(query)=={'run','case','source'},'fixed POST packet')
            length=headers.get('content-length','');require(re.fullmatch('[0-9]{1,4}',length) and 0<int(length)<=8192,'bounded service packet')
            raw=b''
            while len(raw)<int(length):
                block=wrapped.recv(int(length)-len(raw));require(block,'complete service packet');raw+=block
            value=strict_json(raw,8192);required={'schema','runNonce','caseNonce','sourceCommit','slot','existingRegistration','controlledBeforeRegistration','scriptPath','scopePath','bootNonce','fetchNonceMatched'}
            require(set(value)==required and type(value['schema']) is int and value['schema']==1,'service packet schema')
            require(value['runNonce']==self.run and value['caseNonce']==case and value['sourceCommit']==self.source and type(value['slot']) is int and value['slot']==peer['slot'],'service packet identity')
            require(all(type(value[k]) is bool for k in ('existingRegistration','controlledBeforeRegistration','fetchNonceMatched')) and value['fetchNonceMatched'] is True,'actual registration/fetch metadata')
            require(value['scriptPath']==prefix+'service.js' and value['scopePath']==prefix and type(value['bootNonce']) is str and re.fullmatch('[0-9a-f]{32}',value['bootNonce']),'stable worker binding')
            with self.lock:
                old=self.cases[case]['serviceObservation'];require(old is None or old==value,'different service replay');self.cases[case]['serviceObservation']=value
            record['requestRole']='service-report';self._http(wrapped,'text/plain',b'ok')
        except ssl.SSLError as error:
            if record is not None:record.update(errorType='SSLError',tlsErrorReason=getattr(error,'reason','') if getattr(error,'reason','') in ('UNSUPPORTED_PROTOCOL','TLSV1_ALERT_PROTOCOL_VERSION','NO_SHARED_CIPHER','TLSV1_ALERT_UNKNOWN_CA','SSLV3_ALERT_CERTIFICATE_UNKNOWN') else 'OTHER_SSL_ERROR')
        except Exception as error:
            if record is not None:record.update(errorType=type(error).__name__)
            else:
                with self.lock:self.rejected+=1
        finally:
            try:connection.close()
            except OSError:pass
            with self.lock:
                self.connections.discard(original);self.connections.discard(connection)
                if record is not None:
                    size=len(json.dumps(record,separators=(',',':')).encode())
                    if len(self.records)>=96 or self.records_bytes+size>2*1024*1024:self.overflow=True
                    else:self.records_bytes+=size;record['sequence']=len(self.records)+1;self.records.append(record)
    @staticmethod
    def _http(connection,kind,raw,extra=b''):
        connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: '+kind.encode()+b'; charset=utf-8\r\nContent-Length: '+str(len(raw)).encode()+b'\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n'+extra+b'\r\n'+raw)
    def snapshot(self):
        with self.lock:return dict(schema=1,runNonce=self.run,sourceCommit=self.source,records=copy.deepcopy(self.records),cases={key:{k:copy.deepcopy(v) for k,v in row.items()} for key,row in self.cases.items()},recordsOverflow=self.overflow,controls=self.controls,rejectedRequests=self.rejected,upstreamConnections=0,forwardingImplemented=False,actualWireCapture=True,ticketsDisabled=True,privateMaterialExported=False,certificateExceptionUsed=False,serverClosed=self.closed,serverThreadsJoined=self.joined)
    def close(self):
        with self.lock:self.closed=True;connections=list(self.connections)
        self.socket.close()
        for connection in connections:
            try:connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:connection.close()
            except OSError:pass
        deadline=time.monotonic()+5
        for thread in list(self.threads):thread.join(max(0,deadline-time.monotonic()))
        with self.lock:self.joined=all(not thread.is_alive() for thread in self.threads) and not self.connections
        require(self.joined,'all actual server threads closed before final snapshot')
