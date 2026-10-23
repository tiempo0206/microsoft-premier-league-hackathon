import type { ReactNode } from "react";
import { formatClock, passAccuracy } from "./replay";
import { useReplay } from "./useReplay";

function Mark() {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <rect width="40" height="40" rx="12" fill="currentColor" />
      <path
        d="M10 28V13l10 10 10-10v15"
        stroke="#d8ed8d"
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M16 9a6 6 0 1 0-1.7 5.2M16 4v5h-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Team({ name, side }: { name: string; side: "home" | "away" }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("");
  return (
    <div className={`team team-${side}`}>
      <div className="team-crest" aria-hidden="true">
        <span>{initials}</span>
        <svg viewBox="0 0 56 64" fill="none">
          <path
            d="M4 4h48v30c0 14-24 26-24 26S4 48 4 34V4Z"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <path
            d="M10 10h36v23c0 10-18 20-18 20S10 43 10 33V10Z"
            stroke="currentColor"
            strokeOpacity=".3"
          />
        </svg>
      </div>
      <strong>{name}</strong>
      <span className="team-label">{side === "home" ? "Home" : "Away"}</span>
    </div>
  );
}

function Stat({
  label,
  home,
  away,
  homeValue,
  awayValue,
}: {
  label: string;
  home?: number;
  away?: number;
  homeValue?: string;
  awayValue?: string;
}) {
  const total = (home ?? 0) + (away ?? 0);
  return (
    <div className="stat">
      <div className="stat-values">
        <strong>{homeValue ?? home ?? "—"}</strong>
        <span>{label}</span>
        <strong>{awayValue ?? away ?? "—"}</strong>
      </div>
      <div className="stat-bars" aria-hidden="true">
        <span>
          <i style={{ width: `${total ? ((home ?? 0) / total) * 100 : 0}%` }} />
        </span>
        <span>
          <i style={{ width: `${total ? ((away ?? 0) / total) * 100 : 0}%` }} />
        </span>
      </div>
    </div>
  );
}

function Detail({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="detail">
      <span className="detail-number">{number}</span>
      <div>
        <h3>{title}</h3>
        <p>{children}</p>
      </div>
    </div>
  );
}

export default function App() {
  const replay = useReplay();
  const match = replay.matches.find(
    (item) => item.match_id === replay.selectedId,
  );
  const { snapshot } = replay;
  const state = snapshot?.state;
  const clock = snapshot?.replay.clock_sec ?? match?.clip_start_sec;
  const clipDuration = match ? match.clip_end_sec - match.clip_start_sec : 300;
  const elapsed =
    match && clock !== undefined
      ? Math.max(0, Math.min(clipDuration, clock - match.clip_start_sec))
      : 0;
  const statusLabels = {
    idle: "Ready to replay",
    playing: "Replay in progress",
    paused: "Replay paused",
    ended: "Clip complete",
  };
  const status = snapshot
    ? statusLabels[snapshot.replay.status]
    : replay.loading
      ? "Getting the match ready"
      : "Replay unavailable";
  const empty =
    replay.catalogueState === "ready" && replay.matches.length === 0;

  return (
    <>
      <a className="skip-link" href="#match-centre">
        Skip to match centre
      </a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="/" aria-label="MatchMind home">
            <Mark />
            <span>
              MatchMind<span className="brand-dot">.</span>
            </span>
          </a>
          <span className="header-section">
            <span />
            Match centre
          </span>
          <span className="header-note">
            A new perspective on the game <span aria-hidden="true">↗</span>
          </span>
        </div>
      </header>

      <main id="match-centre" className="page">
        <section className="intro" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">
              <span className="tiny-pitch" aria-hidden="true" />
              THE GAME, IN FOCUS
            </p>
            <h1 id="page-title">
              Every match has
              <br />a story to tell<span>.</span>
            </h1>
            <p className="intro-copy">
              Get closer to the game, one moment at a time.
            </p>
          </div>
          <div className="clip-select">
            <label htmlFor="match-select">YOUR MATCH</label>
            <div className="select-shell">
              <select
                id="match-select"
                value={replay.selectedId}
                onChange={(event) => replay.selectMatch(event.target.value)}
                disabled={replay.catalogueState !== "ready" || empty}
              >
                {!match && (
                  <option value="">
                    {empty
                      ? "No clips available"
                      : replay.catalogueState === "error"
                        ? "Match unavailable"
                        : "Loading match…"}
                  </option>
                )}
                {replay.matches.map((item) => (
                  <option key={item.match_id} value={item.match_id}>
                    {item.home} vs {item.away}
                  </option>
                ))}
              </select>
              <span aria-hidden="true">⌄</span>
            </div>
            <div className="clip-select-note">
              <span className="synthetic-small">SYNTHETIC</span>
              <span>
                {match
                  ? `${formatClock(match.clip_start_sec)}–${formatClock(match.clip_end_sec)} · ${clipDuration / 60} min clip`
                  : "Original fictional match data"}
              </span>
            </div>
          </div>
        </section>

        {replay.error && (
          <div className="notice error-notice" role="alert">
            <div>
              <strong>We couldn’t load your replay.</strong>
              <p>{replay.error}</p>
            </div>
            <button className="retry-button" onClick={replay.retry}>
              <RefreshIcon />
              Try again
            </button>
          </div>
        )}
        {replay.streamError && !replay.error && (
          <div className="notice" role="alert">
            <div>
              <strong>Reconnecting to your match</strong>
              <p>{replay.streamError}</p>
            </div>
            <button className="retry-button" onClick={replay.reconnect}>
              <RefreshIcon />
              Reconnect
            </button>
          </div>
        )}
        {empty && (
          <div className="notice" role="status">
            <div>
              <strong>No replay clips available yet.</strong>
              <p>Check back when a synthetic match has been added.</p>
            </div>
          </div>
        )}

        {replay.controlError && (
          <div className="notice error-notice" role="alert">
            <div>
              <strong>The command could not be confirmed.</strong>
              <p>
                {replay.controlError} Retry the same command, or sync the
                current server state.
              </p>
            </div>
            <div className="notice-actions">
              <button
                className="retry-button"
                disabled={replay.pending}
                onClick={replay.retryControl}
              >
                Retry command
              </button>
              <button
                className="retry-button"
                disabled={replay.pending}
                onClick={replay.synchronize}
              >
                Sync replay
              </button>
            </div>
          </div>
        )}

        <section className="playback-controls" aria-label="Playback controls">
          <div className="playback-buttons">
            <button
              className="primary-button"
              disabled={
                replay.controlsDisabled || snapshot?.replay.status === "ended"
              }
              onClick={() =>
                replay.control({
                  action:
                    snapshot?.replay.status === "playing" ? "pause" : "play",
                })
              }
            >
              <span aria-hidden="true">
                {snapshot?.replay.status === "playing" ? "Ⅱ" : "▶"}
              </span>{" "}
              {snapshot?.replay.status === "playing" ? "Pause" : "Play"}
            </button>
            <button
              className="secondary-button"
              disabled={replay.controlsDisabled}
              onClick={() => replay.control({ action: "reset" })}
            >
              <RefreshIcon /> Reset
            </button>
          </div>
          <div className="speed-control">
            <label htmlFor="replay-speed">Playback speed</label>
            <select
              id="replay-speed"
              value={snapshot?.replay.speed ?? 5}
              disabled={replay.controlsDisabled}
              onChange={(event) =>
                replay.control({
                  action: "set_speed",
                  speed: Number(event.target.value) as 1 | 2 | 5 | 10,
                })
              }
            >
              {[1, 2, 5, 10].map((speed) => (
                <option key={speed} value={speed}>
                  {speed}×
                </option>
              ))}
            </select>
          </div>
          <p role="status">
            {replay.pending
              ? "Confirming command…"
              : snapshot?.replay.status === "ended"
                ? "Clip ended. Reset to play again."
                : "Server clock · Statistics follow the replay"}
          </p>
        </section>

        <div className="match-grid" aria-busy={replay.loading}>
          <section
            className={`match-board${replay.loading ? " is-loading" : ""}`}
            aria-labelledby="match-heading"
          >
            <div className="board-top">
              <h2 id="match-heading">MATCH OVERVIEW</h2>
              <span className="synthetic-badge">
                <span />
                SYNTHETIC REPLAY
              </span>
            </div>
            <div className="scoreboard">
              <Team name={match?.home ?? "Home team"} side="home" />
              <div className="score-centre">
                <span className="period-label">
                  {match
                    ? match.period === 2
                      ? "SECOND HALF"
                      : "FIRST HALF"
                    : "MATCH CLIP"}
                </span>
                <div
                  className="score"
                  aria-label={
                    state
                      ? `${match?.home} ${state.score.HOME}, ${match?.away} ${state.score.AWAY}`
                      : replay.loading
                        ? "Score loading"
                        : "Score unavailable"
                  }
                >
                  <span>{state?.score.HOME ?? "—"}</span>
                  <span className="score-divider">:</span>
                  <span>{state?.score.AWAY ?? "—"}</span>
                </div>
                <span className="match-clock" aria-label="Match clock">
                  {clock === undefined ? "—:—" : formatClock(clock)}
                </span>
              </div>
              <Team name={match?.away ?? "Away team"} side="away" />
            </div>
            <div className="pitch-illustration" aria-hidden="true">
              <svg viewBox="0 0 720 218" fill="none">
                <defs>
                  <pattern
                    id="grass"
                    width="80"
                    height="218"
                    patternUnits="userSpaceOnUse"
                  >
                    <rect
                      width="40"
                      height="218"
                      fill="white"
                      fillOpacity=".018"
                    />
                  </pattern>
                </defs>
                <rect x="1" y="1" width="718" height="216" fill="url(#grass)" />
                <g stroke="currentColor" strokeWidth="1.3">
                  <rect x="26" y="17" width="668" height="184" rx="2" />
                  <path d="M360 17v184M26 49h90v120H26m668-120h-90v120h90M26 79h34v60H26m668-60h-34v60h34" />
                  <circle cx="360" cy="109" r="48" />
                  <path d="M116 75a43 43 0 0 1 0 68m488-68a43 43 0 0 0 0 68" />
                </g>
                <circle cx="360" cy="109" r="3" fill="currentColor" />
                <circle cx="83" cy="109" r="2" fill="currentColor" />
                <circle cx="637" cy="109" r="2" fill="currentColor" />
              </svg>
              <div className="pitch-caption">
                <span className="pitch-line" />A closer look at the beautiful
                game
                <span className="pitch-line" />
              </div>
            </div>
            <div className="board-bottom">
              <span className="replay-status">
                <span
                  className={`status-dot ${snapshot?.replay.status === "playing" ? "playing" : ""}`}
                />
                {status}
              </span>
              <span>
                {match
                  ? `${formatClock(match.clip_start_sec)} — ${formatClock(match.clip_end_sec)}`
                  : "Five-minute synthetic clip"}
              </span>
            </div>
          </section>

          <section className="stats-panel" aria-labelledby="stats-heading">
            <div className="panel-heading">
              <p className="eyebrow">THE NUMBERS</p>
              <h2 id="stats-heading">Match statistics</h2>
              <p>Same match. A little more perspective.</p>
            </div>
            <div className="team-key">
              <span>
                <i className="home-key" />
                {match?.home ?? "Home"}
              </span>
              <span>
                {match?.away ?? "Away"}
                <i className="away-key" />
              </span>
            </div>
            <Stat
              label="Shots"
              home={state?.shots.HOME}
              away={state?.shots.AWAY}
            />
            <Stat
              label="Passes"
              home={state?.passes.HOME}
              away={state?.passes.AWAY}
            />
            <Stat
              label="Pass accuracy"
              home={
                state
                  ? state.passes.HOME
                    ? state.completed_passes.HOME / state.passes.HOME
                    : 0
                  : undefined
              }
              away={
                state
                  ? state.passes.AWAY
                    ? state.completed_passes.AWAY / state.passes.AWAY
                    : 0
                  : undefined
              }
              homeValue={
                state
                  ? passAccuracy(state.completed_passes.HOME, state.passes.HOME)
                  : "—"
              }
              awayValue={
                state
                  ? passAccuracy(state.completed_passes.AWAY, state.passes.AWAY)
                  : "—"
              }
            />
            <Stat
              label="Possession time"
              home={state?.possession_seconds.HOME}
              away={state?.possession_seconds.AWAY}
              homeValue={state ? `${state.possession_seconds.HOME}s` : "—"}
              awayValue={state ? `${state.possession_seconds.AWAY}s` : "—"}
            />
            <p className="stats-footnote">
              Possession time is estimated from the synthetic event sequence.
            </p>
          </section>
        </div>

        <section className="replay-strip" aria-label="Replay progress">
          <div className="strip-label">
            <span className="strip-icon" aria-hidden="true">
              ↳
            </span>
            <div>
              <strong>Inside this replay</strong>
              <span>
                {match
                  ? `${clipDuration / 60} minutes of synthetic football`
                  : "Waiting for match details"}
              </span>
            </div>
          </div>
          <div className="progress-wrap">
            <div className="progress-labels">
              <span>{match ? formatClock(match.clip_start_sec) : "—:—"}</span>
              <span>{match ? formatClock(match.clip_end_sec) : "—:—"}</span>
            </div>
            <progress
              max={clipDuration}
              value={elapsed}
              aria-label="Replay progress"
            />
          </div>
          <div
            className={`feed-status ${replay.connection === "connected" && !replay.error ? "feed-connected" : ""}`}
            role="status"
          >
            <span />
            <div>
              <strong>
                {replay.error
                  ? "Feed unavailable"
                  : replay.connection === "connected"
                    ? "Snapshot feed connected"
                    : replay.connection === "reconnecting"
                      ? "Reconnecting to feed"
                      : "Connecting to feed"}
              </strong>
              <span>
                {snapshot
                  ? `Session ${snapshot.replay.replay_id.slice(-8)} · Run ${snapshot.replay.run_id}`
                  : "Waiting for a replay session"}
              </span>
            </div>
          </div>
        </section>

        <section className="details" aria-label="About this replay">
          <Detail number="01" title="Synthetic by design">
            Fictional teams and original events. A clearly labelled space to
            explore the game.
          </Detail>
          <Detail number="02" title="Every number, in context">
            Match statistics reflect the current replay snapshot, from the
            opening moment onward.
          </Detail>
          <Detail number="03" title="A five-minute perspective">
            One focused match segment. All times shown are match time, not a
            full-game result.
          </Detail>
        </section>
        <footer className="page-footer">
          <span>
            MatchMind<span className="brand-dot">.</span>{" "}
            <span className="footer-tagline">Make sense of the moments.</span>
          </span>
          <span>Synthetic football · Original data · No match footage</span>
        </footer>
      </main>
    </>
  );
}
