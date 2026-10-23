/** Manual public transport acceptance. Stays before the first AI window at 1x. */
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import {
  applyStreamMessage,
  controlReplay,
  createReplay,
  getEvents,
  getMatches,
  getReplay,
  mergeEvents,
  replaceSnapshot,
  subscribeToReplay,
} from "../../frontend/src/replay.ts";
import { HttpEventSource } from "./http-event-source.mjs";

const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== "--origin") {
  console.error(
    "Usage: node --experimental-strip-types ../tests/frontend/public-stream-probe.mjs --origin https://your-service.example",
  );
  process.exit(2);
}
const origin = new URL(args[1]);
assert(
  origin.protocol === "https:" &&
    !origin.username &&
    !origin.password &&
    !origin.search &&
    !origin.hash &&
    origin.pathname === "/",
  "Use an HTTPS origin without credentials or a path",
);
const originalFetch = globalThis.fetch;
globalThis.fetch = (path, options) => {
  const url = new URL(path, origin);
  assert.equal(url.origin, origin.origin);
  return originalFetch(url, options);
};
const signal = new AbortController().signal;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const report = {
  checked_at: new Date().toISOString(),
  origin: origin.origin,
  contract_version: "2.0.0",
  status: "started",
  browser_interaction_verified: false,
  model_job_requested: null,
  message_counts: {},
  checks: [],
};
let view = null,
  current = null,
  close = () => {},
  streamError = null;
let snapshots = 0,
  playStarted = 0,
  firstProgress = null,
  maxClock = 1500;
async function until(predicate, description, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (streamError) throw new Error(streamError);
    if (predicate()) return;
    await sleep(100);
  }
  throw new Error(`Timed out: ${description}`);
}
function connect() {
  return subscribeToReplay({
    initial: view.snapshot,
    getCurrent: () => view.snapshot,
    onMessage: (message) => {
      report.message_counts[message.kind] =
        (report.message_counts[message.kind] ?? 0) + 1;
      if (message.kind === "snapshot") snapshots++;
      view = applyStreamMessage(view, message);
      maxClock = Math.max(maxClock, view.snapshot.replay.clock_sec);
      if (
        message.kind === "match_state" &&
        playStarted &&
        view.snapshot.replay.clock_sec > 1500 &&
        firstProgress === null
      )
        firstProgress = Date.now() - playStarted;
    },
    onConnection: () => {},
    onError: (error) => {
      if (error) streamError = error;
    },
    createSource: (url) => new HttpEventSource(url),
  });
}
try {
  const [match] = await getMatches(signal);
  assert(match && match.clip_start_sec === 1500 && match.clip_end_sec === 1800);
  const events = await getEvents(match.match_id, signal);
  assert(
    events.some(
      (event) => event.timestamp_sec > 1500 && event.timestamp_sec <= 1520,
    ),
    "The transport probe needs an early event before any analysis window",
  );
  current = await createReplay(match.match_id, signal);
  report.replay_id = current.replay.replay_id;
  current = await controlReplay(
    current,
    { action: "set_speed", speed: 1 },
    crypto.randomUUID(),
    signal,
  );
  view = replaceSnapshot(null, current);
  close = connect();
  await until(() => snapshots === 1, "initial stream snapshot");
  playStarted = Date.now();
  current = await controlReplay(
    view.snapshot,
    { action: "play" },
    crypto.randomUUID(),
    signal,
  );
  view = replaceSnapshot(view, current);
  await until(
    () => firstProgress !== null && report.message_counts.match_event > 0,
    "incremental match_state and match_event",
  );
  current = await controlReplay(
    view.snapshot,
    { action: "pause" },
    crypto.randomUUID(),
    signal,
  );
  view = replaceSnapshot(view, current);
  const pausedClock = current.replay.clock_sec;
  assert.equal(current.replay.status, "paused");
  assert(
    pausedClock < 1650,
    "The transport probe must stop before the AI window",
  );
  await sleep(500);
  current = await getReplay(current, signal);
  assert.equal(current.replay.clock_sec, pausedClock);
  assert.deepEqual(current.insights, []);
  assert.deepEqual(current.traces, []);
  view = replaceSnapshot(view, current);
  // The page restores event details through this same API, rather than treating the stream as a log.
  view = {
    ...view,
    events: mergeEvents(
      events.filter((event) => event.timestamp_sec <= pausedClock),
    ),
  };
  const state = view.snapshot.state;
  const eventCount = view.events.length;
  const beforeReconnect = snapshots;
  close();
  close = connect();
  await until(
    () => snapshots > beforeReconnect,
    "fresh snapshot after explicit disconnect/reconnect",
  );
  assert.deepEqual(view.snapshot.state, state);
  assert.equal(view.snapshot.replay.clock_sec, pausedClock);
  assert.equal(view.events.length, eventCount);
  assert.equal(
    new Set(view.events.map((event) => event.event_id)).size,
    eventCount,
  );
  current = await controlReplay(
    view.snapshot,
    { action: "reset" },
    crypto.randomUUID(),
    signal,
  );
  const resetRun = current.replay.run_id;
  // Observe the new generation from SSE; do not replace the view from the HTTP response here.
  await until(
    () => view.snapshot.replay.run_id === resetRun,
    "reset snapshot on the live stream",
  );
  assert.equal(view.snapshot.replay.clock_sec, 1500);
  assert.equal(view.snapshot.replay.status, "idle");
  assert.deepEqual(view.snapshot.insights, []);
  assert.deepEqual(view.snapshot.traces, []);
  assert.deepEqual(view.events, []);
  current = view.snapshot;
  assert(maxClock < 1650);
  assert(
    !report.message_counts.insight &&
      !report.message_counts.agent_status &&
      !report.message_counts.error,
  );
  report.model_job_requested = false;
  report.status = "passed";
  report.first_progress_after_play_ms = firstProgress;
  report.paused_clock_sec = pausedClock;
  report.max_observed_clock_sec = maxClock;
  report.snapshots = snapshots;
  report.reset = {
    run_id: resetRun,
    clock_sec: 1500,
    status: "idle",
    insights: 0,
    traces: 0,
    events: 0,
  };
  report.checks = [
    "actual frontend subscription accepts public named SSE frames",
    "incremental match_state and match_event arrive before the deadline",
    "pause freezes the clock",
    "explicit reconnect restores statistics without event duplication",
    "reset snapshot replaces the generation and clears the timeline",
    "no AI window reached",
  ];
} catch (error) {
  report.status = "failed";
  report.error = error.message;
  process.exitCode = 1;
} finally {
  close();
  // Limit any uncertain play command to this probe's own replay.
  if (
    current &&
    (current.replay.status !== "idle" || report.status === "failed")
  ) {
    try {
      await controlReplay(
        current,
        { action: "pause" },
        crypto.randomUUID(),
        signal,
      );
    } catch {
      report.cleanup =
        "Pause could not be confirmed; inspect this temporary replay.";
    }
  }
  globalThis.fetch = originalFetch;
  report.max_observed_clock_sec = maxClock;
  const directory = new URL(
    "../../.artifacts/frontend-public-transport/",
    import.meta.url,
  );
  await mkdir(directory, { recursive: true });
  await writeFile(
    new URL("result.json", directory),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
}
