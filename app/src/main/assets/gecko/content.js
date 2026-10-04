/* Trusted host bridge in the extension's isolated world; never exposed to page scripts. */
(() => {
  'use strict';
  const port = browser.runtime.connectNative('pocketpage');
  window.PocketWebReply = {postMessage: text => {
    if(location.origin === 'https://chatgpt.com')port.postMessage({kind:'reply', text:String(text)});
  }};
  port.onMessage.addListener(message => {
    if(message.kind !== 'evaluate' || !Number.isInteger(message.id))return;
    try {
      const value = (0,eval)(message.code);
      // Match WebView.evaluateJavascript's immediate JSON result, including void.
      const result = value === undefined || value instanceof Promise ? 'null' : JSON.stringify(value);
      port.postMessage({kind:'result', id:message.id, result:result ?? 'null'});
    } catch (_) {port.postMessage({kind:'result', id:message.id, result:'null'});}
  });
  const scale = () => port.postMessage({kind:'scale', value:devicePixelRatio*(visualViewport?.scale ?? 1), width:document.documentElement?.clientWidth ?? 0});
  visualViewport?.addEventListener('resize',scale);
  window.addEventListener('resize',scale);
  document.addEventListener('DOMContentLoaded',scale,{once:true});
  let observedReady=false;
  const observer=new MutationObserver(()=>documentReady());
  const documentReady = () => {
    if(observedReady)return;
    if(document.readyState==='loading'||!document.body)return;
    if(document.body.innerText.trim()||document.querySelector('input,button,textarea,canvas')){
      observedReady=true;observer.disconnect();
      port.postMessage({kind:'documentReady',url:location.href});
    }
  };
  const observe = () => {if(document.documentElement)observer.observe(document.documentElement,{childList:true,subtree:true});documentReady();};
  observe();
  document.addEventListener('DOMContentLoaded',observe,{once:true});
  document.addEventListener('DOMContentLoaded',documentReady,{once:true});
  window.addEventListener('pageshow',documentReady);
  documentReady();
  port.postMessage({kind:'ready'});
  scale();
})();
