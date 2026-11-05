'use strict';
// A bootstrap signal only. Do not read or replace Date, Intl, navigator or any
// Worker global; the independent fixture observes untouched native APIs later.
browser.runtime.sendMessage({kind: 'timezoneProbeDocumentReady'}).catch(() => {});
