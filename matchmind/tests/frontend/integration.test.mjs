import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  applyStreamMessage,
  controlReplay,
  createReplay,
  getEvents,
  mergeEvents,
  replaceSnapshot,
  subscribeToReplay,
} from "../../frontend/src/replay.ts";
const example = JSON.parse(
  await readFile(
    new URL("../../contracts/examples/replay_snapshot.json", import.meta.url),
    "utf8",
  ),
);
const events = (
  await readFile(
    new URL("../../data/fixtures/demo.events.jsonl", import.meta.url),
    "utf8",
  )
)
  .trim()
  .split("\n")
  .map(JSON.parse);
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});
const fresh = () => replaceSnapshot(null, structuredClone(example));
const msg = (
  kind,
  payload,
  seq = example.replay.last_seq + 1,
  run_id = example.replay.run_id,
) => ({ replay_id: example.replay.replay_id, run_id, seq, kind, payload });

test("control retries preserve the same operation key, payload and expected generation", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (calls.length === 1) throw new TypeError("response lost");
    return Response.json(example);
  };
  const key = crypto.randomUUID(),
    controller = new AbortController();
  await assert.rejects(
    controlReplay(example, { action: "reset" }, key, controller.signal),
  );
  await controlReplay(example, { action: "reset" }, key, controller.signal);
  assert.equal(
    calls[0].url,
    `/api/v1/replays/${example.replay.replay_id}/control`,
  );
  for (const call of calls) {
    assert.equal(call.options.headers["Idempotency-Key"], key);
    assert.equal(
      call.options.headers["X-MatchMind-Expected-Run"],
      String(example.replay.run_id),
    );
    assert.deepEqual(JSON.parse(call.options.body), { action: "reset" });
  }
});

test("create retry accepts a stable key shared by StrictMode effect restarts", async () => {
  const keys = [];
  globalThis.fetch = async (_url, options) => {
    keys.push(options.headers["Idempotency-Key"]);
    return Response.json(example);
  };
  const key = crypto.randomUUID();
  await createReplay(
    example.replay.match_id,
    new AbortController().signal,
    key,
  );
  await createReplay(
    example.replay.match_id,
    new AbortController().signal,
    key,
  );
  assert.deepEqual(keys, [key, key]);
});

test("speed commands use the frozen action and speed shape", async () => {
  globalThis.fetch = async (_url, options) => {
    assert.deepEqual(JSON.parse(options.body), {
      action: "set_speed",
      speed: 10,
    });
    return Response.json(example);
  };
  await controlReplay(
    example,
    { action: "set_speed", speed: 10 },
    crypto.randomUUID(),
    new AbortController().signal,
  );
});

test("control refuses a response from another replay", async () => {
  const wrong = structuredClone(example);
  wrong.replay.replay_id = "OTHER";
  globalThis.fetch = async () => Response.json(wrong);
  await assert.rejects(
    controlReplay(
      example,
      { action: "pause" },
      crypto.randomUUID(),
      new AbortController().signal,
    ),
    /different replay/,
  );
});

test("events are presentation data and never increment server statistics", () => {
  const initial = fresh(),
    state = initial.snapshot.state;
  const next = applyStreamMessage(
    initial,
    msg(
      "match_event",
      events.find((e) => e.type === "goal"),
    ),
  );
  assert.deepEqual(next.snapshot.state, state);
  assert.equal(next.events.length, 1);
  assert.equal(
    next.snapshot.replay.clock_sec,
    initial.snapshot.replay.clock_sec,
  );
});

test("match_state replaces counts and updates the server clock", () => {
  const state = structuredClone(example.state);
  state.at_sec += 1;
  state.shots.HOME = 8;
  const next = applyStreamMessage(fresh(), msg("match_state", state));
  assert.equal(next.snapshot.state.shots.HOME, 8);
  assert.equal(next.snapshot.replay.clock_sec, state.at_sec);
});

test("new-generation snapshot clears events, analysis error and prior insights atomically", () => {
  let current = applyStreamMessage(fresh(), msg("match_event", events[0]));
  current = applyStreamMessage(
    current,
    msg(
      "error",
      { code: "TIMEOUT", message: "slow", retryable: true },
      example.replay.last_seq + 2,
    ),
  );
  const reset = structuredClone(example);
  reset.replay = {
    ...reset.replay,
    run_id: reset.replay.run_id + 1,
    last_seq: example.replay.last_seq + 3,
    clock_sec: 1500,
    status: "idle",
  };
  reset.state = { ...reset.state, at_sec: 1500 };
  reset.insights = [];
  reset.traces = [];
  const next = replaceSnapshot(current, reset);
  assert.equal(next.snapshot.replay.run_id, reset.replay.run_id);
  assert.deepEqual(next.events, []);
  assert.deepEqual(next.snapshot.insights, []);
  assert.deepEqual(next.snapshot.traces, []);
  assert.equal(next.analysisError, null);
  assert.equal(replaceSnapshot(next, example), next);
  assert.equal(
    applyStreamMessage(
      next,
      msg("insight", example.insights[0], reset.replay.last_seq + 1),
    ),
    next,
  );
});

test("duplicate/out-of-order and foreign-session updates do not replace the current state", () => {
  const current = fresh();
  assert.equal(
    applyStreamMessage(
      current,
      msg("match_state", example.state, example.replay.last_seq),
    ),
    current,
  );
  assert.equal(
    applyStreamMessage(current, {
      ...msg("match_state", example.state),
      replay_id: "OTHER",
    }),
    current,
  );
});

test("insights deduplicate by id and retain at most the latest twenty", () => {
  let view = fresh();
  for (let i = 0; i < 25; i++)
    view = applyStreamMessage(
      view,
      msg(
        "insight",
        { ...example.insights[0], insight_id: `I-${i}` },
        example.replay.last_seq + i + 1,
      ),
    );
  const last = view.snapshot.insights.at(-1);
  view = applyStreamMessage(
    view,
    msg("insight", last, view.snapshot.replay.last_seq + 1),
  );
  assert.equal(view.snapshot.insights.length, 20);
  assert.equal(
    view.snapshot.insights.filter((i) => i.insight_id === last.insight_id)
      .length,
    1,
  );
});

function stream() {
  let view = fresh();
  const handlers = new Map(),
    errors = [],
    statuses = [];
  const source = {
    addEventListener: (kind, fn) => handlers.set(kind, fn),
    close: () => {},
    onerror: null,
  };
  const close = subscribeToReplay({
    initial: view.snapshot,
    getCurrent: () => view.snapshot,
    onMessage: (message) => {
      view = applyStreamMessage(view, message);
    },
    onError: (e) => errors.push(e),
    onConnection: (s) => statuses.push(s),
    createSource: () => source,
  });
  const send = (message) =>
    handlers.get(message.kind)({ data: JSON.stringify(message) });
  return {
    handlers,
    source,
    errors,
    statuses,
    close,
    send,
    get view() {
      return view;
    },
    set view(v) {
      view = v;
    },
  };
}

test("subscribes to every frozen named SSE kind and presents real agent traces", () => {
  const s = stream();
  assert.deepEqual(
    [...s.handlers.keys()],
    [
      "snapshot",
      "match_event",
      "match_state",
      "insight",
      "agent_status",
      "error",
    ],
  );
  const trace = { ...example.traces[0], note: "Actual completed step" };
  s.send(msg("agent_status", trace));
  assert.equal(
    s.view.snapshot.traces.find((t) => t.note === trace.note).duration_ms,
    trace.duration_ms,
  );
  s.close();
});

test("named business errors retain statistics and do not masquerade as transport failures", () => {
  const s = stream(),
    before = structuredClone(s.view.snapshot.state);
  s.send(
    msg("error", {
      code: "MODEL_UNAVAILABLE",
      message: "Analysis unavailable; replay continues.",
      retryable: true,
    }),
  );
  s.source.onerror({ data: "business error event" });
  assert.equal(s.view.analysisError.code, "MODEL_UNAVAILABLE");
  assert.deepEqual(s.view.snapshot.state, before);
  assert.equal(s.statuses.at(-1), "connected");
  s.close();
});

test("stream checks the latest control snapshot before accepting a late old-run message", () => {
  const s = stream(),
    reset = structuredClone(example);
  reset.replay.run_id++;
  reset.replay.last_seq += 5;
  reset.insights = [];
  reset.traces = [];
  s.view = replaceSnapshot(s.view, reset);
  s.send(msg("insight", example.insights[0], reset.replay.last_seq + 1));
  assert.deepEqual(s.view.snapshot.insights, []);
  s.close();
});

test("malformed payloads and snapshots with mismatched sequence are not rendered", () => {
  const s = stream(),
    before = s.view;
  s.send(
    msg("match_state", { match_id: example.replay.match_id, at_sec: 1650 }),
  );
  const payload = structuredClone(example);
  payload.replay.last_seq += 9;
  s.send(msg("snapshot", payload));
  assert.equal(s.view, before);
  assert.match(s.errors.at(-1), /could not be read/);
  s.close();
});

test("event recovery uses the match API and stable event ordering without duplicates", async () => {
  globalThis.fetch = async (url) => {
    assert.equal(url, `/api/v1/matches/${example.replay.match_id}/events`);
    return Response.json([events[1], events[0], events[0]]);
  };
  assert.deepEqual(
    await getEvents(example.replay.match_id, new AbortController().signal),
    [events[0], events[1]],
  );
  assert.deepEqual(mergeEvents([events[1], events[0], events[0]]), [
    events[0],
    events[1],
  ]);
});

test("event recovery rejects cross-match evidence", async () => {
  globalThis.fetch = async () =>
    Response.json([{ ...events[0], match_id: "OTHER" }]);
  await assert.rejects(
    getEvents(example.replay.match_id, new AbortController().signal),
    /expected format/,
  );
});
