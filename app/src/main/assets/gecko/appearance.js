/* Select the website theme, with a bounded color-only compatibility surface. */
(() => {
  'use strict';
  if (location.origin !== 'https://chatgpt.com' || window.top !== window) {
    globalThis.PocketAppearance = Object.freeze({apply: () => false, synchronize: () => false});
    return;
  }
  let selected = null, nativeSelected = false, observedRoot = null, suspended = false;
  let active = null, sampleTimer = 0, frame = 0, samplesLeft = 0;
  let compatibilitySheet = null, compatibilityStyle = null, compatibilityTried = false;
  let compatibilityRoot = null, compatibilitySurface = null;
  const compatibilityAttribute = 'data-pocket-appearance-compat';
  const composerAttribute = 'data-pocket-appearance-composer';
  const composerSelector = '#prompt-textarea,textarea[data-testid="chat-input"],[contenteditable="true"][role="textbox"]';
  const compatibilityCss = [['dark', '#181818', '#242424', '#eeeeee', '#c3c3c3', '#4a4a4a'],
    ['light', '#ffffff', '#f4f4f4', '#171717', '#555555', '#d0d0d0']].map(([name, bg, secondary, fg, muted, border]) => {
    const root = 'html[' + compatibilityAttribute + '="' + name + '"]';
    const tokens = {'--bg-primary': bg, '--bg-secondary': secondary, '--bg-tertiary': secondary,
      '--main-surface-primary': bg, '--main-surface-secondary': secondary, '--main-surface-tertiary': secondary,
      '--text-primary': fg, '--text-secondary': muted, '--text-tertiary': muted,
      '--border-light': border, '--border-medium': border, '--border-heavy': border};
    const surfaces = [root, root + ' body', root + ' main', root + ' [role="main"]', root + ' header'];
    const composers = [root + ' [' + composerAttribute + ']', ...composerSelector.split(',').map(selector => root + ' ' + selector)];
    return [...surfaces, ...composers].join(',') + '{' + Object.entries(tokens).map(([key, value]) => key + ':' + value + '!important').join(';') + '}' +
      surfaces.join(',') +
      '{background-color:' + bg + '!important;color:' + fg + '!important}' +
      composers.join(',') +
      '{background-color:' + secondary + '!important;color:' + fg + '!important;border-color:' + border + '!important}';
  }).join('\n');
  const retireCompatibility = () => {
    compatibilityRoot?.removeAttribute(compatibilityAttribute);
    compatibilitySurface?.removeAttribute(composerAttribute);
    document.documentElement?.removeAttribute?.(compatibilityAttribute);
    document.querySelector?.('[' + composerAttribute + ']')?.removeAttribute(composerAttribute);
    compatibilityRoot = compatibilitySurface = null;
  };
  const compatibilityApplied = () => !!compatibilityRoot && compatibilityRoot === document.documentElement &&
    compatibilityRoot.getAttribute(compatibilityAttribute) === (selected ? 'dark' : 'light');
  const ensureCompatibilitySheet = () => {
    if (compatibilitySheet) {
      try {
        if (!document.adoptedStyleSheets.includes(compatibilitySheet)) document.adoptedStyleSheets = [...document.adoptedStyleSheets, compatibilitySheet];
        return true;
      } catch (_) { return false; }
    }
    if (!compatibilityTried) {
      compatibilityTried = true;
      try {
        if (typeof CSSStyleSheet === 'function' && 'adoptedStyleSheets' in document) {
          const sheet = new CSSStyleSheet(); sheet.replaceSync(compatibilityCss);
          document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
          compatibilitySheet = sheet; return true;
        }
      } catch (_) {}
    }
    try {
      if (compatibilityStyle && !compatibilityStyle.isConnected) {
        const restored = document.querySelector('style[data-pocket-appearance-sheet]');
        if (restored?.textContent === compatibilityCss) compatibilityStyle = restored;
      }
      if (!compatibilityStyle) {
        compatibilityStyle = document.createElement('style'); compatibilityStyle.textContent = compatibilityCss;
        compatibilityStyle.setAttribute('data-pocket-appearance-sheet', '');
        // Reuse this page's own CSP nonce; never expose it in a receipt.
        const sources = document.querySelectorAll('style[nonce],script[nonce]');
        for (let i = 0; i < Math.min(sources.length, 32); i++) {
          const nonce = sources[i].nonce;
          if (typeof nonce === 'string' && nonce) { compatibilityStyle.nonce = nonce; break; }
        }
      }
      if (!compatibilityStyle.isConnected) (document.head || document.documentElement).appendChild(compatibilityStyle);
      return true;
    } catch (_) { return false; }
  };
  const markComposerSurface = () => {
    const composer = document.querySelector(composerSelector);
    const surface = composer?.closest('#composer-background,[data-testid="composer"],[data-testid="composer-background"],form') || composer?.parentElement;
    if (surface !== compatibilitySurface) compatibilitySurface?.removeAttribute(composerAttribute);
    compatibilitySurface = surface || null;
    if (surface && !surface.hasAttribute(composerAttribute)) surface.setAttribute(composerAttribute, '');
  };
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
    if (selected !== dark) retireCompatibility();
    selected = dark;
    if (suspended) return false;
    const root = typeof document === 'undefined' ? null : document.documentElement;
    if (!root) { lastApply = {attributesApplied: false, storage: 'unavailable', reason: 'root-unavailable'}; return false; }
    if (root !== observedRoot) {
      // Root replacement keeps an already measured mode in this document.
      // It does not create another sheet or repeat provider notifications.
      const mode = compatibilityRoot?.getAttribute(compatibilityAttribute);
      compatibilityRoot?.removeAttribute(compatibilityAttribute);
      compatibilitySurface?.removeAttribute(composerAttribute);
      compatibilityRoot = compatibilitySurface = null;
      if (mode === (dark ? 'dark' : 'light') && ensureCompatibilitySheet()) {
        compatibilityRoot = root;
        if (root.getAttribute(compatibilityAttribute) !== mode) root.setAttribute(compatibilityAttribute, mode);
        markComposerSurface();
      } else root.removeAttribute?.(compatibilityAttribute);
      rootObserver?.disconnect(); observedRoot = root;
      rootObserver?.observe(root, {attributes: true, attributeFilter: ['class', 'style', 'data-theme']});
    }
    const name = dark ? 'dark' : 'light';
    let storage = 'unavailable', attributesApplied = false, reason = '', oldTheme = null, storageArea = null;
    try {
      storageArea = localStorage; oldTheme = storageArea.getItem('theme');
      if (oldTheme === name) storage = 'unchanged';
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
      const dataTheme = typeof root.getAttribute === 'function' ? root.getAttribute('data-theme') : null;
      if (['light', 'dark', 'system'].includes(dataTheme) && dataTheme !== name) root.setAttribute('data-theme', name);
      // A native command is an explicit same-window provider notification,
      // including an already persisted choice. Observer repair never emits it.
      if (fromNative && typeof StorageEvent === 'function' && typeof window.dispatchEvent === 'function') {
        try { window.dispatchEvent(new StorageEvent('storage', {key: 'theme', oldValue: oldTheme, newValue: name,
          storageArea, url: typeof location.href === 'string' ? location.href : location.origin})); } catch (_) {}
      }
      attributesApplied = root.classList.contains(name) && !root.classList.contains(dark ? 'light' : 'dark') && root.style.colorScheme === name;
    } catch (_) { reason = 'attribute-write-failed'; }
    lastApply = {attributesApplied, storage, reason, compatibilityApplied: compatibilityApplied()};
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
  const styleReader = () => {
    const cache = new Map(); let remaining = 512;
    return element => {
      if (cache.has(element)) return cache.get(element);
      if (remaining <= 0) return null;
      remaining--;
      const style = getComputedStyle(element); cache.set(element, style); return style;
    };
  };
  const background = (element, read) => {
    let color = [0, 0, 0, 0], node = element;
    // Unknown canvas color stays unavailable; never infer it from the requested theme.
    for (let depth = 0; node && depth < 256 && color[3] < .999; depth++, node = node.parentElement) {
      const style = read(node);
      // Images/gradients paint above backgroundColor; it cannot prove their
      // actual color, including through a transparent descendant.
      if (style?.backgroundImage && style.backgroundImage !== 'none') return null;
      const behind = style && rgba(style.backgroundColor);
      if (!behind) return null;
      const alpha = color[3] + behind[3] * (1 - color[3]);
      if (alpha) color = [0, 1, 2].map(i => (color[i] * color[3] + behind[i] * behind[3] * (1 - color[3])) / alpha).concat(alpha);
    }
    return color[3] >= .999 ? color : null;
  };
  const opaqueAncestors = (element, read) => {
    let node = element;
    for (let depth = 0; node && depth < 256; depth++, node = node.parentElement) {
      const style = read(node); if (!style) return false;
      const opacity = style.opacity === '' ? 1 : Number(style.opacity);
      if (style.display === 'none' || style.visibility === 'hidden' || !Number.isFinite(opacity) || opacity < .999) return false;
    }
    return !node;
  };
  const painted = (element, read) => {
    const rect = element.getBoundingClientRect(), viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    const right = left + (viewport?.width || window.innerWidth), bottom = top + (viewport?.height || window.innerHeight);
    const x1 = Math.max(left, rect.left), y1 = Math.max(top, rect.top), x2 = Math.min(right, rect.right), y2 = Math.min(bottom, rect.bottom);
    if (!(x2 > x1 && y2 > y1)) return {visible: false, element};
    // Translucent groups cannot be measured from their own background alone.
    if (!opaqueAncestors(element, read) || typeof document.elementFromPoint !== 'function') return {visible: false, element};
    const hit = document.elementFromPoint((x1 + x2) / 2, (y1 + y2) / 2);
    return hit && (hit === element || element.contains(hit)) && (hit === element || opaqueAncestors(hit, read)) ? {visible: true, element: hit} : {visible: false, element};
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
      let read = styleReader();
      if (!compatibilityApplied() && document.body) {
        const rootColor = background(document.documentElement, read), bodyColor = background(document.body, read);
        const opposite = color => color && (request.dark ? luminance(color) > .5 : luminance(color) < .35);
        if (opposite(rootColor) && opposite(bodyColor) && ensureCompatibilitySheet()) {
          compatibilityRoot = document.documentElement;
          compatibilityRoot.setAttribute(compatibilityAttribute, request.dark ? 'dark' : 'light');
          markComposerSurface(); read = styleReader();
        }
      } else if (compatibilityApplied()) { ensureCompatibilitySheet(); markComposerSurface(); read = styleReader(); }
      const candidates = [['root', document.documentElement], ['body', document.body], ['main', document.querySelector('main,[role="main"]')],
        ['composer', document.querySelector(composerSelector)]];
      for (const [region, element] of candidates) {
        if (!element) continue;
        const chatRegion = region === 'main' || region === 'composer';
        const paint = chatRegion ? painted(element, read) : {visible: true, element};
        const style = read(paint.element); if (!style) return {samples, colorStatus: 'unavailable', reason: 'color-unavailable'};
        const bg = background(paint.element, read), fg = rgba(style.color);
        const composedForeground = bg && fg ? fg.slice(0, 3).map((channel, i) => channel * fg[3] + bg[i] * (1 - fg[3])) : null;
        const visible = paint.visible;
        samples.push({region, visible, background: safeColor(style.backgroundColor), foreground: safeColor(style.color),
          backgroundLuminance: bg ? luminance(bg) : null, foregroundLuminance: composedForeground ? luminance(composedForeground) : null});
      }
      const chat = samples.filter(sample => sample.region === 'main' || sample.region === 'composer');
      const known = chat.length > 0 && chat.every(sample => sample.visible && sample.backgroundLuminance !== null && sample.foregroundLuminance !== null);
      const direction = known && chat.every(sample => request.dark ? sample.backgroundLuminance < .35 : sample.backgroundLuminance > .5);
      const contrast = known && chat.every(sample => (Math.max(sample.backgroundLuminance, sample.foregroundLuminance) + .05) /
        (Math.min(sample.backgroundLuminance, sample.foregroundLuminance) + .05) >= 3);
      return {samples, colorStatus: !known ? 'unavailable' : direction && contrast ? 'verified' : 'mismatch',
        reason: !chat.length ? 'chat-region-unavailable' : !known ? 'color-unavailable' : !direction ? 'color-mismatch' : !contrast ? 'color-contrast' : ''};
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
        emit(request, {stage: 'observed', attributesApplied, storage: saved.storage, ...colors, compatibilityApplied: compatibilityApplied(),
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
