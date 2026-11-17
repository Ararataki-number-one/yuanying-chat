/* Production driver in controlled DOM. No real account, network or Android UI. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync('app/src/main/assets/page-driver.js','utf8'),performanceSource=fs.readFileSync('app/src/main/assets/web-performance.js','utf8'),checks=[];
const check=(name,ok)=>{assert.ok(ok,name);checks.push({name,pass:true});};
const conversation='<article data-message-author-role="user" data-message-id="bound-user"><div data-user-message-bubble>original question</div></article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="bound-reply"><div class="markdown"><p>complete original answer</p></div></div><button data-testid="copy-turn-action-button" aria-label="Copy response">Copy</button></section>';
const socketFixtures=[
 ['current-alert',true,(w,t)=>w.document.querySelector('section[data-turn="assistant"]').insertAdjacentHTML('beforeend','<div role="alert">'+t+'</div>')],
 ['global-alert',true,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div role="alert">'+t+'</div>')],
 ['current-retry',true,(w,t)=>w.document.querySelector('section[data-turn="assistant"]').insertAdjacentHTML('beforeend','<span>'+t+'</span><button aria-label="Retry">Retry</button>')],
 ['global-retry',true,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div><span>'+t+'</span><button aria-label="Retry">Retry</button></div>')],
 ['loading-global-alert',true,(w,t)=>{w.document.querySelector('main').innerHTML='<div role="status">Loading</div>';w.document.body.insertAdjacentHTML('beforeend','<div role="alert">'+t+'</div>');}],
 ['ordinary-answer',false,(w,t)=>w.document.querySelector('.markdown p').textContent='The phrase '+t+' is discussed as ordinary answer text.'],
 ['ordinary-answer-with-reply-retry',false,(w,t)=>{w.document.querySelector('.markdown p').textContent=t;w.document.querySelector('[data-message-id="bound-reply"]').insertAdjacentHTML('beforeend','<button aria-label="Retry">Retry</button>');}],
 ['ordinary-answer-with-global-retry',false,(w,t)=>{w.document.querySelector('.markdown p').textContent=t;w.document.body.insertAdjacentHTML('beforeend','<button aria-label="Retry">Retry</button>');}],
 ['ordinary-answer-with-shared-wrapper-retry',false,(w,t)=>{w.document.querySelector('.markdown p').textContent=t;const box=w.document.createElement('div');w.document.body.append(box);box.append(w.document.querySelector('main'));box.insertAdjacentHTML('beforeend','<button aria-label="Retry">Retry</button>');}],
 ['historical-alert',false,(w,t)=>w.document.querySelector('main').insertAdjacentHTML('afterbegin','<section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="past"><div role="alert">'+t+'</div></div></section>')],
 ['historical-retry',false,(w,t)=>w.document.querySelector('main').insertAdjacentHTML('afterbegin','<section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="past">old answer</div><div>'+t+'<button aria-label="Retry">Retry</button></div></section>')],
 ['unlabelled-historical-retry',false,(w,t)=>w.document.querySelector('main').insertAdjacentHTML('afterbegin','<section><div data-message-author-role="assistant" data-message-id="past">old answer</div><div>'+t+'<button aria-label="Retry">Retry</button></div></section>')],
 ['user-quoted-alert',false,(w,t)=>w.document.querySelector('[data-message-id="bound-user"]').insertAdjacentHTML('beforeend','<span role="alert">'+t+'</span>')],
 ['code-block-alert',false,(w,t)=>w.document.querySelector('.markdown').insertAdjacentHTML('beforeend','<pre><code><span role="alert">'+t+'</span></code></pre>')],
 ['inline-code-alert',false,(w,t)=>w.document.querySelector('.markdown').insertAdjacentHTML('beforeend','<code><span role="alert">'+t+'</span></code>')],
 ['code-block-retry',false,(w,t)=>w.document.querySelector('.markdown').insertAdjacentHTML('beforeend','<pre><code>'+t+'<button aria-label="Retry">Retry</button></code></pre>')],
 ['hidden-alert',false,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div role="alert" hidden>'+t+'</div>')],
 ['aria-hidden-alert',false,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div aria-hidden="true"><div role="alert">'+t+'</div></div>')],
 ['menu-alert',false,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div role="menu"><div role="alert">'+t+'</div></div>')],
 ['body-text-without-error-surface',false,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<p>'+t+'</p>')]
];
async function observeSocket(name,expected,setup,phrase,action){
 const w=new JSDOM('<!doctype html><body><main>'+conversation+'</main><textarea id="prompt-textarea">keep unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button></body>',{url:'https://chatgpt.com/c/original',runScripts:'outside-only'}).window;
 Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.hidden?'':this.textContent;}});
 w.Element.prototype.getClientRects=function(){return this.hidden?[]:[{}];};w.getComputedStyle=()=>({display:'block',visibility:'visible'});
 let clicks=0,fetches=0;w.document.addEventListener('click',()=>clicks++);w.fetch=()=>{fetches++;return Promise.reject(new Error('unexpected network attempt'));};w.document.cookie='session=keep;path=/';
 w.eval(performanceSource);
 setup(w,phrase);await Promise.resolve();await Promise.resolve();
 const call=(a,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(a)).replace('__ARG__',JSON.stringify(arg)));
 call('web-transcript');
 const args={kind:'web',confirmed:true,userKey:'id:bound-user',prompt:'original question',expectedUrl:w.location.href,confirmedUrl:w.location.href,export:true,lightObservation:true,incrementalObservation:true};
 const output=JSON.parse(JSON.stringify(call(action,action==='web-inspect'?{}:args)));
 const noEffects=clicks===0&&fetches===0&&w.document.cookie==='session=keep'&&w.document.querySelector('textarea').value==='keep unsent draft'&&w.location.href==='https://chatgpt.com/c/original';
 const classified=!!output.websiteSocketClosed&&output.errorCode==='website_socket_closed'&&output.recoverable===true&&String(output.error).includes('实时连接');
 const clear=!output.websiteSocketClosed&&!output.errorCode&&output.error==='';
 const row={fixture:name,phrase,action,expectedWebsiteSocketFailure:expected,pass:(expected?classified:clear)&&noEffects,noEffects,output};
 w.close();return row;
}
async function socketSurfaceMatrix(){
 const results=[];
 for(const suffix of ['closed','failed'])for(const [name,expected,setup]of socketFixtures)for(const action of ['web-inspect'])results.push(await observeSocket(name,expected,setup,'Browser app server websocket '+suffix,action));
 for(const phrase of ['Browser app server websocket failure','database authentication failed'])for(const action of ['web-inspect'])results.push(await observeSocket('unrelated-failure-role-alert',false,(w,t)=>w.document.body.insertAdjacentHTML('beforeend','<div role="alert">'+t+'</div>'),phrase,action));
 return results;
}

async function main(){
 const w=new JSDOM('<!doctype html><body><main>'+conversation+'</main><textarea id="prompt-textarea">keep unsent draft</textarea><button data-testid="send-button" aria-label="Send">Send</button></body>',{url:'https://chatgpt.com/c/original',runScripts:'outside-only'}).window;
 Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.hidden?'':this.textContent;}});
 w.Element.prototype.getClientRects=function(){return this.hidden?[]:[{}];};w.getComputedStyle=()=>({display:'block',visibility:'visible'});
 let sends=0,fetches=0;w.document.querySelector('[data-testid="send-button"]').addEventListener('click',()=>sends++);
 w.fetch=()=>{fetches++;throw new Error('unexpected network');};w.document.cookie='session=keep;path=/';
 w.eval(performanceSource);const call=(action,arg={})=>w.eval(source.replace('__ACTION__',JSON.stringify(action)).replace('__ARG__',JSON.stringify(arg)));
 const args={kind:'web',confirmed:true,userKey:'id:bound-user',prompt:'original question',expectedUrl:w.location.href,confirmedUrl:w.location.href,export:true,lightObservation:true,incrementalObservation:true},settle=async()=>{await Promise.resolve();await Promise.resolve();};
 const rejected=()=>{const value=call('poll',args);return value.ok===false&&!('submitted'in value)&&!('terminal'in value)&&!('bindingPending'in value)&&!('markdown'in value);};
 check('Retired poll command rejects a previously confirmed task',rejected());
 check('Retired latest command cannot read or classify a response',call('latest',args).ok===false);
 check('Native submit and regenerate commands remain unavailable',call('submit',args).ok===false&&call('regenerate',args).ok===false);
 let inspect=call('web-inspect');
 check('Page readiness works without an active reply task',inspect.composer&&inspect.hasMessages&&!inspect.websiteSocketClosed);
 check('Page readiness contains no sent or completion classification',!('submitted'in inspect)&&!('terminal'in inspect)&&!('bindingPending'in inspect));
 const main=w.document.querySelector('main'),saved=main.innerHTML;
 main.innerHTML='<div role="status">Loading</div>';await settle();inspect=call('web-inspect');
 check('A loading shell is ordinary page state with no pending-send outcome',!inspect.hasMessages&&rejected());
 main.innerHTML=saved;await settle();
 check('Hydration resumes page metadata without restoring a retired task',call('web-inspect').hasMessages&&rejected());
 const user=w.document.querySelector('[data-message-id="bound-user"]');user.remove();await settle();
 check('Virtualizing the original user does not create binding state',rejected()&&!('bindingLost'in call('web-inspect')));
 main.prepend(user);user.querySelector('[data-user-message-bubble]').textContent='';await settle();
 check('An empty question placeholder cannot reactivate send observation',rejected());
 user.querySelector('[data-user-message-bubble]').textContent='an edited question';await settle();
 check('Editing a question stays solely in the website',rejected());
 main.insertAdjacentHTML('beforeend','<article data-message-author-role="user" data-message-id="new-user">another question</article>');await settle();
 check('A later question creates no native completion or other-question classification',rejected()&&!('otherQuestion'in call('web-inspect')));
 for(const route of ['/','/c/assigned','/c/other']){w.history.replaceState({},'',route);await settle();check('Route '+route+' cannot resurrect retired result polling',rejected());}
 w.history.replaceState({},'','/c/original');main.innerHTML=saved;await settle();
 w.document.body.insertAdjacentHTML('beforeend','<div role="alert" id="connection-alert">Browser app server websocket closed</div>');await settle();inspect=call('web-inspect');
 check('A current website connection error remains visible without result detection',inspect.websiteSocketClosed&&inspect.errorCode==='website_socket_closed'&&inspect.recoverable);
 main.innerHTML='<div role="status">Loading</div>';await settle();
 check('Connection errors remain recoverable through a loading shell',call('web-inspect').websiteSocketClosed&&rejected());
 w.document.getElementById('connection-alert').hidden=true;await settle();
 check('Hidden stale connection alerts do not become active failures',!call('web-inspect').websiteSocketClosed);
 w.document.getElementById('connection-alert').remove();main.innerHTML=saved;await settle();
 check('Clearing an error restores ordinary readiness with no resend',!call('web-inspect').websiteSocketClosed&&sends===0&&fetches===0);
 check('All retired task and readiness probes preserve the login cookie and unsent draft',w.document.cookie==='session=keep'&&w.document.querySelector('textarea').value==='keep unsent draft');
 w.close();
 const browserLifecycleChecks=checks.length,socketSurfaces=await socketSurfaceMatrix();
 for(const row of socketSurfaces)checks.push({name:'Socket surface '+row.fixture+' / '+row.phrase+' / '+row.action,pass:row.pass});
 const passed=checks.filter(row=>row.pass).length;
 console.log(JSON.stringify({contract:'browser-result-removal-v1',passed,total:checks.length,browserLifecycleChecks,socketSurfaceChecks:socketSurfaces.length,retiredSemantics:['message binding','send confirmation','reply completion polling','route assignment to a reply task'],scope:'Production JS DOM fixtures for result-feature removal and retained page connection recovery; no live account/network or Android UI claim',checks,socketSurfaces},null,2));
 assert.equal(passed,checks.length,'All browser lifecycle and socket surface checks must pass');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
