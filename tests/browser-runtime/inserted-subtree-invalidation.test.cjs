/* Production cache ownership in real JSDOM mutation deliveries; not Android FPS. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'app/src/main/assets/web-performance.js'),'utf8'),driver=fs.readFileSync(path.join(root,'app/src/main/assets/page-driver.js'),'utf8');
const baseline=process.env.WEB_PERFORMANCE_BASELINE?fs.readFileSync(process.env.WEB_PERFORMANCE_BASELINE,'utf8'):null;
const digest=value=>crypto.createHash('sha256').update(typeof value==='string'?value:JSON.stringify(value)).digest('hex');
const reports=[];
const settle=async()=>{await Promise.resolve();await Promise.resolve();};
function fixture(code){
 const w=new JSDOM('<!doctype html><body><main><article id="user" data-message-author-role="user" data-message-id="u"><div data-user-message-bubble>original question</div></article><section id="turn" data-turn="assistant"><div id="answer" data-message-author-role="assistant" data-message-id="a"><div id="body" class="markdown"><p>original cached answer</p></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section></main><div id="scratch"></div><div id="other"></div><textarea id="prompt-textarea">unsent original draft</textarea><button data-testid="send-button" aria-label="Send">Send</button></body>',{url:'https://chatgpt.com/c/original',runScripts:'outside-only'}).window;
 Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});w.Element.prototype.getClientRects=()=>[{}];w.getComputedStyle=()=>({display:'block',visibility:'visible'});w.Date.now=()=>10000;
 const idle=new Map(),cache=new Map(),observers=[];let id=0,sends=0,walkers=0,nodes=0;
 w.requestIdleCallback=(fn,options)=>{const token=++id;idle.set(token,{fn,options});return token;};w.cancelIdleCallback=token=>idle.delete(token);
 const NativeWeakMap=w.WeakMap;w.WeakMap=class extends NativeWeakMap{set(node,value){cache.set(node,value);return super.set(node,value);}};
 const NativeObserver=w.MutationObserver;w.MutationObserver=class extends NativeObserver{constructor(fn){super(fn);observers.push(this);}};
 const create=w.document.createTreeWalker.bind(w.document);w.document.createTreeWalker=(...args)=>{walkers++;nodes++;const value=create(...args),next=value.nextNode.bind(value);value.nextNode=()=>{const node=next();if(node)nodes++;return node;};return value;};
 w.document.cookie='session=preserved;path=/';w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);w.eval(code);
 const call=(action,arg={})=>w.eval(driver.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
 const first=call('web-transcript'),args={kind:'web',confirmed:true,userKey:'id:u',prompt:'original question',confirmedUrl:w.location.href,expectedUrl:w.location.href,export:true,lightObservation:true,incrementalObservation:true};
 const complete=call('poll',args);assert.equal(complete.contentObserved,true);
 const known={...args,knownReplyKey:complete.replyKey,knownReplyContentRevision:complete.replyContentRevision};
 const states=()=>[...cache].map(([node,value])=>({node:node.id||node.getAttribute('data-message-id'),identity:value.identity,version:value.version,dirty:value.dirty})).sort((a,b)=>a.node.localeCompare(b.node));
 const flushIdle=()=>{const jobs=[...idle.values()];idle.clear();for(const job of jobs){assert.equal(job.options.timeout,750);job.fn({didTimeout:false,timeRemaining:()=>10});}};
 return {w,call,first,args,known,states,flushIdle,perf:()=>w.__pocketWebPerformance,reset(){walkers=nodes=0;},counts:()=>({walkers,nodes}),close(){observers.forEach(x=>x.disconnect());idle.clear();w.close();},invariants(){assert.equal(sends,0);assert.equal(w.document.querySelector('textarea').value,'unsent original draft');assert.match(w.document.cookie,/session=preserved/);}};
}

async function scenario(kind,code){
 const f=fixture(code),{w}=f,doc=w.document,body=doc.getElementById('body'),turn=doc.getElementById('turn');let before,immediate,extra={},maxWalkers=1,measuredCounts=null;
 try{
  if(kind==='cached-nonselector-in-ineligible-wrapper'||kind==='disjoint-cached-scopes'){
   const first=doc.createElement('div');first.id='plain';first.textContent='old plain';doc.body.append(first);await settle();assert.equal(f.perf().memo(first,'plain',()=>first.textContent),'old plain');first.remove();await settle();first.textContent='fresh plain';
   let second=null;
   if(kind==='disjoint-cached-scopes'){second=doc.createElement('div');second.id='plain-second';second.textContent='old second';doc.body.append(second);await settle();f.perf().memo(second,'plain',()=>second.textContent);second.remove();await settle();second.textContent='fresh second';maxWalkers=2;}
   before=f.states();f.reset();const wrapper=doc.createElement('div');wrapper.id='ineligible';doc.body.append(wrapper);wrapper.append(first);if(second)doc.body.append(second);await settle();immediate=f.states();
   extra.probe=f.perf().memo(first,'plain',()=>first.textContent);assert.equal(extra.probe,'fresh plain');
   if(second){extra.second=f.perf().memo(second,'plain',()=>second.textContent);assert.equal(extra.second,'fresh second');}
  }else if(kind==='navigation-and-new-content-version'){
   doc.dispatchEvent(new w.Event('scroll'));body.querySelector('p').append(' deferred candidate');await settle();const queued=f.call('poll',f.known);assert.equal(queued.captureDeferred,true);
   body.remove();await settle();body.querySelector('p').textContent='fresh detached navigation version';before=f.states();f.reset();
   const wrapper=doc.createElement('div');wrapper.id='navigation-wrapper';doc.getElementById('answer').append(wrapper);wrapper.append(body);w.history.replaceState({},'','/c/other');await settle();immediate=f.states();
   const prepared=f.perf().stats().capturesPrepared;f.flushIdle();assert.equal(f.perf().stats().capturesPrepared,prepared);extra.foreign=f.call('poll',f.known);assert.equal(extra.foreign.bindingLost,true);assert.equal(extra.foreign.submitted,false);
   const foreignSnapshot=f.call('web-transcript',{documentId:f.first.documentId,revision:f.first.revision});assert.equal(foreignSnapshot.reset,true);extra.foreignSnapshot={reset:foreignSnapshot.reset,url:foreignSnapshot.url};
   w.history.replaceState({},'','/c/original');const pending=f.call('poll',f.known);assert.equal(pending.captureDeferred,true);f.flushIdle();const complete=f.call('poll',f.known);assert.ok(complete.markdown.includes('fresh detached navigation version'));extra.returned=complete.markdown;
  }else{
   turn.remove();await settle();body.querySelector('p').textContent='fresh detached '+kind;before=f.states();f.reset();
   if(kind==='same-object-added-repeatedly'){
    doc.getElementById('scratch').append(turn);doc.getElementById('other').append(turn);doc.querySelector('main').append(turn);
   }else if(kind==='remove-reinsert-same-delivery'){
    const wrapper=doc.createElement('div');wrapper.id='remove-reinsert-wrapper';doc.body.append(wrapper);wrapper.append(turn);turn.remove();wrapper.append(turn);
   }else if(kind==='detached-added-root'){
    const wrapper=doc.createElement('div');wrapper.id='detached-wrapper';wrapper.append(turn);doc.body.append(wrapper);wrapper.remove();
   }else{
    const wrapper=doc.createElement('div');wrapper.id='history-wrapper';
    if(kind==='descendant-before-ancestor')doc.getElementById('scratch').append(turn);
    doc.body.append(wrapper);wrapper.append(turn);
   }
   await settle();immediate=f.states();
   if(kind==='detached-added-root'){
    measuredCounts=f.counts(); // Count this delivery; the later reattach is another batch.
    extra.detachedText=f.perf().memo(body,'markdown',()=>body.textContent);assert.ok(extra.detachedText.includes('fresh detached '+kind));
    const wrapper=turn.parentElement;doc.body.append(wrapper);await settle();
   }
  }
  const counts=measuredCounts||f.counts();
  // Finish outside active reading for these cache-only cases. The dedicated
  // navigation case above exercises the real driver's queued ownership guard.
  const final=f.call('poll',f.args);if(final.captureDeferred)f.flushIdle();const complete=f.call('poll',f.args);
  if(!kind.includes('plain')&&!kind.includes('nonselector')&&kind!=='disjoint-cached-scopes'&&kind!=='navigation-and-new-content-version')assert.ok(complete.markdown.includes('fresh detached '+kind));
  const snapshot=f.call('web-transcript');f.invariants();
  const invalidated=immediate.filter(item=>item.version!==before.find(old=>old.node===item.node)?.version).map(item=>({node:item.node,from:before.find(old=>old.node===item.node)?.version,to:item.version}));
  // The native bridge transports JSON, not JSDOM window-specific Array prototypes.
  const entries=JSON.parse(JSON.stringify(snapshot.changes.map(x=>({id:x.id,role:x.role,text:x.text,downloads:x.downloads}))));
  return {semantic:{before,immediate,invalidated,finalCache:f.states(),entries,poll:{submitted:complete.submitted,bindingLost:complete.bindingLost||false,terminal:complete.terminal,hasFiles:complete.hasFiles,markdown:complete.markdown},extra:{...extra,foreign:extra.foreign?{bindingLost:extra.foreign.bindingLost,submitted:extra.foreign.submitted}:undefined}},counts,maxWalkers};
 }finally{f.close();}
}

for(const kind of ['ancestor-before-descendant','descendant-before-ancestor','same-object-added-repeatedly','remove-reinsert-same-delivery','cached-nonselector-in-ineligible-wrapper','disjoint-cached-scopes','detached-added-root','navigation-and-new-content-version']){
 test('Inserted subtree ownership: '+kind,async t=>{
  const current=await scenario(kind,source);assert.ok(current.counts.walkers<=current.maxWalkers,kind+' expires each maximal eligible subtree once');
  let before=null;if(baseline){before=await scenario(kind,baseline);assert.deepEqual(current.semantic,before.semantic,'Output, exact invalidated identities/versions and resulting cached values match original production');}
  const row={kind,semanticSha256:digest(current.semantic),baselineSemanticSha256:before?digest(before.semantic):null,semantic:current.semantic,currentCounts:current.counts,baselineCounts:before?.counts||null,exactPairedSemantics:!!before};reports.push(row);t.diagnostic(JSON.stringify({kind,semanticSha256:row.semanticSha256,currentCounts:row.currentCounts,baselineCounts:row.baselineCounts,exactPairedSemantics:row.exactPairedSemantics}));
 });
}
test.after(()=>{if(process.env.SUBTREE_REPORT){fs.mkdirSync(path.dirname(process.env.SUBTREE_REPORT),{recursive:true});fs.writeFileSync(process.env.SUBTREE_REPORT,JSON.stringify({schema:1,scope:'Actual production cache/driver in controlled DOM; no Android timing claim',sourceSha256:digest(source),baselineSha256:baseline?digest(baseline):null,cases:reports},null,2)+'\n');}});
