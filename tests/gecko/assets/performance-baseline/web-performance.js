/* Cached, incremental observation. Does not change website layout or content. */
(() => {
  'use strict';
  window.__pocketInstallWebPerformance = api => {
    if (window.__pocketWebPerformance) return window.__pocketWebPerformance;
    const selector = '[data-message-author-role],article[data-turn],[data-chatgpt-search-unit-key],[data-content-search-unit-key]';
    const cache = new WeakMap(), sent = new Map();
    const documentId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
    let dirty = true, revision = 0, orderKey = '', lastUrl = '', lastInteraction = 0;
    const stats = {entriesBuilt:0,snapshots:0};
    function mark(node) {
      let element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      while (element) {
        const saved = cache.get(element);
        if (saved) { saved.dirty = true; dirty = true; return true; }
        if (element.matches?.(selector)) { dirty = true; return true; }
        element = element.parentElement;
      }
      return false;
    }
    new MutationObserver(records => {
      for (const record of records) {
        if (mark(record.target)) continue;
        if (record.type === 'childList') for (const node of [...record.addedNodes,...record.removedNodes]) {
          if (node.nodeType === Node.ELEMENT_NODE && (node.matches(selector) || node.querySelector(selector))) { dirty = true; break; }
        }
      }
    }).observe(document, {subtree:true,childList:true,characterData:true,attributes:true,
      attributeFilter:['data-message-id','data-chatgpt-selection-message-id','data-chatgpt-search-message-ids',
        'href','download','src','alt','aria-label','hidden','aria-hidden','data-file-name']});
    document.addEventListener('load', event => mark(event.target), true);
    for (const event of ['touchmove','pointerdown','wheel','keydown','input'])
      document.addEventListener(event, () => { lastInteraction = Date.now(); }, {capture:true,passive:true});
    const instance = {
      meta:() => ({dirty,documentId,revision,interacting:Date.now()-lastInteraction<450}),
      stats:() => ({...stats}),
      snapshot(arg) {
        stats.snapshots++;
        const nodes = api.nodes(), users = new Set(api.users()), current = [];
        const reset = arg.documentId !== documentId || arg.revision !== revision || lastUrl !== location.href;
        const changes = [], ids = new Set();
        nodes.forEach((node,index) => {
          const id = api.key(node,index); ids.add(id);
          let saved = cache.get(node);
          if (!saved || saved.dirty || saved.id !== id) {
            const entry = api.entry(node,index,users);
            saved = {id,entry,serial:JSON.stringify(entry),dirty:false};
            cache.set(node,saved);stats.entriesBuilt++;
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
