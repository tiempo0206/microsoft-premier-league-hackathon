/** Exercises the real frontend consumer against the combined B/C app, with an accelerated server clock and an explicitly offline model. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { once } from "node:events";
import { HttpEventSource } from "./http-event-source.mjs";
import {
  applyStreamMessage,
  controlReplay,
  createReplay,
  getEvents,
  getMatches,
  getReplay,
  replaceSnapshot,
  subscribeToReplay,
} from "../../frontend/src/replay.ts";
const root = fileURLToPath(new URL("../../", import.meta.url));
const python =
  process.env.MATCHMIND_PYTHON ||
  `${root}.venv/${process.platform === "win32" ? "Scripts/python.exe" : "bin/python"}`;
const code = `import socket, time, uvicorn
from ai.app import build_app
from ai.config import ModelConfig
sock=socket.socket(); sock.bind(('127.0.0.1',0))
print('PORT='+str(sock.getsockname()[1]),flush=True)
app=build_app(config=ModelConfig(),clock=lambda:time.monotonic()*5)
uvicorn.Server(uvicorn.Config(app,log_level='warning',lifespan='on')).run(sockets=[sock])
`;
const child = spawn(python, ["-u", "-c", code], {
  cwd: root,
  env: {
    ...process.env,
    MATCHMIND_MODEL_PROVIDER: "mock",
    MATCHMIND_DATA_DIR: "data/extra/showcase/press",
    MATCHMIND_SERVE_FRONTEND: "0",
    MATCHMIND_MAX_REPLAY_SESSIONS: "8",
    MATCHMIND_ANALYSIS_LIMIT_PER_HOUR: "30",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
let output = "",
  errors = "";
child.stdout.on("data", (chunk) => {
  output += chunk;
});
child.stderr.on("data", (chunk) => {
  errors += chunk;
});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function until(predicate, timeout = 10000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (await predicate()) return;
    if (child.exitCode !== null)
      throw new Error(`Probe backend exited: ${errors.slice(-2000)}`);
    await sleep(30);
  }
  throw new Error("Timed out waiting for backend state");
}
const originalFetch = globalThis.fetch;
const closers = [];
try {
  await until(() => /PORT=(\d+)/.test(output));
  const base = `http://127.0.0.1:${/PORT=(\d+)/.exec(output)[1]}`;
  await until(async () => {
    try {
      return (await originalFetch(`${base}/api/v1/health`)).ok;
    } catch {
      return false;
    }
  });
  const health = await (await originalFetch(`${base}/api/v1/health`)).json();
  assert.equal(health.model_ready, false);
  globalThis.fetch = (url, options) =>
    originalFetch(new URL(url, base), options);
  const signal = new AbortController().signal;
  const [match] = await getMatches(signal),
    events = await getEvents(match.match_id, signal);
  let view = replaceSnapshot(null, await createReplay(match.match_id, signal));
  const other = await createReplay(match.match_id, signal);
  const kinds = new Set();
  let snapshotCount = 0;
  function connect() {
    return subscribeToReplay({
      initial: view.snapshot,
      getCurrent: () => view.snapshot,
      onMessage: (message) => {
        kinds.add(message.kind);
        if (message.kind === "snapshot") snapshotCount++;
        view = applyStreamMessage(view, message);
      },
      onConnection: () => {},
      onError: () => {},
      createSource: (url) => new HttpEventSource(url),
    });
  }
  let close = connect();
  closers.push(() => close());
  await until(() => kinds.has("snapshot"));
  view = replaceSnapshot(
    view,
    await controlReplay(
      view.snapshot,
      { action: "set_speed", speed: 10 },
      crypto.randomUUID(),
      signal,
    ),
  );
  view = replaceSnapshot(
    view,
    await controlReplay(
      view.snapshot,
      { action: "play" },
      crypto.randomUUID(),
      signal,
    ),
  );
  await until(() => view.snapshot.replay.clock_sec >= 1510);
  view = replaceSnapshot(
    view,
    await controlReplay(
      view.snapshot,
      { action: "pause" },
      crypto.randomUUID(),
      signal,
    ),
  );
  const paused = view.snapshot.replay.clock_sec;
  await sleep(250);
  assert.equal(
    (await getReplay(view.snapshot, signal)).replay.clock_sec,
    paused,
  );
  assert.equal(view.snapshot.replay.status, "paused");
  view = replaceSnapshot(
    view,
    await controlReplay(
      view.snapshot,
      { action: "play" },
      crypto.randomUUID(),
      signal,
    ),
  );
  await until(() => view.snapshot.insights.length === 1);
  view = replaceSnapshot(
    view,
    await controlReplay(
      view.snapshot,
      { action: "pause" },
      crypto.randomUUID(),
      signal,
    ),
  );
  const insight = view.snapshot.insights[0];
  assert.equal(insight.generation.mode, "rule_fallback");
  assert.equal(insight.verification.method, "code_only");
  assert.equal(insight.metrics.high_recoveries, 3);
  assert.equal(insight.metrics.linked_shots, 2);
  assert.notEqual(insight.narratives.casual, insight.narratives.analyst);
  assert(
    insight.evidence_event_ids.every((id) =>
      events.some((event) => event.event_id === id),
    ),
  );
  const stats = await (
    await fetch(
      `/api/v1/matches/${match.match_id}/stats?at_sec=${view.snapshot.replay.clock_sec}`,
    )
  ).json();
  assert.deepEqual(view.snapshot.state, stats);
  const untouched = await getReplay(other, signal);
  assert.equal(untouched.replay.status, "idle");
  assert.equal(untouched.replay.clock_sec, 1500);
  assert.deepEqual(untouched.insights, []);
  const snapshotsBeforeReconnect = snapshotCount;
  close();
  close = connect();
  await until(() => snapshotCount > snapshotsBeforeReconnect);
  assert.equal(view.snapshot.insights.length, 1);
  assert.deepEqual(view.snapshot.state, stats);
  const stale = {
    replay_id: view.snapshot.replay.replay_id,
    run_id: view.snapshot.replay.run_id,
    seq: view.snapshot.replay.last_seq + 100,
    kind: "insight",
    payload: insight,
  };
  const key = crypto.randomUUID(),
    before = view.snapshot;
  const reset = await controlReplay(before, { action: "reset" }, key, signal);
  view = replaceSnapshot(view, reset);
  const duplicate = await controlReplay(
    before,
    { action: "reset" },
    key,
    signal,
  );
  assert.equal(duplicate.replay.run_id, reset.replay.run_id);
  view = replaceSnapshot(view, duplicate);
  assert.equal(view.snapshot.replay.run_id, before.replay.run_id + 1);
  assert.equal(view.snapshot.replay.clock_sec, 1500);
  assert.deepEqual(view.snapshot.insights, []);
  assert.deepEqual(view.events, []);
  assert.deepEqual(view.snapshot.traces, []);
  const clean = view;
  assert.equal(applyStreamMessage(view, stale), clean);
  for (const kind of [
    "snapshot",
    "match_state",
    "match_event",
    "insight",
    "agent_status",
  ])
    assert(kinds.has(kind), `Missing ${kind}`);
  console.log(
    JSON.stringify({
      status: "passed",
      contract: "2.0.0",
      source: "real B/C application with 5x test clock",
      model_calls: 0,
      checks: [
        "catalogue and event recovery",
        "controls and pause freeze",
        "rule fallback with 3 recoveries / 2 linked shots",
        "same-insight audience texts and event references",
        "server statistics",
        "two-session isolation",
        "snapshot reconnect without duplicates",
        "idempotent reset and stale-run rejection",
      ],
      stream_kinds: [...kinds],
    }),
  );
} finally {
  for (const close of closers) close();
  globalThis.fetch = originalFetch;
  if (child.exitCode === null) {
    const exited = once(child, "exit");
    child.kill("SIGINT");
    const timeout = setTimeout(() => child.kill("SIGKILL"), 3000);
    await exited;
    clearTimeout(timeout);
  }
}
