/* Cached, incremental observation. Does not change website layout or content. */
(() => {
  'use strict';
  window.__pocketInstallWebPerformance = api => {
    if (window.__pocketWebPerformance) return window.__pocketWebPerformance;
    const selector = '[data-message-author-role],article[data-turn],[data-chatgpt-search-unit-key],[data-content-search-unit-key]';
    const cache = new WeakMap(), sent = new Map(), messageGroups=new Map();
    const documentId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
    let dirty = true, revision = 0, orderKey = '', lastUrl = '', lastInteraction = 0, nodeSequence=0;
    const stats = {entriesBuilt:0,snapshots:0,derivedBuilt:0,messageListsBuilt:0};
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
    function mark(node) {
      let element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      let matched=false;
      while (element) {
        const saved = cache.get(element);
        // A body memo and its enclosing transcript entry must both expire.
        // Stopping at the first cached descendant leaves the parent stale.
        if (saved) { saved.dirty = true; saved.version++; }
        if (element.matches?.(selector)) { dirty = true; matched=true; }
        element = element.parentElement;
      }
      return matched;
    }
    new MutationObserver(records => {
      for (const record of records) {
        mark(record.target);
        if(record.type==='attributes'&&messageAttributes.has(record.attributeName)){messageGroups.clear();dirty=true;}
        if (record.type === 'childList') for (const node of [...record.addedNodes,...record.removedNodes]) {
          if (node.nodeType === Node.ELEMENT_NODE && (node.matches(selector) || node.querySelector(selector))) { dirty = true; messageGroups.clear(); break; }
        }
      }
    }).observe(document, {subtree:true,childList:true,characterData:true,attributes:true,
      attributeFilter:['data-message-id','data-chatgpt-selection-message-id','data-chatgpt-search-message-ids',
        'href','download','src','alt','aria-label','hidden','aria-hidden','data-file-name',
        'class','data-testid','data-turn','data-markdown-text-style','data-is-reasoning',
        'data-message-author-role','data-chatgpt-search-unit-key','data-content-search-unit-key']});
    document.addEventListener('load', event => mark(event.target), true);
    for (const event of ['touchmove','pointerdown','wheel','keydown','input'])
      document.addEventListener(event, () => { lastInteraction = Date.now(); }, {capture:true,passive:true});
    const instance = {
      meta:() => ({dirty,documentId,revision,interacting:Date.now()-lastInteraction<450}),
      stats:() => ({...stats}),
      memo,
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
          if (!saved.entry || saved.dirty || saved.id !== id) {
            const entry = api.entry(node,index,users);
            saved.id=id;saved.entry=entry;saved.serial=JSON.stringify(entry);saved.dirty=false;
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
