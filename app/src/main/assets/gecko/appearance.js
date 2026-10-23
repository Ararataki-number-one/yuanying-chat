/* Choose ChatGPT's existing theme; never replace its DOM, stylesheet or input. */
(() => {
  'use strict';
  if (location.origin !== 'https://chatgpt.com' || window.top !== window) {
    globalThis.PocketAppearance = Object.freeze({apply: () => false});
    return;
  }
  let selected = null, nativeSelected = false;
  let observedRoot = null, suspended = false;
  const restore = () => { if (!suspended && selected !== null) apply(selected, false); };
  // Watch only the theme attributes, never the streaming message subtree.
  const rootObserver = typeof MutationObserver === 'function' ? new MutationObserver(restore) : null;
  const documentObserver = typeof MutationObserver === 'function' ? new MutationObserver(restore) : null;
  const apply = (dark, fromNative = true) => {
    if (typeof dark !== 'boolean') return false;
    if (fromNative) nativeSelected = true;
    selected = dark;
    if (suspended) return false;
    const root = document.documentElement;
    if (!root) return false;
    if (root !== observedRoot) {
      rootObserver?.disconnect();
      observedRoot = root;
      rootObserver?.observe(root, {attributes: true, attributeFilter: ['class', 'style']});
    }
    const name = dark ? 'dark' : 'light';
    // The website reads this same appearance preference during hydration/navigation.
    // No login, request, draft, or other storage key is read or changed.
    try { if (localStorage.getItem('theme') !== name) localStorage.setItem('theme', name); } catch (_) {}
    // Idempotent writes prevent our observer from creating a mutation loop.
    if (root.classList.contains('dark') !== dark) root.classList.toggle('dark', dark);
    if (root.classList.contains('light') === dark) root.classList.toggle('light', !dark);
    if (root.style.colorScheme !== name) root.style.colorScheme = name;
    return true;
  };
  const resume = () => {
    suspended = false;
    // document_start can precede <html>; also handles a replaced root.
    documentObserver?.observe(document, {childList: true});
    restore();
  };
  document.addEventListener('DOMContentLoaded', restore, {once: true});
  window.addEventListener('pageshow', resume);
  window.addEventListener('pagehide', () => {
    suspended = true;
    rootObserver?.disconnect();
    documentObserver?.disconnect();
    observedRoot = null;
  });
  globalThis.PocketAppearance = Object.freeze({apply});
  // Gecko's preference is set by the app before navigation. Apply it before the
  // native port handshake so a persisted website light theme cannot win startup.
  if (typeof matchMedia === 'function') {
    const scheme = matchMedia('(prefers-color-scheme: dark)');
    // Privacy modes can report a light media query even while the app explicitly
    // requests dark. Once received, the native appearance owns this document.
    scheme.addEventListener('change', event => { if (!nativeSelected) apply(event.matches, false); });
    apply(scheme.matches, false);
  }
  resume();
})();
