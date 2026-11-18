// Execute the exact scripts emitted by the production reader, including a fetch that settles after close.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const scripts = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
assert.equal(scripts.length, 7);

function page() {
  let finishFetch, signal;
  const window = {};
  const context = vm.createContext({ window, AbortController, btoa, Uint8Array,
    fetch(url, options) {
      assert.equal(url, "blob:https://chatgpt.com/file-1");
      signal = options.signal;
      return new Promise(resolve => { finishFetch = resolve; });
    }
  });
  return {
    window, run: index => vm.runInContext(scripts[index], context),
    resolve: blob => finishFetch({ ok: true, blob: () => blob }), signal: () => signal
  };
}

async function main() {
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const bytes = Buffer.alloc(192 * 1024 + 17);
  for (let i = 0; i < bytes.length; i++) bytes[i] = i % 251;
  bytes.write("%PDF-");
  const pdf = new Blob([bytes], { type: "application/pdf" });
  const active = page();
  active.run(0);
  active.resolve(pdf);
  await tick();
  const metadata = active.run(1);
  assert.equal(metadata.ready, true);
  assert.equal(metadata.size, bytes.length);
  assert.equal(metadata.mime, pdf.type);
  const chunks = [];
  for (const request of [2, 4]) {
    active.run(request);
    let result;
    for (let reads = 0; reads < 200; reads++) {
      await tick();
      result = active.run(request + 1);
      if (typeof result.chunk === "string") break;
    }
    chunks.push(Buffer.from(result.chunk, "base64"));
    assert.equal(active.run(request + 1).chunk, undefined);
  }
  assert.deepEqual(Buffer.concat(chunks), bytes);
  active.run(6);
  assert.equal(active.signal().aborted, true);
  assert.deepEqual(Object.keys(active.window), []);
  const cancelled = page();
  cancelled.run(0);
  cancelled.run(6);
  cancelled.resolve(pdf);
  await tick();
  assert.equal(cancelled.signal().aborted, true);
  assert.deepEqual(Object.keys(cancelled.window), []);
  console.log(JSON.stringify({status:"passed", bytes:bytes.length, chunks:chunks.length, lateFetchClean:true}));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
