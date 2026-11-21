import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

// Execute the real provider callbacks with controlled network completion order.
function harness() {
  const oldUser = { slug: 'old', role: 'admin_big' };
  const states = [oldUser, false, '2099-01-01T00:00:00Z', false, 0];
  const refs = [];
  const effects = [];
  const events = {};
  let stateIndex = 0, refIndex = 0;
  const storage = new Map([['qlttnn.account-slug', 'old']]);
  class ApiError extends Error { constructor(status) { super(); this.status = status; } }
  const api = { session: async () => null, logout: async () => {}, activity: async () => ({ expires_at: states[2] }) };
  const react = {
    createContext: () => ({ Provider: 'provider' }),
    useState: () => { const i = stateIndex++; return [states[i], (v) => { states[i] = typeof v === 'function' ? v(states[i]) : v; }]; },
    useRef: (v) => { const i = refIndex++; return refs[i] ||= { current: v }; },
    useCallback: (fn) => fn, useMemo: (fn) => fn(), useEffect: (fn) => effects.push(fn),
  };
  const source = ts.transpileModule(readFileSync('src/lib/auth/session.tsx', 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, sessionStorage: { getItem: (k) => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) },
    window: { addEventListener: (k, fn) => { events[k] = fn; }, removeEventListener: () => {} },
    require: (name) => {
      if (name === 'react') return react;
      if (name === 'react/jsx-runtime') return { jsx: (_, props) => props, jsxs: (_, props) => props };
      if (name === 'next/navigation') return { useRouter: () => ({ replace: () => {} }), usePathname: () => '/admin' };
      if (name === '@/lib/api/client') return { ApiError };
      if (name === '@/lib/api/auth') return { authApi: api };
      if (name === 'antd') return {};
      throw new Error(name);
    },
  });
  const value = exports.SessionProvider({ children: null }).value;
  return { value, states, api, effects, events, ApiError };
}

test('failed logout preserves local session; successful retry clears it', async () => {
  const h = harness();
  h.api.logout = async () => { throw new Error('offline'); };
  await assert.rejects(h.value.signOut(), /offline/);
  assert.equal(h.states[0].slug, 'old');
  h.api.logout = async () => {};
  await h.value.signOut();
  assert.equal(h.states[0], null);
});

test('an anonymous session restores as signed out without an API error', async () => {
  const h = harness();
  h.effects[0]();
  await new Promise(setImmediate);
  assert.equal(h.states[0], null);
  assert.equal(h.states[1], false);
  assert.equal(h.states[3], false);
});

test('a late anonymous session cannot clear a newer login', async () => {
  const h = harness();
  let resolveSession;
  h.api.session = () => new Promise((resolve) => { resolveSession = resolve; });
  h.effects[0]();
  h.value.signIn({ slug: 'new', role: 'admin_big' }, '2099-02-01T00:00:00Z');
  resolveSession(null);
  await new Promise(setImmediate);
  assert.equal(h.states[0].slug, 'new');
});

test('already expired logout clears local state', async () => {
  const h = harness();
  h.api.logout = async () => { throw new h.ApiError(401); };
  await h.value.signOut();
  assert.equal(h.states[0], null);
});

test('late activity 401 cannot clear a newer login', async () => {
  const h = harness();
  let reject;
  h.api.activity = () => new Promise((_, fail) => { reject = fail; });
  h.effects[2]();
  h.events.pointerdown();
  h.value.signIn({ slug: 'new', role: 'admin_big' }, '2099-02-01T00:00:00Z');
  reject(new h.ApiError(401));
  await new Promise(setImmediate);
  assert.equal(h.states[0].slug, 'new');
});
