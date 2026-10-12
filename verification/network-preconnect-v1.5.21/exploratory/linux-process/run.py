#!/usr/bin/env python3
import hashlib,json,os,pathlib,socket,ssl,statistics,subprocess,time,urllib.parse,urllib.request,uuid,traceback
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(__file__).resolve().parent
CORE=ROOT/'work/mihomo-build/bin/mihomo-linux-amd64';GO=ROOT/'work/mihomo-build/toolchain/go/bin/go'
PATCH='24f9b3a5db65265bc719107bc1eb79752c4e115e1babdfc79838237abc849ef9'
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
mono=time.perf_counter_ns

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def until(fn,seconds=5):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  result=fn()
  if result:return result
  time.sleep(.01)
 raise RuntimeError('bounded fixture condition timeout')
def header(s):
 data=b''
 while b'\r\n\r\n' not in data:
  b=s.recv(1)
  if not b:raise EOFError('header EOF')
  data+=b
  if len(data)>8192:raise RuntimeError('oversized header')
 return data
class Fixture:
 def __init__(self):
  self.log=open(OUT/'fixture-stderr.log','w');self.proc=subprocess.Popen(['python3','-u',str(OUT/'fixtures/serve.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
  self.ready=json.loads(self.proc.stdout.readline());assert self.ready['ready'] and self.ready['allDestinationsLoopback'];(OUT/'fixture-ready.json').write_text(json.dumps(self.ready,indent=2)+'\n')
 def snapshot(self):
  self.proc.stdin.write('{"action":"snapshot"}\n');self.proc.stdin.flush();return json.loads(self.proc.stdout.readline())['wireEvents']
 def stop(self):
  self.proc.stdin.write('{"action":"stop"}\n');self.proc.stdin.flush();self.proc.stdout.readline();self.proc.wait(timeout=3);self.log.close()
class Core:
 def __init__(self,fixture,name,enabled):
  self.name=name;self.enabled=enabled;self.root=OUT/name;self.root.mkdir();self.proxyPort=port();self.apiPort=port();self.epoch=self.root/'network.epoch';self.epoch.write_text('ready:'+uuid.uuid4().hex+'\n');os.chmod(self.epoch,0o600)
  nodes=fixture.ready['entries'];fixed=fixture.ready['fixedExit'];self.entry=nodes[0]['name'];self.exit=fixed
  proxies=[dict(n,type='socks5',server=n['host'],udp=False) for n in nodes]
  for n in proxies:n.pop('host')
  (self.root/'subscription.yaml').write_text(json.dumps({'proxies':proxies}))
  fixed=dict(fixed,type='socks5',server=fixed['host'],name='FixedExit',udp=False);fixed.pop('host');fixed.update({'dialer-proxy':'EntryChoice','pocket-preconnect':enabled,'pocket-preconnect-epoch-file':str(self.epoch)})
  config={'log-level':'warning','mode':'rule','ipv6':False,'tcp-concurrent':True,'external-controller':'127.0.0.1:'+str(self.apiPort),'secret':'fixture-control','allow-lan':False,'sniffer':{'enable':False},'tun':{'enable':False},'dns':{'enable':False},'tls':{'custom-certifactes':[fixture.ready['trustedFixtureCertificate']]},'proxy-providers':{'Subscription':{'type':'file','path':'subscription.yaml','override':{'additional-prefix':'Entry|'},'health-check':{'enable':False}}},'proxies':[fixed],'proxy-groups':[{'name':'EntryChoice','type':'select','use':['Subscription']}],'rules':['MATCH,REJECT'],'listeners':[{'name':'PocketOnly','type':'mixed','listen':'127.0.0.1','port':self.proxyPort,'udp':False,'proxy':'FixedExit'}]}
  (self.root/'config.json').write_text(json.dumps(config,indent=2)+'\n');self.log=open(self.root/'core.log','w');self.proc=subprocess.Popen([str(CORE),'-d',str(self.root),'-f',str(self.root/'config.json')],stdout=self.log,stderr=subprocess.STDOUT)
  def ready():
   if self.proc.poll()!=None:raise RuntimeError('core exited: '+(self.root/'core.log').read_text())
   try:return self.api('/version')
   except (OSError,urllib.error.URLError):return False
  self.version=until(ready)
  def selected():
   try:return self.api('/proxies/EntryChoice')
   except (OSError,urllib.error.URLError):return False
  try:self.selection=until(selected)
  except Exception:self.stop();raise
  assert self.selection['now']=='Entry|'+self.entry,(self.selection,self.root/'core.log')
  self.startupObservations=[]
  for index in range(10):
   selected=self.api('/proxies/EntryChoice');provider=self.api('/providers/proxies/Subscription');self.startupObservations.append({'atNs':mono(),'selection':selected['now'],'nodeCount':len(provider['proxies'])})
   assert selected['now']==self.selection['now'] and len(provider['proxies'])==2
   time.sleep(.05)
 def api(self,path):
  req=urllib.request.Request('http://127.0.0.1:'+str(self.apiPort)+path,headers={'Authorization':'Bearer fixture-control'})
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=10) as r:return json.load(r)
 def request(self,fixture):
  target=fixture.ready['target'];ctx=ssl.create_default_context(cadata=fixture.ready['trustedFixtureCertificate']);ctx.set_alpn_protocols(['http/1.1']);start=mono()
  with socket.create_connection(('127.0.0.1',self.proxyPort),5) as s:
   s.settimeout(5);s.sendall(('CONNECT '+target['host']+':'+str(target['port'])+' HTTP/1.1\r\nHost: '+target['host']+'\r\n\r\n').encode());proxyReady=header(s);assert proxyReady.startswith(b'HTTP/1.1 200'),proxyReady
   connectReady=mono()
   with ctx.wrap_socket(s,server_hostname=target['host']) as tls:
    tlsReady=mono();tls.sendall(('HEAD /probe HTTP/1.1\r\nHost: '+target['host']+'\r\nConnection: close\r\n\r\n').encode());response=header(tls);end=mono();assert response.startswith(b'HTTP/1.1 204'),response
    return {'startNs':start,'endNs':end,'durationMs':(end-start)/1e6,'proxyConnectMs':(connectReady-start)/1e6,'targetTlsMs':(tlsReady-connectReady)/1e6,'firstByteAfterTlsMs':(end-tlsReady)/1e6,'status':204,'alpn':tls.selected_alpn_protocol(),'tlsSessionReused':tls.session_reused}
 def stop(self):
  self.proc.terminate()
  try:self.proc.wait(timeout=3)
  except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=3)
  self.log.close()

def groups(rows):
 out={}
 for r in rows:out.setdefault(r['socket'],[]).append(r)
 return out
def phase(rows,key):return next((r for r in rows if r['phase']==key),None)
def ready_sockets(rows):return {k:r for k,r in groups(rows).items() if k.startswith('exit-') and phase(r,'auth-sent') and not phase(r,'connect-received') and not phase(r,'peer-eof')}
def bind_wire(fixture,before,after,result):
 before_ids={r['socket'] for r in before if r['phase']=='target-head-received'}
 targets=[(k,r) for k,r in groups(after).items() if k.startswith('target-') and phase(r,'target-head-received') and k not in before_ids];assert len(targets)==1,targets
 targetid,targetrows=targets[0];targetaccept=phase(targetrows,'accepted');exitrows=[(k,r) for k,r in groups(after).items() if k.startswith('exit-') and phase(r,'upstream-opened') and phase(r,'upstream-opened')['localPort']==targetaccept['peerPort']];assert len(exitrows)==1
 exitid,erows=exitrows[0];exitaccept=phase(erows,'accepted');entryrows=[(k,r) for k,r in groups(after).items() if k.startswith('entry') and phase(r,'upstream-opened') and phase(r,'upstream-opened')['localPort']==exitaccept['peerPort']];assert len(entryrows)==1
 entryid,arows=entryrows[0];assert phase(arows,'connect-received')['host']==fixture.ready['fixedExit']['host'] and phase(arows,'connect-received')['port']==fixture.ready['fixedExit']['port'];assert phase(erows,'connect-received')['host']==fixture.ready['target']['host'];assert phase(erows,'connect-received')['port']==fixture.ready['target']['port']
 # Fixture and runner clocks are same process-host monotonic clock; ready auth is
 # proven by the snapshot taken before the request, without guessing clock origins.
 preauth=exitid in ready_sockets(before)
 result.update({'entrySocket':entryid,'exitSocket':exitid,'targetSocket':targetid,'exitPreauthenticatedBeforeRequest':preauth,'targetConnectAbsentBeforeRequest':not any(r['socket']==exitid and r['phase']=='connect-received' for r in before),'sameFixedExit':True,'authToConnectDelayMs':(phase(erows,'connect-received')['atNs']-phase(erows,'auth-sent')['atNs'])/1e6,'preparationWireMs':(phase(erows,'auth-sent')['atNs']-phase(arows,'accepted')['atNs'])/1e6,'wirePhases':{'entry':arows,'exit':erows,'target':targetrows}})
 return result

def main():
 checks=[];out={'schema':1,'fullActualLinuxCoreProcess':True,'androidAcceptance':False,'wanClaim':False,'fixtureTransport':'two-authenticated-SOCKS5-hops','preparationIsRealNetworkWork':True,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'core':{'path':str(CORE.relative_to(ROOT)),'sha256':sha(CORE),'bytes':CORE.stat().st_size,'version':subprocess.check_output([str(CORE),'-v'],text=True).strip()},'checks':checks,'samples':[]}
 receipt=json.loads((ROOT/'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text());assert receipt['inputs']['patchSha256']==PATCH and sha(ROOT/receipt['inputs']['patch'])==PATCH and receipt['recipe']['fixedExitPreconnect'];out['nativeInputs']=receipt['inputs'];out['nativeRecipe']=receipt['recipe'];out['androidReceiptSha256']=sha(ROOT/'third-party/patches/mihomo-v1.19.31-probe-build.json')
 buildinfo=subprocess.check_output([str(GO),'version','-m',str(CORE)],text=True);(OUT/'actual-core-go-buildinfo.txt').write_text(buildinfo);assert 'go1.26.8' in buildinfo and 'GOOS=linux' in buildinfo and 'GOARCH=amd64' in buildinfo and '-tags=with_gvisor' in buildinfo
 for name in ['serve.py','benchmark.py']:assert sha(OUT/'fixtures'/name)==sha(ROOT/'work/exit-preauth-benchmark'/name)
 fixture=Fixture();cores=[]
 try:
  base=Core(fixture,'baseline-false',False);cores.append(base);candidate=Core(fixture,'production-true',True);cores.append(candidate);out['coreControllers']={c.name:{'version':c.version,'selection':c.selection,'configSha256':sha(c.root/'config.json'),'startupObservations':c.startupObservations} for c in cores}
  seedbefore=fixture.snapshot();assert not seedbefore;seed=candidate.request(fixture);seedafter=fixture.snapshot();out['seed']=bind_wire(fixture,seedbefore,seedafter,seed);assert not out['seed']['exitPreauthenticatedBeforeRequest'];checks.append('actual-parser-provider-prefix-selector-auto-close-first-cold')
  prepared=set()
  def ready():
   rows=fixture.snapshot();slots=ready_sockets(rows)
   if slots:time.sleep(.03);return fixture.snapshot()
  for pair in range(4):
   order=[base,candidate] if pair%2==0 else [candidate,base]
   for core in order:
    before=until(ready) if core.enabled else fixture.snapshot();result=core.request(fixture);after=fixture.snapshot();result=bind_wire(fixture,before,after,result);result.update(pair=pair,scenario=core.name);out['samples'].append(result);assert result['exitPreauthenticatedBeforeRequest']==core.enabled and result['targetConnectAbsentBeforeRequest'] and not result['tlsSessionReused'];prepared.add(result['exitSocket']) if core.enabled else None
  checks.extend(['four-paired-AB-BA-cold-target-TLS-HEAD','eight-new-target-TLS-sockets','single-use-preauthenticated-exit-sockets','same-fixed-exit-actual-entry-chain-no-direct-fallback','auth-only-before-target-connect'])
  before=until(ready);readyids=set(ready_sockets(before));assert len(readyids)==1
  delay=candidate.api('/proxies/FixedExit/delay?url='+urllib.parse.quote(fixture.ready['target']['url'],safe='')+'&timeout=5000');after=fixture.snapshot();out['urlTest']={'response':delay,'readySocketsBefore':sorted(readyids),'readySocketsAfter':sorted(ready_sockets(after)),'wireEventsBefore':len(before),'wireEventsAfter':len(after)};assert readyids==set(ready_sockets(after)),out['urlTest'];assert int(delay['probe']['firstMs'])>=180,delay;checks.append('actual-controller-URLTest-does-not-consume-or-refill')
  byscenario={name:[x['durationMs'] for x in out['samples'] if x['scenario']==name] for name in ['baseline-false','production-true']};out['summary']={name:{'count':len(vals),'p50Ms':statistics.median(vals),'minMs':min(vals),'maxMs':max(vals)} for name,vals in byscenario.items()};out['preparationSamplesMs']=[x['preparationWireMs'] for x in out['samples'] if x['scenario']=='production-true'];out['scope']='Actual full Linux core plus real loopback wire. Delays injected by fixture. Preparation moved ahead of demand; no WAN/Android/browser performance claim.';out['passed']=True
 except Exception:
  out['passed']=False;out['failure']=traceback.format_exc();raise
 finally:
  out['allWireEvents']=fixture.snapshot()
  for core in cores:core.stop()
  fixture.stop();(OUT/'results.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'passed':out['passed'],'checks':len(checks),'summary':out.get('summary'),'coreSha256':out['core']['sha256']}))
if __name__=='__main__':main()
