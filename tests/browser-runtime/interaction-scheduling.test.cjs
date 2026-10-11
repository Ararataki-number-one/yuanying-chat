/* Production observation with controlled idle/geometry. No Android frame-rate claim. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync('app/src/main/assets/page-driver.js','utf8'),perf=fs.readFileSync('app/src/main/assets/web-performance.js','utf8'),observer=fs.readFileSync('app/src/main/assets/web-reply-observer.js','utf8'),content=fs.readFileSync('app/src/main/assets/gecko/content.js','utf8');
const checks=[],check=(name,ok)=>{assert.ok(ok,name);checks.push({name,pass:true});};
const settle=async()=>{await Promise.resolve();await Promise.resolve();};
function fixture(html){const w=new JSDOM('<!doctype html><body>'+html+'</body>',{url:'https://chatgpt.com/c/interaction-fixture',runScripts:'outside-only',pretendToBeVisual:true}).window;const observers=[],NativeObserver=w.MutationObserver;w.MutationObserver=class extends NativeObserver{constructor(callback){super(callback);observers.push(this);}};w.__dispose=()=>{for(const item of observers)item.disconnect();w.close();};Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});w.Element.prototype.getClientRects=()=>[{}];w.getComputedStyle=()=>({display:'block',visibility:'visible'});return w;}
async function main(){
 const w=fixture('<main><article data-message-author-role="user" data-message-id="u1"><div data-user-message-bubble>bound question</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="a1"><div class="markdown"><p>'+('long answer '.repeat(10000))+'</p><pre><code class="language-js">const keep = 1;</code></pre></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section></main><textarea id="prompt-textarea">preserve unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button><aside id="sidebar"></aside>');
 let now=10000;w.Date.now=()=>now;const idle=new Map();let sequence=0;
 w.requestIdleCallback=(callback,options)=>{const id=++sequence;idle.set(id,{callback,options});return id;};w.cancelIdleCallback=id=>idle.delete(id);
 const runIdle=()=>{const queued=[...idle.values()];idle.clear();queued.forEach(item=>item.callback({didTimeout:false,timeRemaining:()=>10}));};
 const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg))),stats=()=>w.__pocketWebPerformance.stats(),interact=()=>w.document.dispatchEvent(new w.Event('scroll'));
 let sends=0;w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);w.document.cookie='session=preserved;path=/';w.eval(perf);
 let transcript=call('web-transcript'),args={kind:'web',confirmed:true,userKey:'id:u1',prompt:'bound question',expectedUrl:w.location.href,confirmedUrl:w.location.href,export:true,lightObservation:true,incrementalObservation:true};
 let full=call('poll',args),known={...args,knownReplyKey:full.replyKey,knownReplyContentRevision:full.replyContentRevision};
 const body=w.document.querySelector('.markdown'),text=body.querySelector('p').firstChild;
 interact();check('Captured scroll, including a scroller without wheel events, marks interaction',w.__pocketWebPerformance.meta().interacting);
 text.nodeValue+=' first final tail';await settle();let before=stats(),deferred=call('poll',known);
 check('First changed final capture yields during active reading without claiming completion content',deferred.captureDeferred&&deferred.contentObserved===false&&deferred.terminal&&!deferred.busy&&!('markdown'in deferred));
 check('Yielding the final capture performs no synchronous markdown or file rebuild',stats().derivedBuilt===before.derivedBuilt&&idle.size===1);
 check('Continuous scrolling has a bounded idle deadline for the complete final body',[...idle.values()][0].options.timeout<=750);
 call('poll',known);call('poll',known);
 check('Repeated polling schedules only one idle preparation for the same exact revision',idle.size===1&&stats().capturesScheduled===before.capturesScheduled+1);
 runIdle();full=call('poll',known);
 check('Idle preparation permits complete observation while the user keeps scrolling',w.__pocketWebPerformance.meta().interacting&&full.contentObserved&&!full.captureDeferred&&full.markdown.includes('first final tail')&&full.markdown.includes('```js\nconst keep = 1;'));
 known={...args,knownReplyKey:full.replyKey,knownReplyContentRevision:full.replyContentRevision};before=stats();interact();const unchanged=call('poll',known);
 check('Known complete content remains eligible for stable sampling during continuous interaction',unchanged.contentObserved&&unchanged.contentUnchanged&&!unchanged.captureDeferred&&idle.size===0&&stats().derivedBuilt===before.derivedBuilt);
 text.nodeValue+=' stale candidate';await settle();call('poll',known);before=stats();text.nodeValue+=' newest final suffix';w.document.querySelector('section').insertAdjacentHTML('beforeend','<a id="late-download" download="latest.csv" href="https://chatgpt.com/backend-api/files/latest">latest.csv</a>');await settle();runIdle();
 check('A body or sibling-file mutation before idle cancels the old preparation',stats().derivedBuilt===before.derivedBuilt&&stats().capturesPrepared===before.capturesPrepared);
 deferred=call('poll',known);check('The changed exact revision requests a fresh preparation',deferred.captureDeferred&&idle.size===1);runIdle();full=call('poll',known);
 check('The fresh final capture contains the full latest body and late generated file',full.contentObserved&&full.hasFiles&&full.markdown.includes('newest final suffix')&&full.markdown.startsWith('long answer'));
 transcript=call('web-transcript',{documentId:transcript.documentId,revision:transcript.revision});
 check('The next transcript retains the final generated attachment and the complete reply',transcript.changes.some(row=>row.id==='id:a1'&&row.text.includes('newest final suffix')&&row.downloads.some(file=>file.name==='latest.csv')));
 known={...args,knownReplyKey:full.replyKey,knownReplyContentRevision:full.replyContentRevision};text.nodeValue+=' navigation candidate';await settle();call('poll',known);before=stats();w.history.replaceState({},'','/c/other');runIdle();
 check('Changing conversation before idle prevents stale body preparation',stats().derivedBuilt===before.derivedBuilt);
 check('An idle callback cannot rebind or finish another conversation',call('poll',known).bindingLost&&!call('poll',known).submitted);
 w.history.replaceState({},'','/c/interaction-fixture');call('poll',known);runIdle();full=call('poll',known);check('Returning to the exact route still recovers the complete original bound reply',full.submitted&&full.contentObserved&&full.markdown.includes('navigation candidate'));
 known={...args,knownReplyKey:full.replyKey,knownReplyContentRevision:full.replyContentRevision};text.nodeValue+=' detached candidate';await settle();call('poll',known);body.remove();await settle();before=stats();runIdle();
 check('Detached DOM is never prepared as the current final response',stats().derivedBuilt===before.derivedBuilt);
 body.querySelector('p').append(' restored detached tail');w.document.querySelector('[data-message-id="a1"]').append(body);await settle();call('poll',known);runIdle();full=call('poll',known);
 check('Restored virtualized content is freshly read with its detached edits',full.contentObserved&&full.markdown.includes('restored detached tail'));
 now+=1000;transcript=call('web-transcript');before=stats();const revision=full.replyContentRevision;
 for(let i=0;i<100;i++)text.nodeValue+=' '+i;await settle();const after=stats();
 check('One mutation batch visits shared ancestors once instead of once per token',after.mutationRecords-before.mutationRecords===100&&after.ancestorVisits-before.ancestorVisits<20);
 full=call('poll',args);check('Batch coalescing still changes the exact revision and preserves every appended token',full.replyContentRevision!==revision&&full.markdown.includes(' 98 99'));
 transcript=call('web-transcript');const sidebar=w.document.getElementById('sidebar');for(let i=0;i<100;i++)sidebar.append(w.document.createElement('div'));await settle();call('web-transcript');before=stats();const currentRevision=call('poll',args).replyContentRevision;
 [...sidebar.children].forEach((node,index)=>node.className='unrelated-'+index);await settle();
 check('Unrelated sidebar class animation leaves message content and transcript clean',!w.__pocketWebPerformance.meta().dirty&&call('poll',args).replyContentRevision===currentRevision&&stats().derivedBuilt===before.derivedBuilt);
 body.querySelector('code').className='language-python';await settle();full=call('poll',args);
 check('Meaningful code class changes still invalidate cached markdown accurately',full.markdown.includes('```python\nconst keep = 1;')&&!full.markdown.includes('```js'));
 transcript=call('web-transcript');const mixedRevision=full.replyContentRevision;
 // A class record precedes a text record under the same cached ancestors.
 // Class-only coalescing must still expire the complete entry/body dependency.
 body.classList.add('presentation-animation');text.nodeValue+=' mixed class and text';await settle();full=call('poll',args);
 check('A mixed class-first/text batch invalidates shared cached ancestors correctly',full.replyContentRevision!==mixedRevision&&full.markdown.includes('mixed class and text'));
 transcript=call('web-transcript',{documentId:transcript.documentId,revision:transcript.revision});
 check('The transcript publishes the changed complete reply after a mixed batch',transcript.changed&&transcript.changes.some(row=>row.id==='id:a1'&&row.text.includes('mixed class and text')));
 const newTurn=w.document.createElement('article');newTurn.setAttribute('data-message-id','mixed-new-user');newTurn.textContent='a genuinely later question';w.document.querySelector('main').append(newTurn);await settle();call('web-transcript');
 newTurn.className='new-message-animation';newTurn.setAttribute('data-message-author-role','user');await settle();
 const realChange=call('poll',args),mixedTranscript=call('web-transcript');
 check('A class-first/identity-attribute batch flags a real new question for the native completion guard',realChange.otherQuestion&&mixedTranscript.changes.some(row=>row.id==='id:mixed-new-user'&&row.role==='user'&&row.text==='a genuinely later question'));

 check('Interaction scheduling is read-only and preserves the login, draft and zero-send invariant',sends===0&&w.document.cookie.includes('session=preserved')&&w.document.querySelector('textarea').value==='preserve unsent draft');
 w.__dispose();

 const clickWindow=fixture('<textarea id="prompt-textarea">synchronous send draft</textarea>'+Array.from({length:1000},(_,i)=>'<button aria-label="Historical control '+i+'">old control</button>').join('')+'<button data-testid="send-button" aria-label="Send">Send</button><main><article data-message-author-role="user" data-message-id="previous">old question</article></main>');
 const handlers=[],timers=new Map(),events=[];let timerId=0,rects=0,styles=0;const originalAdd=clickWindow.document.addEventListener.bind(clickWindow.document);
 clickWindow.document.addEventListener=(type,fn,...rest)=>{if(type==='click')handlers.push(fn);originalAdd(type,fn,...rest);};clickWindow.setTimeout=(fn,delay)=>{const id=++timerId;timers.set(id,{fn,delay});return id;};clickWindow.clearTimeout=id=>timers.delete(id);
 clickWindow.Element.prototype.getClientRects=()=>{rects++;return [{}];};clickWindow.getComputedStyle=()=>{styles++;return {display:'block',visibility:'visible'};};clickWindow.PocketWebReply={postMessage:value=>events.push(JSON.parse(value))};clickWindow.eval(observer);
 const clickCall=(action,arg={})=>clickWindow.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));clickCall('observe-install');rects=styles=0;
 handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('button')});
 check('An unrelated trusted button gesture performs no full-page visibility/layout walk',rects===0&&styles===0&&events.length===0);
 handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('[data-testid="send-button"]')});
 check('A real send intent captures the exact draft and prior identities synchronously',events.length===1&&events[0].type==='intent'&&events[0].prompt==='synchronous send draft'&&events[0].beforeKeys.includes('id:previous'));
 check('A real send checks visibility of only matching controls, not historical buttons',rects<10&&styles<20);
 clickWindow.document.querySelector('textarea').value='later draft';handlers[0]({isTrusted:true,target:clickWindow.document.querySelector('[data-testid="send-button"]')});
 check('A subsequent trusted different prompt keeps its own exact intent snapshot',events.at(-1).type==='intent'&&events.at(-1).prompt==='later draft');
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
 console.log(JSON.stringify({passed:checks.length,total:checks.length,scope:'Actual production JS in controlled DOM; idle and geometry are test-controlled, not Android performance',checks},null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
