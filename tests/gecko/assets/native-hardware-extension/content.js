'use strict';
// Bootstrap ownership only. The fixture's separate first-party script measures
// native navigator values; this content script does not read or replace them.
browser.runtime.sendMessage({kind: 'hardwareProbeDocumentReady'}).catch(() => {});
