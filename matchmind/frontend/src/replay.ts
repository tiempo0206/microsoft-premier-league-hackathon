import type { Match, ReplaySnapshot, StreamMessage } from "./contract";

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
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method: body === undefined ? "GET" : "POST",
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
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
): Promise<ReplaySnapshot> {
  const data = await request("/replays", signal, {
    match_id: matchId,
    speed: 5,
  });
  checkSnapshot(data);
  if (data.replay.match_id !== matchId)
    throw new Error("The replay belongs to a different match.");
  return data;
}

export type Connection = "connecting" | "connected" | "reconnecting";
type Source = Pick<EventSource, "addEventListener" | "close" | "onerror">;
type Subscription = {
  initial: ReplaySnapshot;
  onSnapshot: (snapshot: ReplaySnapshot) => void;
  onConnection: (connection: Connection) => void;
  onError: (message: string | null) => void;
  createSource?: (url: string) => Source;
};

/** A1 consumes complete snapshots. Incremental stream kinds are added in A2. */
export function subscribeToSnapshots({
  initial,
  onSnapshot,
  onConnection,
  onError,
  createSource = (url) => new EventSource(url),
}: Subscription): () => void {
  const replayId = initial.replay.replay_id;
  const matchId = initial.replay.match_id;
  let runId = initial.replay.run_id;
  let lastSeq = initial.replay.last_seq;
  let closed = false;
  const source = createSource(
    `${API}/replays/${encodeURIComponent(replayId)}/stream`,
  );
  onConnection("connecting");
  source.addEventListener("snapshot", (event) => {
    if (closed) return;
    try {
      const message = JSON.parse(
        (event as MessageEvent<string>).data,
      ) as StreamMessage;
      if (
        !isObject(message) ||
        message.kind !== "snapshot" ||
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
      checkSnapshot(message.payload);
      if (
        message.payload.replay.replay_id !== replayId ||
        message.payload.replay.run_id !== message.run_id ||
        message.payload.replay.match_id !== matchId
      )
        throw new Error("Snapshot identity mismatch");
      if (message.run_id < runId || message.seq <= lastSeq) return;
      runId = message.run_id;
      lastSeq = message.seq;
      onSnapshot(message.payload);
      onConnection("connected");
      onError(null);
    } catch {
      onConnection("reconnecting");
      onError(
        "A replay update could not be read. Showing the last valid snapshot.",
      );
    }
  });
  source.onerror = () => {
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
