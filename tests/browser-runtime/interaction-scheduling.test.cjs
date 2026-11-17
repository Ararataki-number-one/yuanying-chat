/* Production observation with controlled idle/geometry. No Android frame-rate claim. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync('app/src/main/assets/page-driver.js','utf8'),perf=fs.readFileSync('app/src/main/assets/web-performance.js','utf8'),observer=fs.readFileSync('app/src/main/assets/web-reply-observer.js','utf8'),content=fs.readFileSync('app/src/main/assets/gecko/content.js','utf8');
const checks=[],check=(name,ok)=>{assert.ok(ok,name);checks.push({name,pass:true});};
const settle=async()=>{await Promise.resolve();await Promise.resolve();};
function fixture(html){const w=new JSDOM('<!doctype html><body>'+html+'</body>',{url:'https://chatgpt.com/c/interaction-fixture',runScripts:'outside-only',pretendToBeVisual:true}).window;const observers=[],NativeObserver=w.MutationObserver;w.MutationObserver=class extends NativeObserver{constructor(callback){super(callback);observers.push(this);}};w.__dispose=()=>{for(const item of observers)item.disconnect();w.close();};Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});w.Element.prototype.getClientRects=()=>[{}];w.getComputedStyle=()=>({display:'block',visibility:'visible'});return w;}
/* Result-prewarm scheduling was removed with native reply detection. Verify
 * that the same formerly-racing DOM situations now schedule no result work. */
async function retiredResultControls(){
 const rows=[];
 for(const kind of ['unchanged','later-user','bound-user-removed','earlier-history-user','other-route','detached-body','body-changed','sidebar-class']){
  const w=fixture('<main><article id="user" data-message-author-role="user" data-message-id="u1"><div data-user-message-bubble>original question</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="a1"><div id="answer" class="markdown"><p>'+('measured response '.repeat(8000))+'</p><pre><code class="language-js">const original = 1;</code></pre></div></div><a download="original.csv" href="/backend-api/files/original">original.csv</a></section></main><textarea id="prompt-textarea">preserved unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button><aside id="sidebar"></aside>');
  const idle=new Map();let sends=0,fetches=0;
  w.requestIdleCallback=(callback,options)=>{idle.set(1,{callback,options});return 1;};w.cancelIdleCallback=id=>idle.delete(id);
  w.document.cookie='session=preserved;path=/';w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);w.fetch=()=>{fetches++;throw new Error('Unexpected network request');};w.eval(perf);
  const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg))),stats=()=>w.__pocketWebPerformance.stats();
  try{
   const first=call('web-transcript'),body=w.document.getElementById('answer'),user=w.document.getElementById('user');
   w.document.dispatchEvent(new w.Event('scroll'));body.querySelector('p').append(' final suffix');await settle();
   const newUser='<article data-message-author-role="user" data-message-id="u2"><div data-user-message-bubble>new question</div></article>';
   if(kind==='later-user')w.document.querySelector('main').insertAdjacentHTML('beforeend',newUser);
   if(kind==='earlier-history-user')w.document.querySelector('main').insertAdjacentHTML('afterbegin',newUser);
   if(kind==='bound-user-removed')user.remove();
   if(kind==='other-route')w.history.replaceState({},'','/c/other');
   if(kind==='detached-body')body.remove();
   if(kind==='body-changed')body.querySelector('p').append(' newest suffix');
   if(kind==='sidebar-class')w.document.getElementById('sidebar').className='unrelated';
   await settle();const before=stats(),disabled=call('poll',{confirmed:true,userKey:'id:u1',knownReplyKey:'id:a1',expectedUrl:'https://chatgpt.com/c/interaction-fixture'}),after=stats();
   const noWork=idle.size===0&&after.derivedBuilt===before.derivedBuilt&&after.capturesPrepared===before.capturesPrepared&&after.capturesScheduled===before.capturesScheduled;
   check('Retired result command schedules no body preparation after '+kind,disabled.ok===false&&disabled.reason==='请在 ChatGPT 原网页中操作'&&noWork);
   const snapshot=call('web-transcript',{documentId:first.documentId,revision:first.revision}),entry=snapshot.changes.find(row=>row.id==='id:a1');
   if(kind==='detached-body')assert.ok(!entry||!entry.text.includes(' final suffix'));else assert.ok(entry&&entry.text.includes(' final suffix')&&entry.downloads.some(file=>file.name==='original.csv'));
   assert.ok(sends===0&&fetches===0&&w.document.cookie==='session=preserved'&&w.document.querySelector('textarea').value==='preserved unsent draft');
   rows.push({kind,noResultWork:noWork,zeroSend:true,zeroFetch:true,cookieAndDraftPreserved:true,snapshotUrl:snapshot.url});
  }finally{w.__dispose();}
 }
 return {contract:'browser-result-removal-v1',actualAndroidExecution:false,rows};
}

async function main(){
 const w=fixture('<main><article data-message-author-role="user" data-message-id="u1"><div data-user-message-bubble>bound question</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="a1"><div class="markdown"><p>'+('long answer '.repeat(10000))+'</p><pre><code class="language-js">const keep = 1;</code></pre></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section></main><textarea id="prompt-textarea">preserve unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button><aside id="sidebar"></aside>');
 let now=10000;w.Date.now=()=>now;const idle=new Map();let sequence=0;
 w.requestIdleCallback=(callback,options)=>{const id=++sequence;idle.set(id,{callback,options});return id;};w.cancelIdleCallback=id=>idle.delete(id);
 const runIdle=()=>{const queued=[...idle.values()];idle.clear();queued.forEach(item=>item.callback({didTimeout:false,timeRemaining:()=>10}));};
 const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg))),stats=()=>w.__pocketWebPerformance.stats(),interact=()=>w.document.dispatchEvent(new w.Event('scroll'));
 let sends=0;w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);w.document.cookie='session=preserved;path=/';w.eval(perf);
 let transcript=call('web-transcript');const cursor=value=>({documentId:value.documentId,revision:value.revision}),entry=value=>value.changes.find(row=>row.id==='id:a1');
 const body=w.document.querySelector('.markdown'),text=body.querySelector('p').firstChild;
 interact();check('Captured scroll, including a scroller without wheel events, marks interaction',w.__pocketWebPerformance.meta().interacting);
 text.nodeValue+=' first final tail';await settle();let before=stats(),inspection=call('web-inspect');
 check('Active reading inspects browser readiness without result classification',inspection.composer&&!('terminal'in inspection)&&!('submitted'in inspection)&&!('markdown'in inspection));
 check('Browser readiness performs no synchronous markdown or file rebuild',stats().derivedBuilt===before.derivedBuilt&&idle.size===0);
 call('web-inspect');call('poll');call('latest');
 check('Repeated readiness and retired result commands never queue reply preparation',idle.size===0&&stats().capturesScheduled===before.capturesScheduled);
 transcript=call('web-transcript',cursor(transcript));let full=entry(transcript);
 check('Explicit snapshots retain the complete body and code during active reading',w.__pocketWebPerformance.meta().interacting&&full.text.includes('first final tail')&&full.text.includes('```js\nconst keep = 1;'));
 before=stats();interact();const unchanged=call('web-transcript',cursor(transcript));
 check('Unchanged explicit snapshots reuse cached content during continuous interaction',unchanged.changed===false&&!Object.hasOwn(unchanged,'changes')&&idle.size===0&&stats().derivedBuilt===before.derivedBuilt);
 text.nodeValue+=' stale candidate';await settle();call('web-inspect');before=stats();text.nodeValue+=' newest final suffix';w.document.querySelector('section').insertAdjacentHTML('beforeend','<a id="late-download" download="latest.csv" href="https://chatgpt.com/backend-api/files/latest">latest.csv</a>');await settle();runIdle();
 check('Body and sibling-file changes do not trigger automatic result preparation',stats().derivedBuilt===before.derivedBuilt&&stats().capturesPrepared===before.capturesPrepared&&idle.size===0);
 transcript=call('web-transcript',cursor(transcript));full=entry(transcript);
 check('The next explicit snapshot retains the whole reply and late generated attachment',full.text.includes('newest final suffix')&&full.text.startsWith('long answer')&&full.downloads.some(file=>file.name==='latest.csv'));
 text.nodeValue+=' navigation candidate';await settle();call('web-inspect');before=stats();w.history.replaceState({},'','/c/other');runIdle();
 check('Changing conversation schedules no stale result preparation',stats().derivedBuilt===before.derivedBuilt&&idle.size===0);
 const other=call('web-transcript',cursor(transcript));check('A new browser route resets the explicit transcript cursor',other.reset&&other.url.endsWith('/c/other'));
 check('No result command can bind or finish another conversation',call('poll').ok===false&&call('latest').ok===false);
 w.history.replaceState({},'','/c/interaction-fixture');transcript=call('web-transcript',cursor(other));full=entry(transcript);
 check('Returning to a route keeps its complete on-demand transcript',transcript.reset&&full.text.includes('navigation candidate'));
 text.nodeValue+=' detached candidate';await settle();call('web-inspect');body.remove();await settle();before=stats();runIdle();
 check('Detached DOM causes no automatic final-response conversion',stats().derivedBuilt===before.derivedBuilt&&idle.size===0);
 body.querySelector('p').append(' restored detached tail');w.document.querySelector('[data-message-id="a1"]').append(body);await settle();transcript=call('web-transcript',cursor(transcript));full=entry(transcript);
 check('Restored virtualized content is freshly read with its detached edits',full.text.includes('restored detached tail'));
 now+=1000;transcript=call('web-transcript');before=stats();const revision=transcript.revision;
 for(let i=0;i<100;i++)text.nodeValue+=' '+i;await settle();const after=stats();
 check('One mutation batch visits shared ancestors once instead of once per token',after.mutationRecords-before.mutationRecords===100&&after.ancestorVisits-before.ancestorVisits<20);
 transcript=call('web-transcript',cursor(transcript));full=entry(transcript);check('Batch coalescing still advances the transcript revision and preserves every token',transcript.revision!==revision&&full.text.includes(' 98 99'));
 transcript=call('web-transcript');const sidebar=w.document.getElementById('sidebar');for(let i=0;i<100;i++)sidebar.append(w.document.createElement('div'));await settle();transcript=call('web-transcript');before=stats();
 [...sidebar.children].forEach((node,index)=>node.className='unrelated-'+index);await settle();
 check('Unrelated sidebar class animation leaves message content and transcript clean',!w.__pocketWebPerformance.meta().dirty&&stats().derivedBuilt===before.derivedBuilt);
 body.querySelector('code').className='language-python';await settle();transcript=call('web-transcript',cursor(transcript));full=entry(transcript);
 check('Meaningful code class changes still invalidate cached markdown accurately',full.text.includes('```python\nconst keep = 1;')&&!full.text.includes('```js'));
 const mixedRevision=transcript.revision;
 body.classList.add('presentation-animation');text.nodeValue+=' mixed class and text';await settle();transcript=call('web-transcript',cursor(transcript));full=entry(transcript);
 check('A mixed class-first/text batch invalidates shared cached ancestors correctly',transcript.revision!==mixedRevision&&full.text.includes('mixed class and text'));
 check('The transcript publishes the changed complete reply after a mixed batch',transcript.changed&&full.text.includes('mixed class and text'));
 const newTurn=w.document.createElement('article');newTurn.setAttribute('data-message-id','mixed-new-user');newTurn.textContent='a genuinely later question';w.document.querySelector('main').append(newTurn);await settle();transcript=call('web-transcript');
 newTurn.className='new-message-animation';newTurn.setAttribute('data-message-author-role','user');await settle();
 const mixedTranscript=call('web-transcript',cursor(transcript));
 check('A class-first identity batch retains the new user entry without result binding',call('poll').ok===false&&mixedTranscript.changes.some(row=>row.id==='id:mixed-new-user'&&row.role==='user'&&row.text==='a genuinely later question'));

 check('Interaction scheduling is read-only and preserves the login, draft and zero-send invariant',sends===0&&w.document.cookie.includes('session=preserved')&&w.document.querySelector('textarea').value==='preserve unsent draft');
 w.__dispose();

 const clickWindow=fixture('<form><textarea id="prompt-textarea">synchronous send draft</textarea>'+Array.from({length:1000},(_,i)=>'<button aria-label="Historical control '+i+'">old control</button>').join('')+'<button data-testid="send-button" aria-label="Send">Send</button></form><main><article data-message-author-role="user" data-message-id="previous">old question</article></main>');
 const handlers=[],timers=new Map(),events=[];let timerId=0,rects=0,styles=0;const originalAdd=clickWindow.document.addEventListener.bind(clickWindow.document);
 clickWindow.document.addEventListener=(type,fn,...rest)=>{if(type==='click')handlers.push(fn);originalAdd(type,fn,...rest);};clickWindow.setTimeout=(fn,delay)=>{const id=++timerId;timers.set(id,{fn,delay});return id;};clickWindow.clearTimeout=id=>timers.delete(id);
 clickWindow.Element.prototype.getClientRects=()=>{rects++;return [{}];};clickWindow.getComputedStyle=()=>{styles++;return {display:'block',visibility:'visible'};};clickWindow.PocketWebReply={postMessage:value=>events.push(JSON.parse(value))};clickWindow.eval(observer);
 const clickCall=(action,arg={})=>clickWindow.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));clickCall('observe-install');rects=styles=0;
 handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('button')});
 check('An unrelated trusted button gesture performs no full-page visibility/layout walk',rects<=1&&styles<=2&&events.length===0);
 handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('[data-testid="send-button"]')});
 check('A trusted send gesture creates no native send intent or prompt snapshot',events.length===0&&!Object.keys(clickWindow.__pocketWebReplyObserver).some(key=>/intent|pending|bound/i.test(key)));
 check('A real send checks visibility of only matching controls, not historical buttons',rects<10&&styles<20);
 clickWindow.document.querySelector('textarea').value='later draft';handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('[data-testid="send-button"]')});
 check('A subsequent different prompt remains solely in the website composer',events.length===0&&clickWindow.document.querySelector('textarea').value==='later draft');
 for(const [id,item] of [...timers])if(item.delay===50){timers.delete(id);item.fn();}let urls=0;const NativeURL=clickWindow.URL;clickWindow.URL=class extends NativeURL{constructor(...args){super(...args);urls++;}};
 for(let i=0;i<20;i++){clickWindow.document.querySelector('main').setAttribute('class','pulse'+i);await settle();}
 check('An already ready route avoids repeated URL parsing for unrelated mutations',urls===0);clickWindow.__dispose();

 const scaleWindow=fixture('<p>Ready</p>'),messages=[],frames=new Map();let frameId=0,scaleValue=1,width=390,widthReads=0;scaleWindow.browser={runtime:{connectNative:()=>({postMessage:m=>messages.push(m),onMessage:{addListener:()=>{}}})}};const resize=[];
 scaleWindow.visualViewport={get scale(){return scaleValue;},addEventListener:(type,fn)=>resize.push(fn)};const nativeWindowAdd=scaleWindow.addEventListener.bind(scaleWindow);scaleWindow.addEventListener=(type,fn,...rest)=>{if(type==='resize')resize.push(fn);nativeWindowAdd(type,fn,...rest);};scaleWindow.requestAnimationFrame=fn=>{const id=++frameId;frames.set(id,fn);return id;};scaleWindow.cancelAnimationFrame=id=>frames.delete(id);Object.defineProperty(scaleWindow.document.documentElement,'clientWidth',{get(){widthReads++;return width;}});scaleWindow.eval(content);
 check('Initial Gecko scale is reported immediately',messages.filter(m=>m.kind==='scale').length===1&&messages.find(m=>m.kind==='scale').width===390);
 messages.length=0;widthReads=0;for(let i=0;i<120;i++)resize.forEach(fn=>fn());
 check('Paired resize bursts schedule a single frame without synchronous viewport reads',frames.size===1&&widthReads===0&&messages.length===0);
 const flushFrame=()=>{const queued=[...frames.values()];frames.clear();queued.forEach(fn=>fn());};flushFrame();
 check('An unchanged viewport sends no redundant native scale message',widthReads===1&&messages.length===0);
 scaleValue=1.2;width=700;resize.forEach(fn=>fn());scaleValue=1.35;width=720;resize.forEach(fn=>fn());flushFrame();
 check('The coalesced resize preserves the final actual scale and viewport width',messages.length===1&&messages[0].kind==='scale'&&messages[0].value===scaleWindow.devicePixelRatio*1.35&&messages[0].width===720);
 resize.forEach(fn=>fn());flushFrame();check('A later duplicate event also leaves the final scale unchanged',messages.length===1);
 scaleValue=1.5;width=740;resize.forEach(fn=>fn());scaleWindow.dispatchEvent(new scaleWindow.Event('pagehide'));
 check('Leaving the page flushes a pending final scale even when animation frames stop',frames.size===0&&messages.length===2&&messages.at(-1).value===scaleWindow.devicePixelRatio*1.5&&messages.at(-1).width===740);
 scaleValue=1.6;width=760;resize.forEach(fn=>fn());Object.defineProperty(scaleWindow.document,'visibilityState',{value:'hidden',configurable:true});scaleWindow.document.dispatchEvent(new scaleWindow.Event('visibilitychange'));
 check('Backgrounding flushes and cancels the pending viewport frame once',frames.size===0&&messages.length===3&&messages.at(-1).value===scaleWindow.devicePixelRatio*1.6&&messages.at(-1).width===760);scaleWindow.__dispose();
 const retiredResults=await retiredResultControls();
 console.log(JSON.stringify({contract:'browser-result-removal-v1',retiredSemantics:['queued reply prewarm','native completion during interaction','send intent snapshots'],passed:checks.length,total:checks.length,scope:'Actual production JS in controlled DOM; idle and geometry are test-controlled, not Android performance',checks,retiredResults},null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
