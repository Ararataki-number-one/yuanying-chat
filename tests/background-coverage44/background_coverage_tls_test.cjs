'use strict';
// Real trusted loopback TLS receiver. No browser, Shared Worker or SW is executed.
const test=require('node:test'),assert=require('node:assert/strict'),https=require('node:https'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const {createIdentityService,DEFAULT_BASE}=require('../../tools/fingerprint/request_identity_server.cjs');
test('worker coverage declarations cannot add detector request paths',async t=>{
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'background-coverage44-tls-'));
  const key=path.join(temp,'key.pem'),cert=path.join(temp,'cert.pem');
  cp.execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',key,'-out',cert],{stdio:'ignore'});
  const service=createIdentityService({key:fs.readFileSync(key),cert:fs.readFileSync(cert)});
  await new Promise(resolve=>service.server.listen(0,'127.0.0.1',resolve));
  const port=service.server.address().port,nonce=()=>crypto.randomBytes(16).toString('hex');
  const get=(operation,id,extra='')=>new Promise((resolve,reject)=>{
    const req=https.get({hostname:'127.0.0.1',port,path:DEFAULT_BASE+operation+'?nonce='+id+extra,ca:fs.readFileSync(cert),agent:false},res=>{
      let bytes=0;const parts=[];res.on('data',chunk=>{bytes+=chunk.byteLength;if(bytes>65536){res.destroy(Error('test response too large'));return;}parts.push(chunk);});
      res.on('error',reject);res.on('end',()=>{const text=Buffer.concat(parts).toString('utf8');let body;try{body=JSON.parse(text);}catch{}resolve({status:res.statusCode,headers:res.headers,body,text,authorized:res.socket?.authorized});});
    });req.on('error',reject);
  });
  try{
    await t.test('optional declarations are false without changing legacy capabilities',async()=>{
      const id=nonce(),r=await get('capabilities',id);
      assert.equal(r.status,200);assert.deepEqual(r.body.backgroundCoverage,{sharedWorker:false,serviceWorker:false});
      assert.deepEqual(r.body.capabilities,{topLevelDocument:true,dedicatedWorker:true,boundedWorkerReply:true,crossOriginFrame:false,crossOriginFrameReceiver:false});
      assert.equal(service.log.events.length,0);assert.equal(service.snapshot(id).createdAt,0);assert.equal(r.headers['service-worker-allowed'],undefined);
    });
    await t.test('unknown worker and registration paths are still outside the protocol',async()=>{
      const before=service.log.events.length;
      for(const operation of ['shared-worker.js','service-worker.js','sw.js','shared.js','register','unregister','cache'])assert.equal((await get(operation,nonce())).status,404);
      assert.equal(service.log.events.length,before);
    });
    await t.test('a forged source tag cannot become shared or service worker evidence',async()=>{
      const id=nonce();assert.equal((await get('document',id)).status,200);
      const before=service.log.events.length;
      for(const source of ['shared-worker','service-worker','shared-worker-fetch','service-worker-fetch'])assert.equal((await get('observe',id,'&source='+source)).status,400);
      assert.equal(service.log.events.length,before);
      const result=await get('result',id);assert.equal(result.status,202);assert.equal(result.body.status,'pending');
      assert.equal(result.body.events.some(x=>/shared|service/.test(x.source)),false);
    });
  }finally{service.server.closeAllConnections?.();await new Promise(resolve=>service.server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
});
