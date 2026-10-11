/* Cached, incremental observation. Does not change website layout or content. */
(() => {
  'use strict';
  window.__pocketInstallWebPerformance = api => {
    if (window.__pocketWebPerformance) return window.__pocketWebPerformance;
    const selector = '[data-message-author-role],article[data-turn],[data-chatgpt-search-unit-key],[data-content-search-unit-key]';
    const memoOwnerSelector=selector+',.markdown,[data-markdown-text-style="assistant-message"]';
    const cache = new WeakMap(), sent = new Map(), messageGroups=new Map();
    const documentId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
    let dirty = true, revision = 0, orderKey = '', lastUrl = '', lastInteraction = 0, nodeSequence=0, capture=null;
    const stats = {entriesBuilt:0,snapshots:0,derivedBuilt:0,messageListsBuilt:0,mutationBatches:0,mutationRecords:0,ancestorVisits:0,capturesScheduled:0,capturesPrepared:0};
    const messageAttributes=new Set(['data-message-author-role','data-turn','data-chatgpt-search-unit-key','data-content-search-unit-key']);
    function record(node) {
      let saved=cache.get(node);
      if(!saved){saved={dirty:true,version:0,identity:++nodeSequence,parts:new Map()};cache.set(node,saved);}
      return saved;
    }
    function memo(node, name, build) {
      if(!node)return build();
      const saved=record(node), previous=saved.parts.get(name);
      if(previous&&previous.version===saved.version)return previous.value;
      const value=build();saved.parts.set(name,{version:saved.version,value});stats.derivedBuilt++;
      return value;
    }
    function mark(node,visited=new Set(),cacheOnly=false) {
      let element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      let matched=false;
      while (element) {
        if(visited.has(element))break;
        visited.add(element);stats.ancestorVisits++;
        const saved = cache.get(element);
        // A body memo and its enclosing transcript entry must both expire.
        // Stopping at the first cached descendant leaves the parent stale.
        if (saved) { saved.dirty = true; saved.version++; dirty=true; }
        if (!cacheOnly&&element.matches?.(selector)) { dirty = true; matched=true; }
        element = element.parentElement;
      }
      return matched;
    }
    function expireInserted(node,expired) {
      if(node.nodeType!==Node.ELEMENT_NODE||!(cache.has(node)||node.matches(memoOwnerSelector)||node.querySelector(memoOwnerSelector)))return;
      // Virtualization can edit a detached cached turn before reattaching it.
      // Inspect that inserted subtree once; ordinary streamed text/paragraphs
      // have no memo owner and never walk the existing conversation tree.
      const walker=document.createTreeWalker(node,NodeFilter.SHOW_ELEMENT);
      let element=node;
      do {const saved=cache.get(element);if(saved&&!expired.has(element)){expired.add(element);saved.dirty=true;saved.version++;dirty=true;}}while((element=walker.nextNode()));
    }
    new MutationObserver(records => {
      const visited=new Set(),expired=new Set();stats.mutationBatches++;stats.mutationRecords+=records.length;
      for (const record of records) {
        // One browser microtask can contain many changes under the same turn.
        // Invalidate each ancestor once, while keeping every memo dependency.
        // A class-only change needs the cached owners, not selector checks on
        // unrelated composer/sidebar ancestors which have never been captured.
        mark(record.target,visited,record.type==='attributes'&&record.attributeName==='class');
        if(record.type==='attributes'&&messageAttributes.has(record.attributeName)){messageGroups.clear();dirty=true;}
        if(record.type==='childList')for(const node of record.addedNodes)expireInserted(node,expired);
        if (record.type === 'childList') for (const node of [...record.addedNodes,...record.removedNodes]) {
          if (node.nodeType === Node.ELEMENT_NODE && (node.matches(selector) || node.querySelector(selector))) { dirty = true; messageGroups.clear(); break; }
        }
      }
    }).observe(document, {subtree:true,childList:true,characterData:true,attributes:true,
      attributeFilter:['data-message-id','data-chatgpt-selection-message-id','data-chatgpt-search-message-ids',
        'href','download','src','srcset','sizes','alt','title','aria-label','hidden','aria-hidden','data-file-name','data-language','encoding',
        'class','data-testid','data-turn','data-markdown-text-style','data-is-reasoning',
        'data-message-author-role','data-chatgpt-search-unit-key','data-content-search-unit-key']});
    document.addEventListener('load', event => mark(event.target), true);
    for (const event of ['touchmove','pointerdown','wheel','scroll','keydown','input'])
      document.addEventListener(event, () => { lastInteraction = Date.now(); }, {capture:true,passive:true});
    const interacting=()=>Date.now()-lastInteraction<450;
    const cancelCapture=()=>{if(!capture)return;if(capture.idle&&window.cancelIdleCallback)cancelIdleCallback(capture.idle);if(capture.timer)clearTimeout(capture.timer);capture=null;};
    const instance = {
      meta:() => ({dirty,documentId,revision,interacting:interacting()}),
      stats:() => ({...stats}),
      memo,
      deferCapture(key,prepare){
        if(capture?.key===key&&capture.prepared)return false;
        if(!interacting()){cancelCapture();return false;}
        if(capture?.key!==key){
          cancelCapture();const candidate=capture={key,prepared:false,idle:0,timer:0};stats.capturesScheduled++;
          const run=()=>{if(capture!==candidate)return;candidate.idle=candidate.timer=0;try{candidate.prepared=prepare()!==false;}catch(_){candidate.prepared=false;}if(candidate.prepared)stats.capturesPrepared++;else if(capture===candidate)capture=null;};
          // The complete final body is still mandatory. Prewarm its memo in a
          // short idle task instead of blocking the native poll during input.
          // The deadline also permits completion during continuous scrolling.
          if(window.requestIdleCallback)candidate.idle=requestIdleCallback(run,{timeout:750});
          else candidate.timer=setTimeout(run,50);
        }
        return true;
      },
      messageNodes:(role,build)=>{if(!messageGroups.has(role)){messageGroups.set(role,build());stats.messageListsBuilt++;}return messageGroups.get(role);},
      contentRevision:nodes => documentId+':'+nodes.map(node=>{const saved=record(node);return saved.identity+'.'+saved.version;}).join(','),
      snapshot(arg) {
        stats.snapshots++;
        const nodes = api.nodes(), users = new Set(api.users()), current = [];
        const reset = arg.documentId !== documentId || arg.revision !== revision || lastUrl !== location.href;
        const changes = [], ids = new Set();
        nodes.forEach((node,index) => {
          const id = api.key(node,index); ids.add(id);
          const saved = record(node);
          const dependency=api.dependency?.(node), dependencyRecord=dependency?record(dependency):null;
          const dependencyVersion=dependencyRecord?dependencyRecord.identity+'.'+dependencyRecord.version:'';
          if (!saved.entry || saved.dirty || saved.id !== id || saved.dependencyVersion!==dependencyVersion) {
            const entry = api.entry(node,index,users);
            saved.id=id;saved.entry=entry;saved.serial=JSON.stringify(entry);saved.dirty=false;
            saved.dependencyVersion=dependencyVersion;
            stats.entriesBuilt++;
          }
          if (saved.entry.role !== 'user' && !saved.entry.text.trim() && !saved.entry.downloads?.length) return;
          current.push(id);
          if (reset || sent.get(id) !== saved.serial) changes.push(saved.entry);
          sent.set(id,saved.serial);
        });
        for (const id of sent.keys()) if (!ids.has(id)) sent.delete(id);
        const nextOrder = JSON.stringify(current), orderChanged = nextOrder !== orderKey;
        const changed = reset || orderChanged || changes.length > 0;
        orderKey = nextOrder;lastUrl = location.href;dirty = false;
        if (changed) revision++;
        return {ok:true,url:location.href,title:document.title,documentId,revision,changed,reset,
          ...(changed ? {changes,...(reset||orderChanged?{order:current}:{})} : {})};
      }
    };
    window.__pocketWebPerformance = instance;
    return instance;
  };
})();
