/* Complete production scripts in JSDOM; deterministic DOM operations, no FPS. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=process.argv[2],optimized=process.argv[3]==='current';
const driver=fs.readFileSync(source+'/page-driver.js','utf8');
const performanceSource=fs.readFileSync(source+'/web-performance.js','utf8');
const observerSource=fs.readFileSync(source+'/web-reply-observer.js','utf8');
const checks=[];
function check(name,value){assert.ok(value,name);checks.push(name);}
const user=(id,text='question')=>'<article data-message-author-role="user"'+(id?' data-message-id="'+id+'"':'')+'><div data-user-message-bubble>'+text+'</div></article>';
const assistant=(id,text='answer')=>'<section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="'+id+'"><div class="markdown"><p>'+text+'</p><pre><code class="language-js">const value = 1;</code></pre></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section>';
function fixture(html){
  const w=new JSDOM('<!doctype html><body><form><textarea id="prompt-textarea">preserve unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button><div id="upload-zone"></div></form><main>'+html+'</main></body>',{url:'https://chatgpt.com/c/order',runScripts:'outside-only'}).window;
  Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
  w.Element.prototype.getClientRects=function(){return this.closest('[hidden],[aria-hidden="true"]')?[]:[{}];};
  w.Element.prototype.getBoundingClientRect=()=>({width:100,height:24,left:0,top:0,bottom:24});
  w.getComputedStyle=()=>({display:'block',visibility:'visible'});
  let comparisons=0,sends=0,fetches=0;
  const compare=w.Node.prototype.compareDocumentPosition;
  w.Node.prototype.compareDocumentPosition=function(...args){comparisons++;return compare.apply(this,args);};
  w.document.addEventListener('click',()=>sends++);
  w.fetch=()=>{fetches++;throw new Error('unexpected fetch');};
  w.document.cookie='session=preserved;path=/';w.eval(performanceSource);
  const call=(action,arg={})=>w.eval(driver.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
  const settle=async()=>{await Promise.resolve();await Promise.resolve();};
  let state=null;
  // The baseline observer delivers at its original microtask boundary. Current
  // reads occur immediately, proving the new cache cannot hide pending moves.
  const snapshot=async()=>{if(!optimized)await settle();const next=call('web-transcript',state?{documentId:state.documentId,revision:state.revision}:{});state=next;const copy=JSON.parse(JSON.stringify(next));delete copy.documentId;return copy;};
  return {w,call,snapshot,settle,comparisons:()=>comparisons,reset:()=>{comparisons=0;},stats:()=>w.__pocketWebPerformance.stats(),
    noEffects:()=>sends===0&&fetches===0&&w.document.cookie==='session=preserved'&&w.document.querySelector('textarea').value==='preserve unsent draft',
    close:()=>w.close()};
}
async function measured(){
  const f=fixture(Array.from({length:600},(_,i)=>user('u'+i,'question '+i)+assistant('a'+i,'answer '+i)).join(''));
  try{
    await f.snapshot();const before=f.stats();f.reset();const outputs=[];
    for(let index=0;index<20;index++){
      f.w.document.querySelector('[data-message-id="a599"] p').firstChild.appendData(' streamed '+index);
      f.w.document.dispatchEvent(new f.w.Event(index%2?'scroll':'input'));
      await f.settle();outputs.push(await f.snapshot());
    }
    const after=f.stats();
    check('Each streamed snapshot still rebuilds exactly its changed reply',after.entriesBuilt-before.entriesBuilt===20);
    check('Each snapshot preserves the current reply identity and full streamed body',outputs.every((row,i)=>row.changes.length===1&&row.changes[0].id==='id:a599'&&row.changes[0].text.includes(' streamed '+i)));
    check('Streaming leaves page content, draft, cookie and zero-action invariants intact',f.noEffects());
    if(optimized){
      check('Twenty streamed snapshots reuse the merged message-order collection',after.messageListsBuilt===before.messageListsBuilt);
      check('Twenty streamed snapshots perform no DOM order comparison',f.comparisons()===0);
    }
    return {messages:1200,streamedUpdates:20,compareDocumentPosition:f.comparisons(),entriesBuilt:after.entriesBuilt-before.entriesBuilt,
      messageListsBuilt:after.messageListsBuilt-before.messageListsBuilt,outputs};
  }finally{f.close();}
}
async function topology(){
  const f=fixture(user('u0','first question')+assistant('a0','first answer')+user('u1','bound question')+assistant('a1','latest answer'));
  const outputs=[];
  async function capture(name,mutation,expectSort=true){
    const before=f.stats().messageListsBuilt;mutation();f.reset();const row=await f.snapshot();check(name+' produces a complete valid delta',row.ok&&Array.isArray(row.changes));
    if(optimized)check(name+' invalidates only the required order cache',expectSort?f.stats().messageListsBuilt>before:f.stats().messageListsBuilt===before);
    outputs.push({name,result:row});return row;
  }
  try{
    outputs.push({name:'initial',result:await f.snapshot()});
    await capture('Streaming text',()=>{f.w.document.querySelector('[data-message-id="a1"] p').textContent='changed reply';},false);
    await capture('Code language attribute',()=>{f.w.document.querySelector('[data-message-id="a1"] code').className='language-python';},false);
    await capture('Stable message identity attribute',()=>{f.w.document.querySelector('[data-message-id="a1"]').setAttribute('data-message-id','a1-renamed');},false);
    await capture('New sibling file',()=>{f.w.document.querySelectorAll('section')[1].insertAdjacentHTML('beforeend','<a id="result-file" download="result.csv" href="https://chatgpt.com/backend-api/files/result">result.csv</a>');},false);
    await capture('Sibling filename attribute',()=>{f.w.document.getElementById('result-file').setAttribute('download','renamed.csv');},false);
    await capture('Move existing user turn',()=>{f.w.document.querySelector('main').append(f.w.document.querySelector('[data-message-id="u0"]'));});
    await capture('Move nested assistant wrapper',()=>{f.w.document.querySelector('main').prepend(f.w.document.querySelectorAll('section')[1]);});
    await capture('Insert nested message wrapper',()=>{f.w.document.querySelector('main').insertAdjacentHTML('beforeend','<div id="nested">'+user('u-nested','nested question')+assistant('a-nested','nested answer')+'</div>');});
    await capture('Change author role',()=>{f.w.document.querySelector('[data-message-id="u-nested"]').setAttribute('data-message-author-role','assistant');});
    await capture('Remove author role',()=>{f.w.document.querySelector('[data-message-id="u-nested"]').removeAttribute('data-message-author-role');});
    await capture('Article data-turn membership',()=>{f.w.document.getElementById('nested').insertAdjacentHTML('beforeend','<article id="turn-member" data-turn="user" data-message-id="turn-id">turn member</article>');});
    await capture('Change article data-turn',()=>{f.w.document.getElementById('turn-member').setAttribute('data-turn','assistant');});
    await capture('Search-unit membership',()=>{f.w.document.getElementById('nested').insertAdjacentHTML('beforeend','<div id="search-member" data-chatgpt-search-unit-key="search:user">search member</div>');});
    await capture('Change search-unit role',()=>{f.w.document.getElementById('search-member').setAttribute('data-chatgpt-search-unit-key','search:assistant');});
    await capture('Content-search membership',()=>{f.w.document.getElementById('nested').insertAdjacentHTML('beforeend','<div id="content-member" data-content-search-unit-key="content:user">content member</div>');});
    await capture('Remove content-search role',()=>{f.w.document.getElementById('content-member').removeAttribute('data-content-search-unit-key');});
    await capture('Nested same-role wrapper deduplication',()=>{const wrap=f.w.document.createElement('article');wrap.setAttribute('data-message-author-role','assistant');wrap.setAttribute('data-message-id','outer-id');const child=f.w.document.querySelector('[data-message-id="a-nested"]');child.replaceWith(wrap);wrap.append(child);});
    await capture('Remove nested owner wrapper',()=>{const wrap=f.w.document.querySelector('[data-message-id="outer-id"]');wrap.replaceWith(wrap.firstElementChild);});
    await capture('Position-derived identity insertion',()=>{f.w.document.querySelector('main').insertAdjacentHTML('afterbegin',user('','position question'));});
    await capture('Position-derived identity reindexing',()=>{f.w.document.querySelector('main').insertAdjacentHTML('afterbegin',user('u-before-position','inserted before position question'));});
    await capture('Position-derived message reorder',()=>{const position=[...f.w.document.querySelectorAll('[data-message-author-role="user"]')].find(node=>!node.hasAttribute('data-message-id'));f.w.document.querySelector('main').append(position);});
    await capture('Malformed dual-role preserves original multiplicity',()=>{f.w.document.querySelector('main').insertAdjacentHTML('beforeend','<article data-message-author-role="user" data-turn="assistant" data-message-id="dual">dual-role content</article>');});
    const duplicate=outputs.at(-1).result.order.filter(id=>id==='id:dual');check('Dual-role node retains both original merged-array occurrences',duplicate.length===2);
    const detached=f.w.document.getElementById('nested');
    await capture('Virtualized wrapper removal',()=>detached.remove());
    detached.querySelector('[data-message-id="a-nested"] p').textContent='edited while detached';
    await capture('Reinsert detached edited wrapper',()=>f.w.document.querySelector('main').append(detached));
    await capture('Same-task detach edit and reinsert',()=>{const section=f.w.document.querySelector('[data-message-id="a0"]').closest('section');section.remove();section.querySelector('p').textContent='detached in one task';f.w.document.querySelector('main').append(section);});
    await capture('Fragment batch move',()=>{const fragment=f.w.document.createDocumentFragment();fragment.append(f.w.document.querySelector('[data-message-id="u0"]'),f.w.document.querySelector('[data-message-id="u1"]'));f.w.document.querySelector('main').prepend(fragment);});
    await capture('Hydration replacing same stable identities',()=>{f.w.document.querySelector('main').innerHTML=user('u1','bound question')+assistant('a1','hydrated answer');});
    check('All same-task topology operations retain draft/cookie and perform no page action',f.noEffects());
    return outputs;
  }finally{f.close();}
}
async function runtimeAndFallback(){
  const f=fixture(user('u1','bound question')+assistant('a1','complete answer'));
  const observations=[];
  try{
    await f.snapshot();
    const args={kind:'web',confirmed:true,userKey:'id:u1',prompt:'bound question',confirmedUrl:f.w.location.href,expectedUrl:f.w.location.href,export:true,lightObservation:true,incrementalObservation:true};
    let result=f.call('poll',args);check('Current-turn completion is still observed',result.terminal&&!result.busy&&result.contentObserved&&result.markdown.includes('complete answer'));
    const posts=[];f.w.PocketWebReply={postMessage:packet=>posts.push(JSON.parse(packet))};f.w.eval(observerSource);f.call('observe-install',{resourceBinding:'binding-0000000001'});
    const resources=()=>{f.w.__pocketWebReplyObserver.requestResources('resource-order-test01');return posts.at(-1);};
    const stop=f.w.document.createElement('button');stop.setAttribute('data-testid','stop-button');stop.setAttribute('aria-label','Stop');f.w.document.body.append(stop);
    f.w.document.getElementById('upload-zone').setAttribute('data-upload-state','uploading');result=resources();check('Resource and upload start remain immediate',result.busy&&result.uploading);
    stop.remove();f.w.document.getElementById('upload-zone').removeAttribute('data-upload-state');result=resources();check('Resource and upload completion remain immediate',!result.busy&&!result.uploading);
    const context=f.w.document.createElement('div');context.innerHTML='<span>Browser app server websocket closed</span><button aria-label="Retry">Retry</button>';f.w.document.querySelector('section').append(context);
    if(!optimized)await f.settle();result=f.call('poll',args);check('Current retry/socket error remains immediate',result.websiteSocketClosed&&result.errorCode==='website_socket_closed');
    observations.push({error:result.error,errorCode:result.errorCode,websiteSocketClosed:result.websiteSocketClosed});
    context.firstChild.textContent='Everything is ready';result=f.call('poll',args);check('Retry context remains live',result.error==='');context.remove();
    f.w.document.querySelector('[data-user-message-bubble]').textContent='edited bound question';if(!optimized)await f.settle();result=f.call('poll',args);check('Editing the bound question still invalidates ownership',result.bindingLost===true);
    observations.push({bindingLost:result.bindingLost,error:result.error});
    delete f.w.__pocketWebPerformance.orderedMessageNodes;f.reset();await f.snapshot();
    check('An older installed helper falls back to the original sort',f.comparisons()>0);
    delete f.w.__pocketWebPerformance;f.reset();result=f.call('transcript');check('An absent performance helper retains the original transcript path',result.ok&&result.entries.length===2&&f.comparisons()>0);
    check('Completion/errors/upload/fallback checks preserve draft/cookie and zero page actions',f.noEffects());
    return observations;
  }finally{f.close();}
}
(async()=>{
  const measuredResult=await measured(),topologyResult=await topology(),runtime=await runtimeAndFallback();
  console.log(JSON.stringify({status:'passed',passed:checks.length,checks,measured:measuredResult,topology:topologyResult,runtime,
    scope:'Complete unchanged production scripts in JSDOM with explicit innerText/geometry adapters; baseline permits original observer microtask, current exercises same-task topology reads. DOM operations only, no Gecko/Android/frame timing.'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
