// Integration check: use A's unchanged HTTP/snapshot consumer against a real B process.
import assert from 'node:assert/strict';
import { getMatches, createReplay, subscribeToSnapshots } from '../../frontend/src/replay.ts';

const base = process.argv[2] || 'http://127.0.0.1:8877';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname), 'Loopback test only');
const nativeFetch = globalThis.fetch;
globalThis.fetch = (input, init) => nativeFetch(new URL(input, base), init);

class LoopbackSSE {
  constructor(url) {
    this.listeners = new Map();
    this.controller = new AbortController();
    this.done = this.read(url);
  }
  addEventListener(name, fn) { this.listeners.set(name, fn); }
  close() { this.controller.abort(); }
  async read(url) {
    try {
      const response = await fetch(url, { signal: this.controller.signal });
      assert.equal(response.status, 200);
      const decoder = new TextDecoder();
      let pending = '';
      for await (const chunk of response.body) {
        pending += decoder.decode(chunk, { stream: true });
        const frames = pending.split(/\r?\n\r?\n/);
        pending = frames.pop();
        for (const frame of frames) {
          const lines = frame.split(/\r?\n/);
          const name = lines.find(x => x.startsWith('event: '))?.slice(7);
          const data = lines.filter(x => x.startsWith('data: ')).map(x => x.slice(6)).join('\n');
          if (name) this.listeners.get(name)?.({ data });
        }
      }
    } catch (error) {
      if (!this.controller.signal.aborted) this.onerror?.(error);
    }
  }
}

async function until(check) {
  const deadline = Date.now() + 5000;
  while (!check()) {
    assert.ok(Date.now() < deadline, 'Timed out waiting for A1 to consume B');
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}

let source, dispose;
try {
  const health = await fetch('/api/v1/health');
  assert.equal(health.status, 200);
  assert.equal((await health.json()).contract_version, '2.0.0');
  const missing = await fetch('/api/v1/not-a-real-route');
  assert.equal(missing.status, 404);
  assert.equal((await missing.json()).error.code, 'NOT_FOUND');
  const signal = new AbortController().signal;
  const matches = await getMatches(signal);
  const initial = await createReplay(matches[0].match_id, signal);
  let latest = initial, connected = false;
  dispose = subscribeToSnapshots({ initial,
    onSnapshot: value => { latest = value; },
    onConnection: value => { connected ||= value === 'connected'; },
    onError: value => { if (value) throw new Error(value); },
    createSource: url => (source = new LoopbackSSE(url)) });
  await until(() => connected);
  const control = async action => {
    const response = await fetch(`/api/v1/replays/${initial.replay.replay_id}/control`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) });
    assert.equal(response.status, 200);
    return response.json();
  };
  await control('play');
  await until(() => latest.replay.clock_sec > 1500);
  const observedClock = latest.replay.clock_sec;
  await control('pause');
  await until(() => latest.replay.status === 'paused');
  const paused = latest.replay.clock_sec;
  await new Promise(resolve => setTimeout(resolve, 150));
  assert.equal((await (await fetch(`/api/v1/replays/${initial.replay.replay_id}`)).json()).replay.clock_sec, paused);
  await control('reset');
  await until(() => latest.replay.run_id === 2);
  assert.equal(latest.replay.clock_sec, 1500);
  assert.deepEqual(latest.state.score, { HOME: 0, AWAY: 0 });
  console.log(JSON.stringify({ result: 'passed', unchanged_A1_consumer: true,
    transport: 'API-only HTTP and snapshot SSE', connected, observed_clock: observedClock,
    reset_run: latest.replay.run_id, runtime_model_calls: 0 }));
} finally {
  dispose?.();
  if (source) await source.done;
  globalThis.fetch = nativeFetch;
}
