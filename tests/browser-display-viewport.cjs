// Run with JSDOM_MODULE=/absolute/node_modules/jsdom node this-file generated-script.js.
// DOM mutation checks only; Android WebView layout, login and gestures need a device.
const fs=require('node:fs');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const source=fs.readFileSync(process.argv[2],'utf8');
const checks=[];const check=(name,pass)=>{if(!pass)throw new Error(name);checks.push({name,pass:true});};
const settle=w=>new Promise(resolve=>w.setTimeout(resolve,0));
const html='<!doctype html><html><head><title>Original title</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><select id="model"><option>Original model</option></select><div id="messages">Original message</div><textarea>Unsent draft</textarea></body></html>';
(async()=>{
  const dom=new JSDOM(html,{url:'https://chatgpt.com/c/fixture',runScripts:'outside-only'}),w=dom.window;
  w.document.cookie='session_marker=keep; path=/';const before=w.document.body.innerHTML;
  w.eval(source);await settle(w);
  check('Desktop viewport replaces the phone-sized metadata',w.document.querySelector('meta[name=viewport]').content==='width=1024');
  check('Official title remains unchanged',w.document.title==='Original title');
  check('Input, model and message markup remain unchanged',w.document.body.innerHTML===before);
  check('Unsent input text remains unchanged',w.document.querySelector('textarea').value==='Unsent draft');
  check('Display policy preserves the existing cookie',w.document.cookie.includes('session_marker=keep'));
  w.eval(source);await settle(w);check('Repeated installation does not add viewport tags',w.document.querySelectorAll('meta[name=viewport]').length===1);
  w.document.querySelector('meta[name=viewport]').content='width=device-width';await settle(w);
  check('Official SPA metadata updates retain desktop width',w.document.querySelector('meta[name=viewport]').content==='width=1024');
  w.document.querySelector('meta[name=viewport]').remove();await settle(w);
  check('A replaced or removed viewport is restored once',w.document.querySelectorAll('meta[name=viewport]').length===1&&w.document.querySelector('meta[name=viewport]').content==='width=1024');
  const duplicate=w.document.createElement('meta');duplicate.name='VIEWPORT';duplicate.content='width=device-width';w.document.head.appendChild(duplicate);await settle(w);
  check('Duplicate viewport definitions cannot re-enable mobile width',[...w.document.querySelectorAll('meta[name="viewport" i]')].every(m=>m.content==='width=1024'));
  const frame=w.document.createElement('iframe');w.document.body.appendChild(frame);frame.contentWindow.eval(source);await settle(w);
  check('Embedded frames receive no desktop metadata',!frame.contentDocument.querySelector('meta[name=viewport]'));
  const early=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'outside-only'}),ew=early.window;
  ew.document.head.remove();ew.eval(source);const head=ew.document.createElement('head');ew.document.documentElement.insertBefore(head,ew.document.body);await settle(ew);
  check('Document-start installation works before head exists',head.querySelector('meta[name=viewport]').content==='width=1024');
  check('Viewport allows native pinch zoom',!head.querySelector('meta[name=viewport]').content.includes('user-scalable=no'));
  w.close();ew.close();console.log(JSON.stringify({passed:checks.length,total:checks.length,scope:'DOM only, no Android rendering or account login',checks},null,2));
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
