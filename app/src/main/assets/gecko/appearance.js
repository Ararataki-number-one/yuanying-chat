/* Select the website's existing theme and report observations, never replace its CSS or inputs. */
(() => {
  'use strict';
  if (location.origin !== 'https://chatgpt.com' || window.top !== window) {
    globalThis.PocketAppearance = Object.freeze({apply: () => false, synchronize: () => false});
    return;
  }
  let selected = null, nativeSelected = false, observedRoot = null, suspended = false;
  let active = null, sampleTimer = 0, frame = 0, samplesLeft = 0;
  const cancelSample = () => {
    if (sampleTimer) clearTimeout(sampleTimer);
    if (frame && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(frame);
    sampleTimer = frame = 0;
  };
  const emit = (request, value) => {
    if (request !== active || suspended) return;
    try { request.report({kind: 'appearanceReceipt', protocol: 1, documentId: request.documentId,
      version: request.version, dark: request.dark, ...value}); } catch (_) {}
  };
  const restore = () => {
    if (!suspended && selected !== null) { apply(selected, false); scheduleSample(); }
  };
  // Only root attributes/document-root replacement are watched, not streamed messages.
  const rootObserver = typeof MutationObserver === 'function' ? new MutationObserver(restore) : null;
  const documentObserver = typeof MutationObserver === 'function' ? new MutationObserver(restore) : null;
  let lastApply = {attributesApplied: false, storage: 'unavailable', reason: 'root-unavailable'};
  const apply = (dark, fromNative = true) => {
    if (typeof dark !== 'boolean') return false;
    if (fromNative) nativeSelected = true;
    selected = dark;
    if (suspended) return false;
    const root = typeof document === 'undefined' ? null : document.documentElement;
    if (!root) { lastApply = {attributesApplied: false, storage: 'unavailable', reason: 'root-unavailable'}; return false; }
    if (root !== observedRoot) {
      rootObserver?.disconnect(); observedRoot = root;
      rootObserver?.observe(root, {attributes: true, attributeFilter: ['class', 'style']});
    }
    const name = dark ? 'dark' : 'light';
    let storage = 'unavailable', attributesApplied = false, reason = '';
    try {
      if (localStorage.getItem('theme') === name) storage = 'unchanged';
      else {
        try { localStorage.setItem('theme', name); storage = localStorage.getItem('theme') === name ? 'written' : 'failed'; }
        catch (_) { storage = 'failed'; }
      }
    } catch (_) { storage = 'unavailable'; }
    if (storage === 'failed') reason = 'storage-write-failed';
    else if (storage === 'unavailable') reason = 'storage-unavailable';
    try {
      if (root.classList.contains('dark') !== dark) root.classList.toggle('dark', dark);
      if (root.classList.contains('light') === dark) root.classList.toggle('light', !dark);
      if (root.style.colorScheme !== name) root.style.colorScheme = name;
      attributesApplied = root.classList.contains(name) && !root.classList.contains(dark ? 'light' : 'dark') && root.style.colorScheme === name;
    } catch (_) { reason = 'attribute-write-failed'; }
    lastApply = {attributesApplied, storage, reason};
    // Legacy helper confirms settings writes only. Native confirmation uses synchronize's colors.
    return attributesApplied && (storage === 'written' || storage === 'unchanged');
  };
  const rgba = value => {
    if (value === 'transparent') return [0, 0, 0, 0];
    const match = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)$/.exec(value);
    if (match) {
      const color = [+match[1] / 255, +match[2] / 255, +match[3] / 255, match[4] === undefined ? 1 : +match[4]];
      return color.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1) ? color : null;
    }
    const srgb = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)$/.exec(value);
    if (!srgb) return null;
    const color = [+srgb[1], +srgb[2], +srgb[3], srgb[4] === undefined ? 1 : +srgb[4]];
    return color.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1) ? color : null;
  };
  const luminance = color => {
    const c = color.slice(0, 3).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
  };
  const safeColor = value => /^(?:transparent|rgba?\([\d.,% /]+\)|color\(srgb [\d.% /]+\)|okl(?:ab|ch)\([\d.% /-]+\))$/.test(value) && value.length <= 96 ? value : '';
  const background = element => {
    let color = [0, 0, 0, 0], node = element;
    // Unknown canvas color stays unavailable; never infer it from the requested theme.
    for (let depth = 0; node && depth < 16 && color[3] < .999; depth++, node = node.parentElement) {
      const behind = rgba(getComputedStyle(node).backgroundColor);
      if (!behind) return null;
      const alpha = color[3] + behind[3] * (1 - color[3]);
      if (alpha) color = [0, 1, 2].map(i => (color[i] * color[3] + behind[i] * behind[3] * (1 - color[3])) / alpha).concat(alpha);
    }
    return color[3] >= .999 ? color : null;
  };
  const opaqueAncestors = element => {
    let node = element;
    for (let depth = 0; node && depth < 16; depth++, node = node.parentElement) {
      const style = getComputedStyle(node), opacity = style.opacity === '' ? 1 : Number(style.opacity);
      if (style.display === 'none' || style.visibility === 'hidden' || !Number.isFinite(opacity) || opacity < .999) return false;
    }
    return !node;
  };
  const painted = element => {
    const rect = element.getBoundingClientRect(), viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    const right = left + (viewport?.width || window.innerWidth), bottom = top + (viewport?.height || window.innerHeight);
    const x1 = Math.max(left, rect.left), y1 = Math.max(top, rect.top), x2 = Math.min(right, rect.right), y2 = Math.min(bottom, rect.bottom);
    if (!(x2 > x1 && y2 > y1)) return {visible: false, element};
    // Translucent groups cannot be measured from their own background alone.
    if (!opaqueAncestors(element) || typeof document.elementFromPoint !== 'function') return {visible: false, element};
    const hit = document.elementFromPoint((x1 + x2) / 2, (y1 + y2) / 2);
    return hit && (hit === element || element.contains(hit)) && (hit === element || opaqueAncestors(hit)) ? {visible: true, element: hit} : {visible: false, element};
  };
  const preference = request => {
    try {
      if (localStorage.getItem('theme') === (request.dark ? 'dark' : 'light')) return {storage: lastApply.storage === 'written' ? 'written' : 'unchanged', reason: ''};
      return {storage: 'failed', reason: lastApply.storage === 'failed' && lastApply.reason === 'storage-write-failed' ? 'storage-write-failed' : 'storage-preference-mismatch'};
    } catch (_) { return {storage: 'unavailable', reason: 'storage-unavailable'}; }
  };
  const observe = request => {
    const samples = [];
    if (document.visibilityState === 'hidden') return {samples, colorStatus: 'unavailable', reason: 'page-hidden'};
    try {
      const candidates = [['root', document.documentElement], ['body', document.body], ['main', document.querySelector('main,[role="main"]')],
        ['composer', document.querySelector('#prompt-textarea,textarea[data-testid="chat-input"],[contenteditable="true"][role="textbox"]')]];
      for (const [region, element] of candidates) {
        if (!element) continue;
        const chatRegion = region === 'main' || region === 'composer';
        const paint = chatRegion ? painted(element) : {visible: true, element};
        const style = getComputedStyle(paint.element), bg = background(paint.element), fg = rgba(style.color);
        const visible = paint.visible;
        samples.push({region, visible, background: safeColor(style.backgroundColor), foreground: safeColor(style.color),
          backgroundLuminance: bg ? luminance(bg) : null, foregroundLuminance: fg && fg[3] >= .999 ? luminance(fg) : null});
      }
      const chat = samples.filter(sample => sample.region === 'main' || sample.region === 'composer');
      const known = chat.length > 0 && chat.every(sample => sample.visible && sample.backgroundLuminance !== null);
      const correct = known && chat.every(sample => request.dark ? sample.backgroundLuminance < .35 : sample.backgroundLuminance > .5);
      return {samples, colorStatus: !known ? 'unavailable' : correct ? 'verified' : 'mismatch',
        reason: !chat.length ? 'chat-region-unavailable' : !known ? 'color-unavailable' : !correct ? 'color-mismatch' : ''};
    } catch (_) { return {samples: [], colorStatus: 'unavailable', reason: 'color-unavailable'}; }
  };
  function scheduleSample() {
    if (!active || suspended || !samplesLeft || sampleTimer || frame) return;
    const request = active;
    sampleTimer = setTimeout(() => {
      sampleTimer = 0;
      const measure = () => {
        frame = 0;
        if (request !== active || suspended || !samplesLeft) return;
        samplesLeft--;
        const saved = preference(request), colors = observe(request), root = document.documentElement;
        const name = request.dark ? 'dark' : 'light';
        const attributesApplied = !!root && root.classList.contains(name) && !root.classList.contains(request.dark ? 'light' : 'dark') && root.style.colorScheme === name;
        emit(request, {stage: 'observed', attributesApplied, storage: saved.storage, ...colors,
          reason: colors.reason || saved.reason || (attributesApplied ? '' : 'attribute-write-failed')});
      };
      if (document.visibilityState !== 'hidden' && typeof requestAnimationFrame === 'function') frame = requestAnimationFrame(measure); else measure();
    }, 350);
  }
  const synchronize = (message, report) => {
    if (!message || message.protocol !== 1 || typeof message.dark !== 'boolean' || typeof report !== 'function' ||
      typeof message.documentId !== 'string' || !/^[a-zA-Z0-9-]{16,80}$/.test(message.documentId) ||
      !Number.isSafeInteger(message.version) || message.version < 1 || message.version > 2147483647 || suspended) return false;
    if (active && (active.documentId !== message.documentId || message.version <= active.version)) return false;
    cancelSample(); active = {documentId: message.documentId, version: message.version, dark: message.dark, report}; samplesLeft = 3;
    emit(active, {stage: 'received'});
    apply(message.dark);
    emit(active, {stage: 'applied', ...lastApply});
    scheduleSample(); return true;
  };
  const resume = () => {
    suspended = false;
    documentObserver?.observe(document, {childList: true});
    restore();
  };
  document.addEventListener('DOMContentLoaded', restore, {once: true});
  document.addEventListener('load', event => { if (event.target?.tagName === 'LINK' && event.target.rel === 'stylesheet') scheduleSample(); }, true);
  window.addEventListener('pageshow', resume);
  window.addEventListener('pagehide', () => {
    suspended = true; cancelSample(); rootObserver?.disconnect(); documentObserver?.disconnect(); observedRoot = null;
  });
  globalThis.PocketAppearance = Object.freeze({apply, synchronize});
  if (typeof matchMedia === 'function') {
    const scheme = matchMedia('(prefers-color-scheme: dark)');
    scheme.addEventListener('change', event => { if (!nativeSelected) apply(event.matches, false); });
    apply(scheme.matches, false);
  }
  resume();
})();
