/* Observe page readiness, resource use and attachment removal only.
 * The browser never creates or confirms a website-send task. */
(() => {
  'use strict';
  window.__pocketInstallWebReplyObserver = (api, resourceBinding = '') => {
    if (window !== window.top || location.origin !== 'https://chatgpt.com' ||
        !window.PocketWebReply?.postMessage) return false;
    if (window.__pocketWebReplyObserver) { window.__pocketWebReplyObserver.refreshResources?.(resourceBinding); return true; }
    const uuid = () => typeof crypto.randomUUID === 'function' ? crypto.randomUUID() :
      [...crypto.getRandomValues(new Uint8Array(16))].map(n => n.toString(16).padStart(2, '0')).join('');
    const documentId = window.__pocketAttachmentDocumentId || (window.__pocketAttachmentDocumentId = uuid());
    let lastGestureAt = 0, gestureUntil = 0, gestureTimer = null;
    const attachmentEvents=[];
    let readyRoute = '', readyUrl = '', readinessScheduled = false;
    let resourceScheduled=false,lastResource='',resourceSequence=0,resourceZone=null;
    const resourceSelectors='[data-testid="stop-button"],button[aria-label="Stop"],button[aria-label="Stop generating"],button[aria-label="Stop streaming"],button[aria-label="停止"],button[aria-label="停止生成"],[data-state="uploading"],[data-upload-state],[role="progressbar"],[aria-busy="true"],#prompt-textarea,[data-composer-markdown]';
    const normalized = text => String(text || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
    const address = url => new URL(url).origin + new URL(url).pathname;
    const newChat = url => /^\/(?:g\/[^/]+\/?)?$/.test(new URL(url).pathname);
    const sameRoute = (from, to) => address(from) === address(to) ||
      (newChat(from) && /^\/(?:g\/[^/]+\/)?c\/[^/]+$/.test(new URL(to).pathname));
    const removeLabel=button=>/^(Remove (?:file|attachment|image)|Remove$|移除|删除附件|删除文件)/i.test(normalized(button?.getAttribute('aria-label')||button?.getAttribute('title')||button?.innerText));
    function attachmentNames(button,zone){
      for(let root=button?.parentElement,depth=0;root&&root!==zone&&depth<7;root=root.parentElement,depth++){
        if([...root.querySelectorAll('button,[role="button"]')].filter(removeLabel).length!==1)break;
        const nodes=[root,...root.querySelectorAll('[data-file-name],[title],img[alt]')];
        for(const attribute of ['data-file-name','title','alt']){const names=nodes.map(node=>normalized(node.getAttribute(attribute))).filter(name=>name&&name.length<=160&&!/^(Remove|移除|删除)/i.test(name));if(names.length)return [...new Set(names)];}
        const names=[...root.querySelectorAll('span,p')].filter(node=>!node.children.length&&!button.contains(node)).map(node=>normalized(node.textContent)).filter(name=>name&&name.length<=160);if(names.length)return [...new Set(names)];
      }
      return [];
    }
    function attachmentFact(kind,names,at,url){if(!names.length)return;attachmentEvents.push({kind,names,at,url});if(attachmentEvents.length>64)attachmentEvents.shift();}
    function emit(type, data = {}) {
      try { window.PocketWebReply.postMessage(JSON.stringify({type, documentId, url:location.href, resourceBinding, ...data})); }
      catch (_) { /* No website behavior depends on a host callback. */ }
    }
    // A brief interaction guard prevents configuration changes from racing a
    // website event. It neither reads the input nor checks a send/reply result.
    function noteInteraction() {
      lastGestureAt = Date.now(); gestureUntil = lastGestureAt + 1500;
      clearTimeout(gestureTimer);
      gestureTimer = setTimeout(() => { gestureTimer = null; scheduleResources(); }, 1500);
      scheduleResources();
    }
    function resourceBusy() { return !!api.resourceBusy() || Date.now() < gestureUntil; }
    function scheduleResources(){
      if(resourceScheduled||typeof api.uploadBusy!=='function'||typeof api.resourceBusy!=='function')return;
      resourceScheduled=true;
      setTimeout(()=>{resourceScheduled=false;const input=api.composer();resourceZone=input&&(input.closest('form')||input.parentElement?.parentElement);const busy=resourceBusy(),uploading=!!api.uploadBusy(),signature=address(location.href)+'|'+busy+'|'+uploading;if(signature===lastResource)return;lastResource=signature;emit('resource-work',{busy,uploading,resourceSequence:++resourceSequence,capturedAt:Date.now()});},250);
    }
    function resourceMutations(records){
      // Reply text/markdown mutations never scan page buttons or composer.
      // Cache the small composer zone and observe only relevant controls.
      const related=(node,deep=false)=>node?.nodeType===1&&(resourceZone?.contains(node)||node.matches(resourceSelectors)||deep&&!node.closest('[data-message-author-role],article,[data-turn]')&&!!node.querySelector(resourceSelectors));
      if(records.some(record=>record.type!=='characterData'&&(related(record.target)||record.type==='childList'&&[...record.addedNodes,...record.removedNodes].slice(0,32).some(node=>related(node,true)))))scheduleResources();
    }
    // One readiness signal per route; the host still checks composer and transcript.
    // This can run before window.load when an unrelated resource is slow.
    function scheduleReadiness() {
      if (readinessScheduled || readyUrl === location.href) return;
      if(readyRoute===address(location.href)){readyUrl=location.href;emit('resource-route');lastResource='';scheduleResources();return;}
      readinessScheduled = true;
      setTimeout(() => {
        readinessScheduled = false;
        if (!api.composer()) return;
        if (!newChat(location.href) && !api.hasMessages()) return;
        readyRoute = address(location.href);
        readyUrl=location.href;
        emit('ready');
      }, 50);
    }
    document.addEventListener('click', event => {
      if (!event.isTrusted) return;
      const target = event.target instanceof Element ? event.target : event.target?.parentElement;
      const button = target?.closest('button,[role="button"]');
      const input=api.composer(),zone=input&&(input.closest('form')||input.parentElement?.parentElement);
      if (!zone?.contains(target)) return;
      noteInteraction();
      if(button&&removeLabel(button))attachmentFact('removed',attachmentNames(button,zone),Date.now(),location.href);
    }, true);
    document.addEventListener('keydown', event => {
      if (!event.isTrusted) return;
      const input = api.composer();
      if (input && (input === event.target || input.contains(event.target))) noteInteraction();
    }, true);
    window.addEventListener('popstate', () => {scheduleReadiness();scheduleResources();});
    new MutationObserver(records=>{scheduleReadiness();resourceMutations(records);}).observe(document, {subtree:true, childList:true, attributes:true});
    document.addEventListener('DOMContentLoaded', scheduleReadiness, {once:true});
    scheduleReadiness();
    scheduleResources();
    function requestResources(request){
      if(typeof request!=='string'||!/^[a-zA-Z0-9-]{16,80}$/.test(request))return false;
      const busy=resourceBusy(),uploading=!!api.uploadBusy();
      lastResource=address(location.href)+'|'+busy+'|'+uploading;
      emit('resource-work',{busy,uploading,guardRequestId:request,resourceSequence:++resourceSequence,capturedAt:Date.now()});return true;
    }
    window.__pocketWebReplyObserver = Object.freeze({requestResources,documentId,lastGestureAt:()=>lastGestureAt,attachmentEvidence:(name,since)=>{if(!Number.isFinite(since)||since<=0)return {};const facts=attachmentEvents.filter(event=>event.at>since&&event.names.includes(name)&&sameRoute(event.url,location.href));return {removed:facts.some(event=>event.kind==='removed')};},refreshResources:binding=>{if(typeof binding!=='string'||binding.length>80||binding===resourceBinding)return;resourceBinding=binding;lastResource='';scheduleResources();}});
    return true;
  };
})();
