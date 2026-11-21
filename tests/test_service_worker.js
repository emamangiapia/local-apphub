/* Verify that the PWA never intercepts private API requests or caches the dashboard. */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const handlers = {};
const cacheLookups = [];
let offlineResponse = { status: 200, offline: true };
const source = fs.readFileSync(path.join(__dirname, "../apphub/static/sw.js"), "utf8");
const worker = {
  location: { origin: "https://pc.tailnet.ts.net" },
  addEventListener(type, callback) { handlers[type] = callback; },
};
vm.runInNewContext(source, {
  self: worker,
  URL,
  caches: {
    async match(key) { cacheLookups.push(key); return key === "/offline.html" ? offlineResponse : undefined; },
    async open() { return { async put() {}, async addAll() {} }; },
  },
  fetch: async () => { throw new Error("PC spento"); },
  Response: { error: () => ({ status: 0 }) },
});

let intercepted = false;
for (const method of ["GET", "POST"]) {
  handlers.fetch({
    request: { method, url: "https://pc.tailnet.ts.net/api/status", mode: "cors" },
    respondWith() { intercepted = true; },
  });
}
assert.equal(intercepted, false, "Le richieste API devono andare direttamente al server");

(async () => {
  let response;
  handlers.fetch({
    request: { method: "GET", url: "https://pc.tailnet.ts.net/", mode: "navigate" },
    respondWith(promise) { response = promise; },
  });
  assert.equal(await response, offlineResponse);
  assert.deepEqual(cacheLookups, ["/offline.html"]);
  console.log("PWA privacy tests: OK");
})().catch((error) => { console.error(error); process.exitCode = 1; });
