import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  createReplay,
  formatClock,
  getMatches,
  passAccuracy,
  subscribeToSnapshots,
} from "../../frontend/src/replay.ts";

const example = JSON.parse(
  await readFile(
    new URL("../../contracts/examples/replay_snapshot.json", import.meta.url),
    "utf8",
  ),
);
const match = JSON.parse(
  await readFile(
    new URL("../../data/fixtures/demo.match.json", import.meta.url),
    "utf8",
  ),
);
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("loads the supplied match catalogue using the same-origin contract path", async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/matches");
    assert.equal(options.method, "GET");
    return Response.json([match]);
  };
  assert.deepEqual(await getMatches(new AbortController().signal), [match]);
});

test("an empty catalogue is valid; malformed match data is not", async () => {
  globalThis.fetch = async () => Response.json([]);
  assert.deepEqual(await getMatches(new AbortController().signal), []);
  globalThis.fetch = async () =>
    Response.json([{ ...match, synthetic: false }]);
  await assert.rejects(
    getMatches(new AbortController().signal),
    /expected format/,
  );
});

test("creates a replay with the frozen match_id and recommended speed", async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/replays");
    assert.equal(options.method, "POST");
    assert.deepEqual(JSON.parse(options.body), {
      match_id: match.match_id,
      speed: 5,
    });
    return Response.json(example, { status: 201 });
  };
  assert.deepEqual(
    await createReplay(match.match_id, new AbortController().signal),
    example,
  );
});

test("rejects a replay for another match instead of showing its statistics", async () => {
  globalThis.fetch = async () => Response.json(example, { status: 201 });
  await assert.rejects(
    createReplay("OTHER-MATCH", new AbortController().signal),
    /different match/,
  );
});

test("HTTP, network, and non-JSON failures produce actionable connection errors", async () => {
  globalThis.fetch = async () => new Response(null, { status: 429 });
  await assert.rejects(
    getMatches(new AbortController().signal),
    /sessions are busy/,
  );
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(
    getMatches(new AbortController().signal),
    /could not be reached/,
  );
  globalThis.fetch = async () => new Response("not JSON");
  await assert.rejects(
    getMatches(new AbortController().signal),
    /unreadable response/,
  );
});

test("abort signals remain aborts so unmounted requests are not reported as errors", async () => {
  const controller = new AbortController();
  controller.abort();
  globalThis.fetch = async (_url, { signal }) => {
    signal.throwIfAborted();
  };
  await assert.rejects(getMatches(controller.signal), { name: "AbortError" });
});

function connection() {
  const callbacks = new Map();
  const snapshots = [],
    statuses = [],
    errors = [];
  let closed = false;
  const source = {
    onerror: null,
    addEventListener: (event, callback) => callbacks.set(event, callback),
    close: () => {
      closed = true;
    },
  };
  const close = subscribeToSnapshots({
    initial: example,
    onSnapshot: (value) => snapshots.push(value),
    onConnection: (value) => statuses.push(value),
    onError: (value) => errors.push(value),
    createSource: (url) => {
      assert.equal(url, `/api/v1/replays/${example.replay.replay_id}/stream`);
      return source;
    },
  });
  const emit = (seq, runId = example.replay.run_id) => {
    seq += example.replay.last_seq;
    const payload = structuredClone(example);
    payload.replay.run_id = runId;
    payload.replay.last_seq = seq;
    callbacks.get("snapshot")({
      data: JSON.stringify({
        replay_id: example.replay.replay_id,
        run_id: runId,
        seq,
        kind: "snapshot",
        payload,
      }),
    });
  };
  return {
    callbacks,
    snapshots,
    statuses,
    errors,
    source,
    close,
    emit,
    isClosed: () => closed,
  };
}

test("consumes named snapshot messages and ignores duplicates and older generations", () => {
  const c = connection();
  c.emit(1);
  c.emit(1);
  c.emit(2, example.replay.run_id + 1);
  c.emit(3);
  assert.equal(c.snapshots.length, 2);
  assert.equal(c.snapshots[1].replay.run_id, example.replay.run_id + 1);
  assert.equal(c.statuses.at(-1), "connected");
  assert.equal(c.errors.at(-1), null);
  c.close();
});

test("a broken or malformed stream retains the last valid snapshot and can recover", () => {
  const c = connection();
  c.emit(1);
  c.source.onerror();
  assert.equal(c.statuses.at(-1), "reconnecting");
  c.callbacks.get("snapshot")({ data: "{broken" });
  assert.equal(c.snapshots.length, 1);
  assert.match(c.errors.at(-1), /last valid snapshot/);
  c.emit(2);
  assert.equal(c.snapshots.length, 2);
  assert.equal(c.errors.at(-1), null);
  c.close();
});

test("closing a subscription releases its source and rejects late callbacks", () => {
  const c = connection();
  c.close();
  c.emit(1);
  c.source.onerror();
  assert.equal(c.isClosed(), true);
  assert.equal(c.snapshots.length, 0);
  assert.deepEqual(c.statuses, ["connecting"]);
});

test("rejects an envelope carrying a snapshot from a different replay", () => {
  const c = connection();
  const payload = structuredClone(example);
  payload.replay.replay_id = "OTHER";
  c.callbacks.get("snapshot")({
    data: JSON.stringify({
      replay_id: example.replay.replay_id,
      run_id: example.replay.run_id,
      seq: 1,
      kind: "snapshot",
      payload,
    }),
  });
  assert.equal(c.snapshots.length, 0);
  assert.match(c.errors.at(-1), /could not be read/);
  c.close();
});

test("displays match minutes and does not invent a percentage with zero attempts", () => {
  assert.equal(formatClock(1500), "25:00");
  assert.equal(formatClock(1650), "27:30");
  assert.equal(passAccuracy(0, 0), "—");
  assert.equal(passAccuracy(2, 3), "67%");
});
