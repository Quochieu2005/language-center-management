import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

// Exercise the actual submit handler without introducing a DOM/test framework.
const source = ts.createSourceFile("TuitionPage.tsx", readFileSync(new URL("../src/components/admin/tuition/TuitionPage.tsx", import.meta.url), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let collect;
let restore;
function findCollect(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(source) === "collect") collect = node.initializer;
  if (ts.isFunctionDeclaration(node) && node.name?.text === "readReceiptAttempt") restore = node;
  ts.forEachChild(node, findCollect);
}
findCollect(source);
assert.ok(collect);
assert.ok(restore);
const script = ts.transpile(`${restore.getText(source)}\nglobalThis.collect = ${collect.getText(source)};`, { target: ts.ScriptTarget.ES2022 });

function handler(site, send, storage = new Map()) {
  const states = [];
  const context = {
    site, active: { site_code: site, tuition_id: `${site}-HP-000001` },
    user: { account_id: "TK" },
    sessionStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    receiptBusy: { current: false }, receiptAttempts: { current: {} },
    setReceiptSubmitting: (value) => states.push(value),
    academicsApi: { collectTuition: send }, crypto: { randomUUID },
    message: { success() {}, error() {}, warning() {} }, setModal() {}, setActive() {},
    receiptForm: { resetFields() {} }, load() {}, loadSummary() {},
    toMessage: (error) => error.message,
  };
  vm.runInNewContext(script, context);
  return { context, states };
}
const values = { amount: 200000, payment_method: "tien_mat", note: "" };

test("receipt keys fit the complete ID at short and maximum-length sites", async () => {
  for (const site of ["Q1", "Q7", "TD", "SITE123456"]) {
    let received;
    const { context } = handler(site, async (_id, _site, payload) => { received = payload; return {}; });
    await context.collect(values);
    assert.equal(`${site}-PT-${received.idempotency_key}`.length, 24);
    assert.ok(received.idempotency_key.length >= 8);
  }
});

test("retry after network failure reuses the same key and clears it only on success", async () => {
  const keys = [];
  const { context, states } = handler("Q1", async (_id, _site, payload) => {
    keys.push(payload.idempotency_key);
    if (keys.length === 1) throw new Error("Network timeout");
    return {};
  });
  await context.collect(values);
  assert.equal(Object.keys(context.receiptAttempts.current).length, 1);
  await context.collect(values);
  assert.equal(keys[0], keys[1]);
  assert.equal(Object.keys(context.receiptAttempts.current).length, 0);
  assert.deepEqual(states, [true, false, true, false]);
});

test("a second submit while the first is pending does not send another request", async () => {
  let calls = 0;
  let resolve;
  const waiting = new Promise((done) => { resolve = done; });
  const { context } = handler("Q1", async () => { calls++; await waiting; return {}; });
  const first = context.collect(values);
  await context.collect(values);
  assert.equal(calls, 1);
  resolve();
  await first;
  assert.equal(context.receiptBusy.current, false);
});

test("pending receipt survives a reload and is isolated by account", async () => {
  const storage = new Map();
  const keys = [];
  const first = handler("Q1", async (_id, _site, payload) => { keys.push(payload.idempotency_key); throw new Error("Timeout"); }, storage);
  await first.context.collect(values);
  assert.equal(storage.size, 1);
  const otherUser = handler("Q1", async (_id, _site, payload) => { keys.push(payload.idempotency_key); return {}; }, storage);
  otherUser.context.user.account_id = "OTHER";
  await otherUser.context.collect(values);
  assert.notEqual(keys[0], keys[1]);
  const reloaded = handler("Q1", async (_id, _site, payload) => { keys.push(payload.idempotency_key); return {}; }, storage);
  await reloaded.context.collect(values);
  assert.equal(keys[0], keys[2]);
  assert.equal(storage.size, 0);
});

test("unavailable or malformed session storage does not break the in-page retry", async () => {
  const keys = [];
  const { context } = handler("Q1", async (_id, _site, payload) => {
    keys.push(payload.idempotency_key);
    if (keys.length === 1) throw new Error("Timeout");
    return {};
  });
  context.sessionStorage.getItem = () => "{invalid json";
  context.sessionStorage.setItem = () => { throw new Error("Storage blocked"); };
  await context.collect(values);
  await context.collect(values);
  assert.equal(keys[0], keys[1]);
});
