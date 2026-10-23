import type {
  ControlReplay,
  ErrorInfo,
  Event,
  Insight,
  Match,
  MatchState,
  ReplaySnapshot,
  StreamMessage,
  Trace,
} from "./contract";

const API = "/api/v1";
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;
const isCount = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value >= 0;
const hasCounts = (value: unknown): boolean =>
  isObject(value) && isCount(value.HOME) && isCount(value.AWAY);

async function request(
  path: string,
  signal: AbortSignal,
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method: body === undefined ? "GET" : "POST",
      ...(body === undefined
        ? {}
        : {
            body: JSON.stringify(body),
          }),
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
      signal: AbortSignal.any([signal, AbortSignal.timeout(10_000)]),
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error(
      "The replay service could not be reached. Please try again.",
    );
  }
  if (!response.ok) {
    throw new Error(
      response.status === 429
        ? "All replay sessions are busy. Please try again shortly."
        : `The replay service returned an error (${response.status}). Please try again.`,
    );
  }
  try {
    return await response.json();
  } catch {
    throw new Error(
      "The replay service returned an unreadable response. Please try again.",
    );
  }
}

export async function getMatches(signal: AbortSignal): Promise<Match[]> {
  const data = await request("/matches", signal);
  if (
    !Array.isArray(data) ||
    !data.every(
      (match) =>
        isObject(match) &&
        typeof match.match_id === "string" &&
        match.match_id.length > 0 &&
        typeof match.home === "string" &&
        typeof match.away === "string" &&
        match.synthetic === true &&
        isCount(match.clip_start_sec) &&
        isCount(match.clip_end_sec) &&
        match.clip_end_sec > match.clip_start_sec &&
        (match.period === 1 || match.period === 2) &&
        (match.home_attack_direction === "right" ||
          match.home_attack_direction === "left") &&
        (match.initial_possession_team === "HOME" ||
          match.initial_possession_team === "AWAY") &&
        isCount(match.seed) &&
        typeof match.generator_version === "string",
    )
  )
    throw new Error("The replay catalogue is not in the expected format.");
  return data as Match[];
}

function checkSnapshot(value: unknown): asserts value is ReplaySnapshot {
  if (!isObject(value) || !isObject(value.replay) || !isObject(value.state)) {
    throw new Error("The replay snapshot is not in the expected format.");
  }
  const { replay, state } = value;
  if (
    typeof replay.replay_id !== "string" ||
    !replay.replay_id ||
    !isCount(replay.run_id) ||
    replay.run_id < 1 ||
    !isCount(replay.last_seq) ||
    typeof replay.match_id !== "string" ||
    !isCount(replay.clock_sec) ||
    ![1, 2, 5, 10].includes(replay.speed as number) ||
    !["idle", "playing", "paused", "ended"].includes(replay.status as string) ||
    state.match_id !== replay.match_id ||
    state.at_sec !== replay.clock_sec ||
    ![
      "score",
      "shots",
      "passes",
      "completed_passes",
      "possession_seconds",
    ].every((key) => hasCounts(state[key])) ||
    !(
      state.last_event_id === null || typeof state.last_event_id === "string"
    ) ||
    !Array.isArray(value.insights) ||
    !Array.isArray(value.traces)
  ) {
    throw new Error("The replay snapshot is not in the expected format.");
  }
}

export async function createReplay(
  matchId: string,
  signal: AbortSignal,
  operationId: string = crypto.randomUUID(),
): Promise<ReplaySnapshot> {
  const data = await request(
    "/replays",
    signal,
    {
      match_id: matchId,
      speed: 5,
    },
    { "Idempotency-Key": operationId },
  );
  checkSnapshot(data);
  if (data.replay.match_id !== matchId)
    throw new Error("The replay belongs to a different match.");
  return data;
}

export async function controlReplay(
  initial: ReplaySnapshot,
  command: ControlReplay,
  operationId: string,
  signal: AbortSignal,
): Promise<ReplaySnapshot> {
  const data = await request(
    `/replays/${encodeURIComponent(initial.replay.replay_id)}/control`,
    signal,
    command,
    {
      "Idempotency-Key": operationId,
      "X-MatchMind-Expected-Run": String(initial.replay.run_id),
    },
  );
  checkSnapshot(data);
  if (
    data.replay.replay_id !== initial.replay.replay_id ||
    data.replay.match_id !== initial.replay.match_id
  )
    throw new Error("The control response belongs to a different replay.");
  return data;
}

export async function getReplay(
  initial: ReplaySnapshot,
  signal: AbortSignal,
): Promise<ReplaySnapshot> {
  const data = await request(
    `/replays/${encodeURIComponent(initial.replay.replay_id)}`,
    signal,
  );
  checkSnapshot(data);
  if (
    data.replay.replay_id !== initial.replay.replay_id ||
    data.replay.match_id !== initial.replay.match_id
  )
    throw new Error("The response belongs to a different replay.");
  return data;
}

function validState(value: unknown, matchId: string): value is MatchState {
  return (
    isObject(value) &&
    value.match_id === matchId &&
    isCount(value.at_sec) &&
    [
      "score",
      "shots",
      "passes",
      "completed_passes",
      "possession_seconds",
    ].every((key) => hasCounts(value[key]))
  );
}

function validEvent(value: unknown, matchId: string): value is Event {
  return (
    isObject(value) &&
    value.match_id === matchId &&
    typeof value.event_id === "string" &&
    isCount(value.timestamp_sec) &&
    ["pass", "recovery", "shot", "goal", "foul"].includes(
      value.type as string,
    ) &&
    ["HOME", "AWAY"].includes(value.team_id as string) &&
    typeof value.player_id === "string" &&
    isObject(value.position) &&
    [value.position.x, value.position.y].every(
      (n) => typeof n === "number" && n >= 0 && n <= 100,
    ) &&
    (value.end_position === null ||
      (isObject(value.end_position) &&
        [value.end_position.x, value.end_position.y].every(
          (n) => typeof n === "number" && n >= 0 && n <= 100,
        ))) &&
    typeof value.outcome === "string"
  );
}

function validInsight(value: unknown, matchId: string): value is Insight {
  return (
    isObject(value) &&
    value.match_id === matchId &&
    typeof value.insight_id === "string" &&
    isObject(value.window) &&
    isCount(value.window.start_sec) &&
    isCount(value.window.end_sec) &&
    value.window.start_sec <= value.window.end_sec &&
    isObject(value.narratives) &&
    typeof value.narratives.casual === "string" &&
    typeof value.narratives.analyst === "string" &&
    Array.isArray(value.evidence_event_ids) &&
    value.evidence_event_ids.every((id) => typeof id === "string") &&
    Array.isArray(value.claims) &&
    value.claims.every(
      (c) =>
        isObject(c) &&
        typeof c.claim_id === "string" &&
        typeof c.text === "string",
    ) &&
    isObject(value.metrics) &&
    [
      "high_recoveries",
      "linked_shots",
      "window_seconds",
      "home_possession_seconds",
      "away_possession_seconds",
      "home_shots",
      "away_shots",
    ].every((key) =>
      isCount(value.metrics && (value.metrics as Record<string, unknown>)[key]),
    ) &&
    isObject(value.verification) &&
    ["passed", "fallback"].includes(value.verification.status as string) &&
    ["agent_and_code", "code_only"].includes(
      value.verification.method as string,
    ) &&
    Array.isArray(value.verification.rejected_claims) &&
    value.verification.rejected_claims.every((c) => typeof c === "string") &&
    isObject(value.generation) &&
    ["live_model", "rule_fallback", "precomputed"].includes(
      value.generation.mode as string,
    ) &&
    typeof value.generation.provider === "string" &&
    (value.generation.model === null ||
      typeof value.generation.model === "string") &&
    isObject(value.display) &&
    typeof value.display.title === "string"
  );
}

function validTrace(value: unknown): value is Trace {
  return (
    isObject(value) &&
    typeof value.task_id === "string" &&
    ["analyst", "narrator", "auditor", "validator"].includes(
      value.agent as string,
    ) &&
    ["started", "completed", "rejected", "failed", "fallback"].includes(
      value.status as string,
    ) &&
    isCount(value.duration_ms) &&
    typeof value.note === "string"
  );
}

function validError(value: unknown): value is ErrorInfo {
  return (
    isObject(value) &&
    typeof value.code === "string" &&
    typeof value.message === "string" &&
    typeof value.retryable === "boolean"
  );
}

export type ReplayView = {
  snapshot: ReplaySnapshot;
  events: Event[];
  analysisError: ErrorInfo | null;
};
const uniqueInsights = (items: Insight[]) =>
  [...new Map(items.map((item) => [item.insight_id, item])).values()].slice(
    -20,
  );
const uniqueTraces = (items: Trace[]) =>
  [
    ...new Map(
      items.map((item) => [
        `${item.task_id}:${item.agent}:${item.status}`,
        item,
      ]),
    ).values(),
  ].slice(-50);

export function mergeEvents(items: Event[]): Event[] {
  return [...new Map(items.map((item) => [item.event_id, item])).values()].sort(
    (a, b) =>
      a.timestamp_sec - b.timestamp_sec || a.event_id.localeCompare(b.event_id),
  );
}

export function replaceSnapshot(
  current: ReplayView | null,
  snapshot: ReplaySnapshot,
): ReplayView {
  checkSnapshot(snapshot);
  if (
    !snapshot.insights.every(
      (item) =>
        validInsight(item, snapshot.replay.match_id) &&
        item.window.end_sec <= snapshot.replay.clock_sec,
    ) ||
    !snapshot.traces.every(validTrace)
  )
    throw new Error("The analysis snapshot is not in the expected format.");
  if (current) {
    const before = current.snapshot.replay,
      after = snapshot.replay;
    if (
      before.replay_id !== after.replay_id ||
      before.match_id !== after.match_id ||
      after.run_id < before.run_id ||
      after.last_seq < before.last_seq
    )
      return current;
  }
  const sameRun = current?.snapshot.replay.run_id === snapshot.replay.run_id;
  return {
    snapshot: {
      ...snapshot,
      insights: uniqueInsights(snapshot.insights),
      traces: uniqueTraces(snapshot.traces),
    },
    events: sameRun
      ? current.events.filter(
          (e) => e.timestamp_sec <= snapshot.replay.clock_sec,
        )
      : [],
    analysisError: sameRun ? current.analysisError : null,
  };
}

/** Transport state only. Never derive or increment match statistics from an event. */
export function applyStreamMessage(
  current: ReplayView,
  message: StreamMessage,
): ReplayView {
  const replay = current.snapshot.replay;
  if (
    message.replay_id !== replay.replay_id ||
    message.run_id < replay.run_id ||
    message.seq <= replay.last_seq
  )
    return current;
  if (message.kind === "snapshot")
    return replaceSnapshot(current, message.payload);
  if (message.run_id !== replay.run_id) return current; // A new generation starts with a complete snapshot.
  const snapshot = {
    ...current.snapshot,
    replay: { ...replay, last_seq: message.seq },
  };
  switch (message.kind) {
    case "match_event":
      return {
        ...current,
        snapshot,
        events: mergeEvents([...current.events, message.payload]),
      };
    case "match_state":
      return {
        ...current,
        snapshot: {
          ...snapshot,
          state: message.payload,
          replay: { ...snapshot.replay, clock_sec: message.payload.at_sec },
        },
      };
    case "insight":
      return {
        ...current,
        analysisError: null,
        snapshot: {
          ...snapshot,
          insights: uniqueInsights([...snapshot.insights, message.payload]),
        },
      };
    case "agent_status":
      return {
        ...current,
        snapshot: {
          ...snapshot,
          traces: uniqueTraces([...snapshot.traces, message.payload]),
        },
      };
    case "error":
      return { ...current, snapshot, analysisError: message.payload };
  }
}

export async function getEvents(
  matchId: string,
  signal: AbortSignal,
): Promise<Event[]> {
  const data = await request(
    `/matches/${encodeURIComponent(matchId)}/events`,
    signal,
  );
  if (!Array.isArray(data) || !data.every((item) => validEvent(item, matchId)))
    throw new Error("Event details are not in the expected format.");
  return mergeEvents(data);
}

export type Connection = "connecting" | "connected" | "reconnecting";
type Source = Pick<EventSource, "addEventListener" | "close" | "onerror">;
type ReplaySubscription = {
  initial: ReplaySnapshot;
  getCurrent?: () => ReplaySnapshot;
  onMessage: (message: StreamMessage) => void;
  onConnection: (connection: Connection) => void;
  onError: (message: string | null) => void;
  createSource?: (url: string) => Source;
};
type Subscription = {
  initial: ReplaySnapshot;
  onSnapshot: (snapshot: ReplaySnapshot) => void;
  onConnection: (connection: Connection) => void;
  onError: (message: string | null) => void;
  createSource?: (url: string) => Source;
};

export function subscribeToReplay({
  initial,
  getCurrent,
  onMessage,
  onConnection,
  onError,
  createSource = (url) => new EventSource(url),
}: ReplaySubscription): () => void {
  const replayId = initial.replay.replay_id;
  const matchId = initial.replay.match_id;
  let runId = initial.replay.run_id;
  let lastSeq = initial.replay.last_seq;
  let closed = false;
  const source = createSource(
    `${API}/replays/${encodeURIComponent(replayId)}/stream`,
  );
  onConnection("connecting");
  for (const kind of [
    "snapshot",
    "match_event",
    "match_state",
    "insight",
    "agent_status",
    "error",
  ] as const)
    source.addEventListener(kind, (event) => {
      if (closed) return;
      try {
        const message = JSON.parse(
          (event as MessageEvent<string>).data,
        ) as StreamMessage;
        if (
          !isObject(message) ||
          message.kind !== kind ||
          message.replay_id !== replayId
        )
          return;
        if (
          !isCount(message.seq) ||
          message.seq < 1 ||
          !isCount(message.run_id) ||
          message.run_id < 1
        ) {
          throw new Error("Invalid stream identity");
        }
        const current = getCurrent?.().replay;
        if (current) {
          runId = Math.max(runId, current.run_id);
          lastSeq = Math.max(lastSeq, current.last_seq);
        }
        if (message.run_id < runId || message.seq <= lastSeq) return;
        if (message.kind === "snapshot") {
          checkSnapshot(message.payload);
          if (
            message.payload.replay.replay_id !== replayId ||
            message.payload.replay.run_id !== message.run_id ||
            message.payload.replay.match_id !== matchId ||
            message.payload.replay.last_seq !== message.seq
          )
            throw new Error("Snapshot identity mismatch");
          replaceSnapshot(null, message.payload);
        } else {
          if (message.run_id !== runId)
            throw new Error("New generation requires a snapshot");
          const payload = message.payload;
          if (
            !(message.kind === "match_event"
              ? validEvent(payload, matchId)
              : message.kind === "match_state"
                ? validState(payload, matchId)
                : message.kind === "insight"
                  ? validInsight(payload, matchId)
                  : message.kind === "agent_status"
                    ? validTrace(payload)
                    : validError(payload))
          )
            throw new Error("Invalid update payload");
          if (
            message.kind === "insight" &&
            current &&
            message.payload.window.end_sec > current.clock_sec
          )
            throw new Error("Insight is ahead of replay");
        }
        runId = message.run_id;
        lastSeq = message.seq;
        onMessage(message);
        onConnection("connected");
        onError(null);
      } catch {
        onConnection("reconnecting");
        onError(
          "A replay update could not be read. Showing the last valid snapshot.",
        );
      }
    });
  source.onerror = (event) => {
    if (event && "data" in event) return; // Named business errors are handled above.
    if (closed) return;
    onConnection("reconnecting");
    onError(
      "Connection interrupted. Showing the last snapshot while reconnecting.",
    );
  };
  return () => {
    closed = true;
    source.close();
  };
}

/** Kept for existing A1 consumers; the integrated page listens to all six kinds. */
export function subscribeToSnapshots({
  onSnapshot,
  ...options
}: Subscription): () => void {
  return subscribeToReplay({
    ...options,
    onMessage: (message) => {
      if (message.kind === "snapshot") onSnapshot(message.payload);
    },
  });
}

export function formatClock(seconds: number): string {
  return `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
}

export function passAccuracy(completed: number, attempted: number): string {
  return attempted === 0
    ? "—"
    : `${Math.round((completed / attempted) * 100)}%`;
}
