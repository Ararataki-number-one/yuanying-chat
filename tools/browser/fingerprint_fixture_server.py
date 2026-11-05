#!/usr/bin/env python3
"""Bounded synthetic loopback proxy; TLS private material lives only in host /tmp."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from urllib.parse import parse_qs,urlsplit

HOSTS=('fp-a.pocketchat.test','fp-b.pocketchat.test')
GUEST_PORT=18765
HEADER_LIMIT=16384
HEADERS=('user-agent','sec-ch-ua','sec-ch-ua-mobile','sec-ch-ua-platform','sec-ch-ua-platform-version','sec-ch-ua-model','sec-ch-ua-arch','sec-ch-ua-bitness','sec-ch-ua-full-version-list')
PATHS=('/document','/frame','/hints','/worker.js','/favicon.ico')


def require(value,message):
    if not value:raise ValueError('Synthetic TLS fixture: '+message)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def openssl(*args):
    # Never include tool stdout/stderr (or key material) in exceptions or reports.
    result=subprocess.run(['openssl',*map(str,args)],capture_output=True,timeout=30)
    require(result.returncode==0,'OpenSSL public-certificate operation failed')
    return result.stdout


class EphemeralCertificates:
    """No key bytes leave this class's /tmp directory; cleanup runs on all paths."""
    def __init__(self):
        self._directory=tempfile.TemporaryDirectory(prefix='pocketchat-fingerprint-tls-',dir='/tmp')
        self.directory=Path(self._directory.name)
        os.chmod(self.directory,0o700)
        try:
            ca_key=self.directory/'ca.key';leaf_key=self.directory/'leaf.key'
            self.ca=self.directory/'ca.pem';self.leaf=self.directory/'leaf.pem'
            csr=self.directory/'leaf.csr';extension=self.directory/'leaf.ext'
            openssl('req','-x509','-newkey','rsa:2048','-nodes','-days','2','-sha256','-subj','/CN=Ephemeral PocketChat controlled test CA','-keyout',ca_key,'-out',self.ca,'-addext','basicConstraints=critical,CA:TRUE,pathlen:0','-addext','keyUsage=critical,keyCertSign,cRLSign')
            openssl('req','-new','-newkey','rsa:2048','-nodes','-subj','/CN='+HOSTS[0],'-keyout',leaf_key,'-out',csr)
            extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:'+HOSTS[0]+',DNS:'+HOSTS[1]+'\n')
            openssl('x509','-req','-in',csr,'-CA',self.ca,'-CAkey',ca_key,'-CAcreateserial','-days','2','-sha256','-extfile',extension,'-out',self.leaf)
            for path in self.directory.iterdir():os.chmod(path,0o600)
            self.ca_bytes=self.ca.read_bytes();leaf_pem=self.leaf.read_text('ascii')
            self.leaf_sha=digest(ssl.PEM_cert_to_DER_cert(leaf_pem));self.ca_sha=digest(self.ca_bytes)
            self.subject_hash=openssl('x509','-in',self.ca,'-subject_hash_old','-noout').decode('ascii').strip()
            require(re.fullmatch('[0-9a-f]{8}',self.subject_hash),'public CA subject hash invalid')
            for host in HOSTS:openssl('verify','-CAfile',self.ca,'-verify_hostname',host,self.leaf)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.leaf,leaf_key);self.context=context
            self.public=dict(caPemSha256=self.ca_sha,leafDerSha256=self.leaf_sha,subjectHashOld=self.subject_hash,opensslChainVerified=True,hostnameVerified=list(HOSTS),ephemeral=True,privateMaterialLocation='host-tmp-only',privateMaterialExported=False,certificateExceptionUsed=False)
        except BaseException:self.close();raise

    def close(self):self._directory.cleanup()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def read_header(stream):
    """Consume exactly through CRLFCRLF, preserving the following TLS ClientHello."""
    data=bytearray()
    while not data.endswith(b'\r\n\r\n'):
        value=stream.recv(1)
        if not value:raise ValueError('Incomplete synthetic request')
        data+=value
        if len(data)>HEADER_LIMIT:raise ValueError('Synthetic header exceeds bound')
    text=data.decode('iso-8859-1');lines=text[:-4].split('\r\n');parts=lines[0].split(' ')
    require(len(parts)==3 and parts[2] in ('HTTP/1.0','HTTP/1.1'),'request line invalid')
    headers={}
    for line in lines[1:]:
        require(':' in line and not line.startswith((' ','\t')),'header invalid')
        name,value=line.split(':',1);name=name.lower();value=value.strip()
        require(re.fullmatch('[a-z0-9-]+',name) and name not in headers and '\x00' not in value,'header duplicate or invalid')
        require(len(value)<=2048,'header value exceeds bound');headers[name]=value
    require('transfer-encoding' not in headers and headers.get('content-length','0')=='0','request body unsupported')
    return parts[0],parts[1],headers


class FingerprintServer:
    def __init__(self,certificates,script,binding):
        require(set(binding)=={'sourceCommit','sourceTree','runNonce','integrationApkSha256','sdkRunId','sdkRunAttempt'},'exact invocation binding required')
        require(re.fullmatch('[0-9a-f]{40}',binding['sourceCommit']) and re.fullmatch('[0-9a-f]{40}',binding['sourceTree']) and re.fullmatch('[0-9a-f]{32}',binding['runNonce']) and re.fullmatch('[0-9a-f]{64}',binding['integrationApkSha256']),'source/APK/invocation identity invalid')
        require(type(script) is str and 0<len(script)<=32768 and '</script' not in script.lower(),'first-inline script invalid')
        self.certificates=certificates;self.script=script;self.binding=dict(binding)
        self._lock=threading.Lock();self._gate=threading.BoundedSemaphore(12);self._clients=set();self._threads=set();self._closed=threading.Event();self.engine=None
        self.rows={engine:dict(accepted=0,rejected=0,tlsConnections=0,requests=[]) for engine in ('chromium','gecko')}
        self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.socket.listen(16);self.socket.settimeout(.2)
        self.port=self.socket.getsockname()[1];self.thread=threading.Thread(target=self._accept,daemon=True)

    def start(self):self.thread.start();return self
    def begin(self,engine):
        require(engine in self.rows,'unknown engine')
        until=time.monotonic()+5
        while True:
            with self._lock:
                if not self._clients:
                    self.engine=engine;self.rows[engine]=dict(accepted=0,rejected=0,tlsConnections=0,requests=[]);return
            require(time.monotonic()<until,'previous engine still has active synthetic connections');time.sleep(.02)

    def snapshot(self,engine):
        require(engine in self.rows,'unknown evidence engine')
        with self._lock:result=json.loads(json.dumps(self.rows[engine]))
        result.update(schema=1,engine=engine,binding=self.binding,upstreamConnections=0,forwardingImplemented=False,certificateExceptionUsed=False,trustMethod='domain-scoped-user-ca',caPemSha256=self.certificates.ca_sha,leafDerSha256=self.certificates.leaf_sha)
        return result

    def _accept(self):
        while not self._closed.is_set():
            try:connection,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:return
            if not self._gate.acquire(blocking=False):connection.close();continue
            with self._lock:self._clients.add(connection);engine=self.engine
            thread=threading.Thread(target=self._serve,args=(connection,engine),daemon=True)
            with self._lock:self._threads.add(thread)
            thread.start()

    def _serve(self,connection,engine):
        try:
            connection.settimeout(15);method,target,headers=read_header(connection)
            if method=='GET' and target.startswith('/__evidence?'):
                require(headers.get('host')=='127.0.0.1:'+str(GUEST_PORT),'control authority differs')
                query=urlsplit(target);parameters=parse_qs(query.query,strict_parsing=True)
                require(query.path=='/__evidence' and set(parameters)=={'engine','nonce','source'} and all(len(v)==1 for v in parameters.values()),'control query invalid')
                require(parameters['nonce']==[self.binding['runNonce']] and parameters['source']==[self.binding['sourceCommit']] and parameters['engine']==[engine],'control invocation differs')
                self._send(connection,'application/json',json.dumps(self.snapshot(engine),separators=(',',':')).encode());return
            require(engine in self.rows,'engine not started')
            secure=False
            if method=='CONNECT':
                require(target in tuple(host+':443' for host in HOSTS),'CONNECT target outside synthetic hosts')
                host=target[:-4];require(headers.get('host') in (host,host+':443'),'CONNECT authority differs')
                connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                wrapped=self.certificates.context.wrap_socket(connection,server_side=True)
                with self._lock:self._clients.discard(connection);self._clients.add(wrapped);self.rows[engine]['tlsConnections']+=1
                connection=wrapped;secure=True;method,target,headers=read_header(connection)
                require(target.startswith('/') and not target.startswith('//'),'TLS target must be origin form')
            else:
                uri=urlsplit(target);require(uri.scheme=='http' and uri.hostname in HOSTS and uri.port in (None,80) and not uri.username and not uri.password and not uri.fragment,'HTTP target outside synthetic hosts');host=uri.hostname
            self._respond(connection,engine,host,secure,method,target,headers)
        except (ValueError,OSError,ssl.SSLError,UnicodeError):
            if engine in self.rows:
                with self._lock:self.rows[engine]['rejected']+=1
        finally:
            with self._lock:self._clients.discard(connection);self._threads.discard(threading.current_thread())
            with contextlib.suppress(OSError):connection.close()
            self._gate.release()

    def _respond(self,connection,engine,host,secure,method,target,headers):
        require(method=='GET','only synthetic GET permitted');uri=urlsplit(target)
        require(uri.path in PATHS and not uri.fragment,'target outside synthetic paths')
        require(headers.get('host') in (host,host+(':443' if secure else ':80')),'HTTP authority differs')
        scheme='https' if secure else 'http';origin=scheme+'://'+host
        observed=dict(origin=origin,path=uri.path,tls=secure,method='GET');observed.update({key:headers[key] for key in HEADERS if key in headers})
        with self._lock:
            row=self.rows[engine];require(len(row['requests'])<200,'request receipt bound exceeded');row['requests'].append(observed);row['accepted']+=1
        if uri.path=='/hints':kind='application/json';body=b'{"synthetic":true}'
        elif uri.path=='/worker.js':kind='text/javascript';body=b"postMessage({documentGuard:globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')]===true,auditAvailable:typeof globalThis.__pocketchatChromiumFingerprintObserve==='function'});"
        elif uri.path=='/favicon.ico':kind='image/x-icon';body=b''
        else:
            frames="<iframe src='"+origin+"/frame'></iframe><iframe src='"+scheme+'://'+(HOSTS[1] if host==HOSTS[0] else HOSTS[0])+"/frame'></iframe>" if uri.path=='/document' else ''
            kind='text/html; charset=UTF-8';body=("<!doctype html><html><head><script>"+self.script+"</script><meta name='viewport' content='width=device-width,initial-scale=1'><title>Fingerprint fixture</title></head><body><h1>Synthetic fingerprint fixture</h1>"+frames+'</body></html>').encode()
        self._send(connection,kind,body)

    @staticmethod
    def _send(connection,kind,body):
        header='HTTP/1.1 200 OK\r\nContent-Type: '+kind+'\r\nContent-Length: '+str(len(body))+'\r\nCache-Control: no-store\r\nAccept-CH: Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version, Sec-CH-UA-Model, Sec-CH-UA-Arch, Sec-CH-UA-Bitness, Sec-CH-UA-Full-Version-List\r\nConnection: close\r\n\r\n'
        connection.sendall(header.encode('ascii')+body)

    def close(self):
        self._closed.set();self.socket.close()
        if self.thread.is_alive():self.thread.join(2)
        with self._lock:clients=list(self._clients);threads=list(self._threads)
        for connection in clients:
            with contextlib.suppress(OSError):connection.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):connection.close()
        for thread in threads:thread.join(2)


class AndroidUserCa:
    """Only PUBLIC CA bytes cross adb; no system/APEX writes or permissive TLS."""
    def __init__(self,adb,certificates):self.adb=adb;self.certificates=certificates;self.path=None;self.receipt={};self.root_requested=False
    def set_root(self,root):
        self.adb('root' if root else 'unroot');self.adb('wait-for-device',timeout=60)
        uid=self.adb('shell','id','-u').stdout.decode().strip()
        require(uid==('0' if root else '2000'),'adb root unavailable' if root else 'shell evidence UID 2000 unavailable')
        return int(uid)
    def install(self):
        a=self.adb;c=self.certificates
        require(a('shell','getprop','ro.kernel.qemu').stdout.decode().strip()=='1','controlled emulator required')
        self.root_requested=True;self.set_root(True)
        require(a('shell','am','get-current-user').stdout.decode().strip()=='0','primary Android user required')
        require(a('shell','getenforce').stdout.decode().strip()=='Enforcing','SELinux enforcing required')
        store='/data/misc/user/0/cacerts-added';path=store+'/'+c.subject_hash+'.0'
        require(a('shell','test','-e',path,check=False).returncode==1,'CA filename collision or store access failure')
        a('shell','mkdir','-p',store);a('shell','chown','system:system',store);a('shell','chmod','0755',store)
        self.path=path
        a('push',str(c.ca),path);a('shell','chown','system:system',path);a('shell','chmod','0644',path);a('shell','restorecon','-RF',store)
        require(a('exec-out','cat',path).stdout==c.ca_bytes,'installed PUBLIC CA bytes differ')
        mode=a('shell','stat','-c','%a:%u:%g',path).stdout.decode().strip();require(mode=='644:1000:1000','CA owner or permissions differ')
        label=a('shell','ls','-Zd',path).stdout.decode().strip().split()[0];require(re.fullmatch(r'u:object_r:(?!unlabeled)[a-zA-Z0-9_]+:s0',label),'CA SELinux label missing')
        require(not a('shell','restorecon','-n','-v',path).stdout.strip(),'CA SELinux label not restored')
        a('shell','am','force-stop','local.pocketchat.test')
        evidence_uid=self.set_root(False)
        self.receipt=dict(method='domain-scoped-user-ca',androidUser=0,adbRoot=True,selinuxEnforcing=True,installedPublicCaBytesMatch=True,ownerAndMode=mode,selinuxContext=label,storePath=path,subjectHashOld=c.subject_hash,appForceStoppedAfterInstall=True,publicCaPemSha256=c.ca_sha,expectedLeafDerSha256=c.leaf_sha,evidenceShellUid=evidence_uid,shellRestoredAfterInstall=True,removedAfterExecution=False)
        return self.receipt

    def remove(self):
        if self.path is None:
            if self.root_requested:self.set_root(False);self.root_requested=False
            return
        try:
            cleanup_uid=self.set_root(True)
            # Delete only this invocation's exact PUBLIC certificate, never a preexisting CA.
            existing=self.adb('exec-out','cat',self.path,check=False)
            if existing.returncode==0:
                require(existing.stdout==self.certificates.ca_bytes,'CA changed before cleanup; refusing removal')
                self.adb('shell','rm',self.path)
            require(self.adb('shell','test','-e',self.path,check=False).returncode==1,'ephemeral PUBLIC CA cleanup failed')
            self.receipt['removedAfterExecution']=True;self.receipt['cleanupRootUid']=cleanup_uid;self.path=None
        finally:
            self.receipt['cleanupShellUid']=self.set_root(False);self.receipt['shellRestoredAfterCleanup']=True;self.root_requested=False
