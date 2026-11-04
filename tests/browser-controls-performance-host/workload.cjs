/* Actual production assets in JSDOM. DOM/read counters, never frame timings. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const assets=process.argv[2],optimized=process.argv[3]==='optimized';
const driver=fs.readFileSync(assets+'/page-driver.js','utf8');
const performanceSource=fs.readFileSync(assets+'/web-performance.js','utf8');
const replySource=fs.readFileSync(assets+'/web-reply-observer.js','utf8');
const checks=[];
function check(name,condition){assert.ok(condition,name);checks.push(name);}
function fixture(extra='',install=true){
  const w=new JSDOM('<!doctype html><body><form><textarea id="prompt-textarea">keep unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button><div id="upload-zone"></div></form><button data-testid="model-switcher-dropdown-button" aria-label="Model selector">GPT</button><main><article data-message-author-role="user" data-message-id="u1"><div data-user-message-bubble>bound prompt</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="a1"><div class="markdown"><p id="answer">original answer</p></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section></main><aside id="controls">'+extra+'</aside></body>',{url:'https://chatgpt.com/c/controls',runScripts:'outside-only'}).window;
  const counters={documentControlQueries:0,documentControlNodes:0,scopedControlQueries:0,scopedControlNodes:0,controlLabelReads:0,controlTextReads:0};
  const isControlList=s=>s==='button,[role="button"]'||s==='button[aria-label],[role="button"][aria-label]';
  const attribute=w.Element.prototype.getAttribute;
  const isControl=e=>e.tagName==='BUTTON'||attribute.call(e,'role')==='button';
  w.Element.prototype.getAttribute=function(name){if(name==='aria-label'&&isControl(this))counters.controlLabelReads++;return attribute.call(this,name);};
  for(const [prototype,kind]of [[w.Document.prototype,'document'],[w.Element.prototype,'scoped']]){
    const query=prototype.querySelectorAll;
    prototype.querySelectorAll=function(selector){const result=query.call(this,selector);if(isControlList(selector)){counters[kind+'ControlQueries']++;counters[kind+'ControlNodes']+=result.length;}return result;};
  }
  // Explicit geometry/innerText adapters. They model ancestor/descendant CSS
  // changes for parity controls; this does not execute a browser layout engine.
  const hidden=e=>e.closest('[hidden],.css-hidden,[style*="display: none"]');
  const text=n=>n.nodeType===w.Node.TEXT_NODE?n.nodeValue:n.nodeType!==w.Node.ELEMENT_NODE||hidden(n)?'':[...n.childNodes].map(text).join('');
  Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){if(isControl(this))counters.controlTextReads++;return text(this);}});
  w.Element.prototype.getClientRects=function(){return hidden(this)?[]:[{}];};
  w.getComputedStyle=e=>({display:hidden(e)?'none':'block',visibility:e.closest('.invisible')?'hidden':'visible'});
  w.Date.now=()=>1700000000000;
  w.document.cookie='session=preserved;path=/';
  let sends=0,fetches=0;
  w.document.addEventListener('click',()=>sends++);
  w.fetch=()=>{fetches++;throw new Error('observation must not fetch');};
  w.eval(performanceSource);
  const call=(action,arg={})=>w.eval(driver.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
  if(install)call('web-transcript');
  const args={kind:'web',confirmed:true,userKey:'id:u1',prompt:'bound prompt',confirmedUrl:w.location.href,expectedUrl:w.location.href,export:true,lightObservation:true,incrementalObservation:install};
  const inspect=()=>call('web-inspect');
  const poll=()=>call('poll',args);
  const settle=async()=>{await Promise.resolve();await Promise.resolve();};
  const reset=()=>{for(const key of Object.keys(counters))counters[key]=0;};
  const stop=()=>{const node=w.document.createElement('button');node.setAttribute('aria-label','Stop');w.document.body.append(node);return node;};
  const noEffects=()=>sends===0&&fetches===0&&w.document.cookie==='session=preserved'&&w.document.querySelector('textarea').value==='keep unsent draft';
  return {w,call,args,inspect,poll,settle,reset,counters,stop,noEffects,close:()=>w.close()};
}
const summary=row=>({busy:row.busy,error:row.error||'',terminal:!!row.terminal,submitted:!!row.submitted,thinking:!!row.thinking,searching:!!row.searching,hasReply:!!row.hasReply,contentObserved:row.contentObserved!==false});
async function workload(){
  const f=fixture(Array.from({length:600},(_,i)=>'<button aria-label="'+(i%2?'Copy response':'Rename chat')+'">historical action '+i+'</button>').join(''));
  try{
    f.stop();await f.settle();f.inspect();f.poll();f.reset();
    const before=f.w.__pocketWebPerformance.stats(),outputs=[];
    for(let index=0;index<40;index++){
      const paragraph=f.w.document.getElementById('answer');
      if(index%2)paragraph.firstChild.appendData(' streamed');
      else {const span=f.w.document.createElement('span');span.textContent=' streamed';paragraph.append(span);}
      f.w.document.dispatchEvent(new f.w.Event(index%2?'scroll':'input'));
      await f.settle();
      outputs.push(summary(f.inspect()),summary(f.poll()));
    }
    const after=f.w.__pocketWebPerformance.stats();
    check('Streaming and gestures retain exact busy/reply observation',outputs.every(row=>row.busy&&row.error===''&&(!row.submitted||!row.contentObserved)));
    check('Read-only workload preserves the draft/cookie and never sends or fetches',f.noEffects());
    if(optimized){
      check('Forty streamed updates rebuild no page-wide control collection',after.controlListsBuilt===before.controlListsBuilt);
      check('Forty streamed updates rebuild no attribute candidate group',after.controlGroupsBuilt===before.controlGroupsBuilt);
      check('Steady polls enumerate no whole-page button NodeList',f.counters.documentControlQueries===0&&f.counters.documentControlNodes===0);
      check('Steady polls inspect fewer than 1000 control labels',f.counters.controlLabelReads<1000);
    }
    return {updates:40,historicalControls:600,counters:{...f.counters},outputs};
  }finally{f.close();}
}
async function sameTaskControls(install){
  const f=fixture('',install),observations=[];
  function busy(name,expected){const row=f.inspect();check(name,row.busy===expected);observations.push({name,busy:row.busy});}
  try{
    busy('Initial page has no stop control',false);
    const control=f.stop();busy('Same-task stop insertion is visible before mutation delivery',true);
    control.remove();busy('Same-task stop removal clears busy before mutation delivery',false);
    const wrapper=f.w.document.createElement('div');wrapper.innerHTML='<span role="button" aria-label="Stop">icon</span>';f.w.document.body.append(wrapper);
    busy('Inserted nested role-button is discovered',true);
    wrapper.firstChild.setAttribute('role','link');busy('Changing role removes non-button membership immediately',false);
    wrapper.firstChild.setAttribute('role','button');busy('Changing role adds button membership immediately',true);
    wrapper.remove();busy('Removing a whole wrapper expires detached control references',false);
    control.setAttribute('aria-label','Copy');f.w.document.body.append(control);busy('Ordinary aria-labelled button remains idle',false);
    control.setAttribute('aria-label','  sToP  ');busy('Whitespace and case variants of aria-label stay supported',true);
    control.setAttribute('aria-label','停止生成');busy('Localized aria-label change is immediately observed',true);
    control.setAttribute('aria-label','Copy');control.setAttribute('data-testid','stop-button');busy('Test-id stop remains authoritative despite another label',true);
    control.removeAttribute('data-testid');busy('Removing test-id restores the live label result',false);
    control.removeAttribute('aria-label');control.innerHTML='<span>Stop</span>';busy('Text-only controls remain live candidates',true);
    control.firstChild.firstChild.nodeValue='Copy';busy('Text-only character data changes are observed in the same task',false);
    control.innerHTML='<span class="css-hidden">Stop</span><span>Copy</span>';busy('Hidden descendant text cannot be mistaken for Stop',false);
    control.firstChild.className='';control.lastChild.className='css-hidden';busy('Descendant CSS changes can reveal Stop without changing text',true);
    control.className='css-hidden';busy('Ancestor CSS hiding is checked fresh',false);
    control.className='';control.setAttribute('inert','');busy('Busy retains rendered control semantics when inert',true);
    control.removeAttribute('inert');control.setAttribute('aria-hidden','true');busy('Aria-hidden visibility change clears busy immediately',false);
    control.removeAttribute('aria-hidden');busy('Aria-hidden removal restores busy immediately',true);
    control.style.display='none';busy('Inline style visibility is checked without candidate invalidation',false);
    control.style.display='';busy('Inline style removal restores busy immediately',true);
    control.innerHTML='<svg><title>Stop</title></svg>';busy('Changing matching SVG descendant text stays live',true);
    control.querySelector('title').textContent='Copy';busy('Nonmatching SVG descendant text clears busy',false);
    control.setAttribute('title','Stop');busy('Title alone does not change the original Stop matching semantics',false);
    control.setAttribute('aria-label',' ');control.textContent='Stop';busy('Nonempty whitespace aria-label continues to suppress text fallback',false);
    control.remove();
    const section=f.w.document.querySelector('section');
    section.insertAdjacentHTML('beforeend','<div id="retry-context"><span>Something went wrong</span><button aria-label="Retry">Retry</button></div>');
    const retry=f.w.document.querySelector('#retry-context button');
    let row=f.poll();check('Same-task retry insertion reports current response error',!!row.error);observations.push({name:'retry-insert',error:row.error});
    retry.setAttribute('aria-label','Copy');row=f.poll();check('Same-task retry relabelling clears response error',row.error==='');
    retry.removeAttribute('aria-label');retry.textContent='Try again';row=f.poll();check('Text-only retry is evaluated live',!!row.error);
    retry.textContent='Copy';row=f.poll();check('Text-only retry mutation clears response error',row.error==='');
    retry.textContent='Retry';f.w.document.getElementById('retry-context').firstChild.textContent='Everything is ready';row=f.poll();check('Retry context is reevaluated without control membership changes',row.error==='');
    f.w.document.getElementById('retry-context').remove();
    row=f.poll();check('Actual response completion remains immediate with current-turn actions',row.terminal&&!row.busy&&row.contentObserved!==false&&row.markdown==='original answer');
    check('Same-task control changes preserve draft/cookie and perform no page action',f.noEffects());
    return observations;
  }finally{f.close();}
}
async function resourcesAndDrain(){
  const f=fixture();
  try{
    const posts=[];f.w.PocketWebReply={postMessage:packet=>posts.push(JSON.parse(packet))};
    f.w.eval(replySource);f.call('observe-install',{resourceBinding:'binding-0000000001'});
    const sample=()=>{assert.equal(f.w.__pocketWebReplyObserver.requestResources('resource-guard-00001'),true);return posts.at(-1);};
    let row=sample();check('Initial resource state is read from the actual upload/resource APIs',!row.busy&&!row.uploading);
    const stop=f.stop();stop.setAttribute('data-testid','stop-button');
    f.w.document.getElementById('upload-zone').setAttribute('data-upload-state','uploading');row=sample();
    check('Same-task resource and upload starts remain immediately detectable',row.busy&&row.uploading);
    stop.remove();f.w.document.getElementById('upload-zone').removeAttribute('data-upload-state');row=sample();
    check('Same-task resource and upload ends remain immediately detectable',!row.busy&&!row.uploading);
    f.inspect();f.w.document.getElementById('answer').textContent='new final answer';f.inspect();
    if(!optimized)await f.settle(); // Prior source has no synchronous drain.
    const final=f.poll();check(optimized?'Draining candidate records also invalidates final-body transcript memos':'Prior observer delivery invalidates final-body transcript memos',final.markdown==='new final answer');
    const delta=f.call('web-transcript');check('Candidate reads retain the transcript update',delta.changes.some(entry=>entry.id==='id:a1'&&entry.text==='new final answer'));
    delete f.w.__pocketWebPerformance.controlCandidates;
    check('An already installed older helper safely falls back to live control queries',f.inspect().busy===false);
    const legacyStop=f.stop();check('The older-helper fallback observes newly inserted Stop controls',f.inspect().busy===true);legacyStop.remove();
    check('Resource/drain checks preserve draft/cookie and perform no page action',f.noEffects());
    return {busyTransitions:[false,true,false],uploadTransitions:[false,true,false],finalMarkdown:final.markdown};
  }finally{f.close();}
}
(async()=>{
  const measured=await workload();
  const controls=await sameTaskControls(true),fallback=await sameTaskControls(false);
  const resources=await resourcesAndDrain();
  console.log(JSON.stringify({status:'passed',passed:checks.length,checks,measured,controls,fallback,resources,scope:'Actual unmodified production assets in JSDOM with explicit innerText/geometry adapters; deterministic DOM/query counters, not elapsed time, Gecko, Android, FPS or real website measurements'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
