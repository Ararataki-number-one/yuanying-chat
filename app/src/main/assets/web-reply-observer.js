/* Observe trusted website gestures. This module never fills, clicks or submits. */
(() => {
  'use strict';
  window.__pocketInstallWebReplyObserver = api => {
    if (window !== window.top || location.origin !== 'https://chatgpt.com' ||
        !window.PocketWebReply?.postMessage) return false;
    if (window.__pocketWebReplyObserver) return true;
    const uuid = () => typeof crypto.randomUUID === 'function' ? crypto.randomUUID() :
      [...crypto.getRandomValues(new Uint8Array(16))].map(n => n.toString(16).padStart(2, '0')).join('');
    const documentId = uuid();
    let attempt = null, scheduled = false, timer = null;
    let readyRoute = '', readinessScheduled = false;
    const normalized = text => String(text || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
    const address = url => new URL(url).origin + new URL(url).pathname;
    const stable = key => /^(id|unit):/.test(key);
    const newChat = url => /^\/(?:g\/[^/]+\/?)?$/.test(new URL(url).pathname);
    const sameRoute = (from, to) => address(from) === address(to) ||
      (newChat(from) && /^\/(?:g\/[^/]+\/)?c\/[^/]+$/.test(new URL(to).pathname));
    function emit(type, data = {}) {
      try { window.PocketWebReply.postMessage(JSON.stringify({type, documentId, url:location.href, ...data})); }
      catch (_) { /* No website behavior depends on a host callback. */ }
    }
    function invalidate(reason) {
      if (!attempt || attempt.ended || attempt.userKey) return;
      attempt.ended = true;
      clearTimeout(timer);
      emit('uncertain', {token:attempt.token, reason});
    }
    function check() {
      scheduled = false;
      const current = attempt;
      if (!current || current.ended || current.userKey) return;
      if (!sameRoute(current.url, location.href)) { invalidate('网页已切换到其他对话'); return; }
      const users = api.messages('user');
      const fresh = users.map((node, index) => ({node, key:api.key(node, index)}))
        .filter(item => !current.before.has(item.key));
      if (fresh.length > 1) { invalidate('同时出现多条消息，无法确定本次发送'); return; }
      if (fresh.length !== 1) return;
      const item = fresh[0];
      if (item.node !== users[users.length - 1]) { invalidate('新出现的消息不是当前最后一条提问'); return; }
      // Position-derived identities cannot safely survive a reload or branch change.
      if (!stable(item.key)) { invalidate('网页没有提供可持续核对的消息标识'); return; }
      const actual = api.userText(item.node);
      if (current.prompt.trim() && normalized(actual) !== normalized(current.prompt)) return;
      if (!current.prompt.trim() && !api.busy()) return;
      current.userKey = item.key;
      clearTimeout(timer);
      emit('bound', {token:current.token, userKey:item.key, prompt:actual});
    }
    function schedule() {
      scheduleReadiness();
      if (!attempt || attempt.ended || attempt.userKey || scheduled) return;
      scheduled = true;
      setTimeout(check, 30);
    }
    // One readiness signal per route; the host still checks composer and transcript.
    // This can run before window.load when an unrelated resource is slow.
    function scheduleReadiness() {
      if (readinessScheduled || readyRoute === address(location.href)) return;
      readinessScheduled = true;
      setTimeout(() => {
        readinessScheduled = false;
        if (!api.composer()) return;
        if (!newChat(location.href) && !api.hasMessages()) return;
        readyRoute = address(location.href);
        emit('ready');
      }, 50);
    }
    function begin() {
      const input = api.composer(), send = api.sendButton();
      if (!input || !send || send.disabled || send.getAttribute('aria-disabled') === 'true' || api.busy()) return;
      const prompt = api.draft(input), beforeKeys = api.messages('user').map(api.key);
      if (prompt.length > 300000 || beforeKeys.length > 4000) return;
      const now = Date.now();
      // Enter can also cause a trusted form submit. Treat both as one gesture.
      if (attempt && !attempt.ended && !attempt.userKey && now - attempt.started < 700 &&
          attempt.url === location.href && attempt.prompt === prompt &&
          JSON.stringify(attempt.beforeKeys) === JSON.stringify(beforeKeys)) return;
      clearTimeout(timer);
      attempt = {token:uuid(), url:location.href, prompt, beforeKeys,
        before:new Set(beforeKeys), started:now, userKey:'', ended:false};
      emit('intent', {token:attempt.token, prompt, beforeKeys, capturedAt:now});
      timer = setTimeout(() => invalidate('未能确认网页接收了这次操作，请核对原消息'), 45000);
      schedule();
    }
    document.addEventListener('click', event => {
      if (!event.isTrusted) return;
      const target = event.target instanceof Element ? event.target : event.target?.parentElement;
      const button = target?.closest('button,[role="button"]');
      const text = (button?.getAttribute('aria-label') || button?.innerText || '').trim();
      if (button && (button.matches('[data-testid="stop-button"]') ||
          /^(停止|停止生成|Stop|Stop generating|Stop streaming)$/i.test(text))) {
        if (attempt) attempt.ended = true;
        clearTimeout(timer);
        const users = api.messages('user');
        emit('stop', {token:attempt?.token || '', userKey:users.length ? api.key(users.at(-1), users.length - 1) : ''});
        return;
      }
      if (button && button === api.sendButton()) { begin(); return; }
      const link = target?.closest('a[href]');
      if (link && attempt && !attempt.userKey) {
        try { if (address(link.href) !== address(location.href)) invalidate('发送核对期间打开了其他页面'); } catch (_) {}
      }
    }, true);
    document.addEventListener('keydown', event => {
      if (!event.isTrusted || event.isComposing || event.keyCode === 229 || event.repeat ||
          event.key !== 'Enter' || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
      const input = api.composer();
      if (input && (input === event.target || input.contains(event.target))) begin();
    }, true);
    // A script-triggered requestSubmit() can produce an isTrusted submit event.
    // Only a trusted click/keydown is evidence of the user's send gesture.
    window.addEventListener('popstate', () => invalidate('发送核对期间切换了网页历史'));
    window.addEventListener('pagehide', () => invalidate('页面已离开，原发送结果需要核对'));
    new MutationObserver(schedule).observe(document, {subtree:true, childList:true, characterData:true, attributes:true});
    document.addEventListener('DOMContentLoaded', scheduleReadiness, {once:true});
    scheduleReadiness();
    window.__pocketWebReplyObserver = Object.freeze({documentId,lastGestureAt:()=>attempt?.started||0});
    return true;
  };
})();
