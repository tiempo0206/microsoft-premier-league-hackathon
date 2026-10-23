/** Manual, explicitly opted-in public acceptance. Never part of the offline test glob. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import {
  applyStreamMessage,
  controlReplay,
  createReplay,
  getEvents,
  getMatches,
  getReplay,
  replaceSnapshot,
} from "../../frontend/src/replay.ts";

const args = process.argv.slice(2);
if (args.length !== 3 || args[0] !== "--origin" || args[2] !== "--live-once") {
  console.error(
    "Usage: node --experimental-strip-types ../tests/frontend/public-probe.mjs --origin https://your-service.example --live-once",
  );
  console.error(
    "This manual check can invoke one paid AI workflow. Never add it to normal tests or CI.",
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
  assert.equal(
    url.origin,
    origin.origin,
    "Requests must stay on the selected origin",
  );
  return originalFetch(url, options);
};
const signal = new AbortController().signal;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let current = null;
const report = {
  checked_at: new Date().toISOString(),
  origin: origin.origin,
  contract_version: "2.0.0",
  status: "started",
  analysis_windows_requested: 0,
  browser_interaction_verified: false,
  checks: [],
};
const reportDirectory = new URL(
  "../../.artifacts/frontend-public-acceptance/",
  import.meta.url,
);
try {
  const healthResponse = await fetch("/api/v1/health", {
    signal: AbortSignal.timeout(20000),
  });
  assert.equal(healthResponse.status, 200);
  report.health = await healthResponse.json();
  assert.equal(report.health.contract_version, "2.0.0");
  const htmlResponse = await fetch("/", { signal: AbortSignal.timeout(20000) });
  assert.equal(htmlResponse.status, 200);
  const html = await htmlResponse.text();
  const assets = [
    ...html.matchAll(/(?:src|href)="(\/assets\/[A-Za-z0-9_.-]+)"/g),
  ].map((item) => item[1]);
  assert(
    assets.some((path) => path.endsWith(".js")) &&
      assets.some((path) => path.endsWith(".css")),
  );
  report.assets = [];
  for (const path of assets) {
    const response = await fetch(path, { signal: AbortSignal.timeout(20000) });
    assert.equal(response.status, 200);
    const remote = Buffer.from(await response.arrayBuffer());
    const local = await readFile(
      new URL(`../../frontend/dist${path}`, import.meta.url),
    );
    const sha256 = (value) => createHash("sha256").update(value).digest("hex");
    assert.equal(
      sha256(remote),
      sha256(local),
      `Public bundle differs from this checkout: ${path}`,
    );
    report.assets.push({
      path,
      sha256: sha256(remote),
      matches_reviewed_bundle: true,
    });
  }
  report.checks.push("public assets match the reviewed frontend bundle");
  const match = (await getMatches(signal)).find(
    (item) => item.match_id === "MM-DEMO-01",
  );
  assert(
    match && match.clip_start_sec === 1500 && match.clip_end_sec === 1800,
    "This manual probe requires the baseline 25:00–30:00 clip",
  );
  const events = await getEvents(match.match_id, signal);
  current = await createReplay(match.match_id, signal);
  report.replay_id = current.replay.replay_id;
  current = await controlReplay(
    current,
    { action: "set_speed", speed: 10 },
    crypto.randomUUID(),
    signal,
  );
  current = await controlReplay(
    current,
    { action: "play" },
    crypto.randomUUID(),
    signal,
  );
  report.analysis_windows_requested = 1;
  const deadline = Date.now() + 75000;
  while (current.replay.clock_sec < 1650 && Date.now() < deadline) {
    await wait(1000);
    current = await getReplay(current, signal);
  }
  assert(
    current.replay.clock_sec >= 1650,
    "Replay did not reach the analysis window",
  );
  current = await controlReplay(
    current,
    { action: "pause" },
    crypto.randomUUID(),
    signal,
  );
  assert.equal(current.replay.status, "paused");
  const pausedClock = current.replay.clock_sec;
  while (!current.insights.length && Date.now() < deadline) {
    await wait(1000);
    current = await getReplay(current, signal);
    assert.equal(
      current.replay.clock_sec,
      pausedClock,
      "Paused clock advanced while analysis completed",
    );
  }
  assert.equal(
    current.insights.length,
    1,
    "No analysis was published within the bounded observation period",
  );
  const view = replaceSnapshot(null, current);
  const insight = current.insights[0];
  const stateResponse = await fetch(
    `/api/v1/matches/${encodeURIComponent(match.match_id)}/stats?at_sec=${pausedClock}`,
    { signal: AbortSignal.timeout(10000) },
  );
  assert.equal(stateResponse.status, 200);
  assert.deepEqual(current.state, await stateResponse.json());
  const evidence = insight.evidence_event_ids.map((id) =>
    events.find((event) => event.event_id === id),
  );
  assert(evidence.length > 0, "An insight must reference recorded evidence");
  assert(
    evidence.every(
      (event) =>
        event &&
        event.timestamp_sec >= insight.window.start_sec &&
        event.timestamp_sec <= insight.window.end_sec,
    ),
  );
  assert(insight.narratives.casual && insight.narratives.analyst);
  assert.notEqual(insight.narratives.casual, insight.narratives.analyst);
  report.match_id = match.match_id;
  report.paused_clock_sec = pausedClock;
  report.insight = {
    insight_id: insight.insight_id,
    window: insight.window,
    generation: insight.generation,
    verification: insight.verification,
    metrics: insight.metrics,
    evidence_event_ids: insight.evidence_event_ids,
    narratives: insight.narratives,
  };
  report.traces = current.traces.map(({ agent, status, duration_ms }) => ({
    agent,
    status,
    duration_ms,
  }));
  report.live_model_verified =
    insight.generation.mode === "live_model" &&
    insight.verification.method === "agent_and_code" &&
    insight.verification.status === "passed";
  report.checks.push(
    "actual frontend consumer accepts the public snapshot and insight",
    "pause holds while the analysis finishes",
    "statistics match the public server endpoint",
    "both narrative fields share one insight and evidence set",
    "every evidence reference resolves inside the published window",
  );
  const initial = current,
    key = crypto.randomUUID();
  const reset = await controlReplay(initial, { action: "reset" }, key, signal);
  const repeated = await controlReplay(
    initial,
    { action: "reset" },
    key,
    signal,
  );
  assert.equal(repeated.replay.run_id, reset.replay.run_id);
  assert.equal(reset.replay.run_id, initial.replay.run_id + 1);
  assert.equal(reset.replay.clock_sec, match.clip_start_sec);
  assert.deepEqual(reset.insights, []);
  assert.deepEqual(reset.traces, []);
  const clean = replaceSnapshot(view, reset);
  const stale = {
    replay_id: initial.replay.replay_id,
    run_id: initial.replay.run_id,
    seq: reset.replay.last_seq + 100,
    kind: "insight",
    payload: insight,
  };
  assert.equal(applyStreamMessage(clean, stale), clean);
  current = await getReplay(reset, signal);
  assert.equal(current.replay.status, "idle");
  assert.deepEqual(current.insights, []);
  assert.deepEqual(current.traces, []);
  report.reset = {
    run_id: current.replay.run_id,
    clock_sec: current.replay.clock_sec,
    insights: current.insights.length,
    traces: current.traces.length,
  };
  report.checks.push(
    "reset retry increments the generation once",
    "reset clears insights and traces",
    "the consumer discards a late old-run insight",
  );
  report.status = report.live_model_verified
    ? "passed_live"
    : "passed_fallback_only";
  if (!report.live_model_verified) process.exitCode = 1;
} catch (error) {
  report.status = "failed";
  report.error = error.message;
  process.exitCode = 1;
} finally {
  // Also resolve an uncertain play response before leaving our own replay.
  if (
    current &&
    (current.replay.status === "playing" || report.status === "failed")
  ) {
    try {
      await controlReplay(
        current,
        { action: "pause" },
        crypto.randomUUID(),
        signal,
      );
    } catch {
      /* No repeated analysis or other-session changes. */
    }
  }
  globalThis.fetch = originalFetch;
  await mkdir(reportDirectory, { recursive: true });
  await writeFile(
    new URL("result.json", reportDirectory),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
}
