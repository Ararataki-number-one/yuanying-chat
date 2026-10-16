/* Choose ChatGPT's existing theme; never replace its DOM, stylesheet or input. */
(() => {
  'use strict';
  let selected = null;
  const apply = dark => {
    if (location.origin !== 'https://chatgpt.com' || window.top !== window || typeof dark !== 'boolean') return false;
    selected = dark;
    const root = document.documentElement;
    if (!root) return false;
    const name = dark ? 'dark' : 'light';
    // The website reads this same appearance preference during hydration/navigation.
    // No login, request, draft, or other storage key is read or changed.
    try { if (localStorage.getItem('theme') !== name) localStorage.setItem('theme', name); } catch (_) {}
    root.classList.toggle('dark', dark);
    root.classList.toggle('light', !dark);
    root.style.colorScheme = name;
    return true;
  };
  const restore = () => { if (selected !== null) apply(selected); };
  document.addEventListener('DOMContentLoaded', restore, {once: true});
  window.addEventListener('pageshow', restore);
  globalThis.PocketAppearance = Object.freeze({apply});
})();
