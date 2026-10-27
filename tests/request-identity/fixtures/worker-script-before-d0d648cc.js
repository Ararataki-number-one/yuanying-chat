function javascriptObservation() {
  const text = value => typeof value === 'string' ? value.slice(0, 2048) : '';
  return {ua: text(navigator.userAgent), language: text(navigator.language),
    languages: Array.from(navigator.languages || []).slice(0, 8).map(text)};
}

function workerScript(nonce, protocol) {
  const js = javascriptObservation();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  const target = new URL('observe', location.href);
  target.search = '?nonce=' + nonce + '&source=worker';
  fetch(target, {credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error',
    cache: 'no-store', mode: 'same-origin', signal: controller.signal})
    .then(async response => {
      const value = await response.json();
      const ok = response.ok && value.schema === 1 && value.protocol === protocol &&
        value.nonce === nonce && value.source === 'worker-fetch' && value.ok === true;
      postMessage({schema: 1, protocol, nonce, status: ok ? 'complete' : 'failed', js});
    }).catch(() => postMessage({schema: 1, protocol, nonce, status: 'failed', js}))
    .finally(() => clearTimeout(timer));
}
