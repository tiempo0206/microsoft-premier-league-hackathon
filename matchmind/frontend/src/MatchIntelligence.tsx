import { useEffect, useRef, useState } from "react";
import type { ErrorInfo, Event, Match, ReplaySnapshot } from "./contract";
import { formatClock } from "./replay";

type Props = {
  match: Match;
  snapshot: ReplaySnapshot;
  events: Event[];
  eventError: string | null;
  analysisError: ErrorInfo | null;
  retryEvents: () => void;
};
const sourceLabels = {
  live_model: "Live model",
  rule_fallback: "Rule fallback",
  precomputed: "Precomputed",
};
const eventLabel = (event: Event) =>
  `${formatClock(event.timestamp_sec)} · ${event.type} · ${event.player_id}`;

export function MatchIntelligence({
  match,
  snapshot,
  events,
  eventError,
  analysisError,
  retryEvents,
}: Props) {
  const [audience, setAudience] = useState<"casual" | "analyst">("casual");
  const [selectedInsightId, setSelectedInsightId] = useState("");
  const [selectedEventId, setSelectedEventId] = useState("");
  const timeline = useRef<HTMLDivElement>(null);
  const selectedButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const list = timeline.current,
      button = selectedButton.current;
    if (list && button)
      list.scrollTo({
        top:
          list.scrollTop +
          button.getBoundingClientRect().top -
          list.getBoundingClientRect().top -
          12,
        behavior: "smooth",
      });
  }, [selectedEventId]);
  const insights = snapshot.insights;
  const active =
    insights.find((item) => item.insight_id === selectedInsightId) ??
    insights.at(-1);
  const evidenceIds = new Set(active?.evidence_event_ids ?? []);
  const selected = events.find((event) => event.event_id === selectedEventId);
  const pitchEvents = active
    ? events.filter((event) => evidenceIds.has(event.event_id))
    : events.slice(-12);
  const teamName = (team: string) =>
    team === "HOME" ? match.home : match.away;
  function selectEvent(eventId: string, insightId?: string) {
    if (insightId) setSelectedInsightId(insightId);
    setSelectedEventId(eventId);
  }
  return (
    <section className="intelligence" aria-labelledby="insight-heading">
      <div className="intelligence-heading">
        <div>
          <p className="eyebrow">BEYOND THE SCORELINE</p>
          <h2 id="insight-heading">
            The story behind the moments<span>.</span>
          </h2>
          <p>One set of evidence. Your way into the game.</p>
        </div>
        <fieldset className="audience-switch">
          <legend>Audience mode</legend>
          {(["casual", "analyst"] as const).map((mode) => (
            <label key={mode} className={audience === mode ? "selected" : ""}>
              <input
                type="radio"
                name="audience"
                value={mode}
                checked={audience === mode}
                onChange={() => setAudience(mode)}
              />
              <span>{mode === "casual" ? "Casual" : "Analyst"}</span>
            </label>
          ))}
        </fieldset>
      </div>
      {analysisError && (
        <div className="notice" role="alert">
          <div>
            <strong>Analysis unavailable · Replay continues</strong>
            <p>{analysisError.message}</p>
          </div>
          <span className="source-badge">{analysisError.code}</span>
        </div>
      )}
      <div className="intelligence-grid">
        <div className="insight-column">
          {insights.length === 0 && (
            <div className="insight-empty" role="status">
              <span className="empty-symbol" aria-hidden="true">
                ↗
              </span>
              <p className="eyebrow">ROOM FOR A NEW PERSPECTIVE</p>
              <h3>
                {snapshot.replay.clock_sec < 1650
                  ? "Let the story unfold."
                  : "No insight published for this window."}
              </h3>
              <p>
                {snapshot.replay.clock_sec < 1650
                  ? "Play past 27:30 to analyse the 25:00–27:30 window. You can pause while the explanation arrives."
                  : "The event feed and match statistics remain available. Analysis is published only when the server returns a result."}
              </p>
            </div>
          )}
          {[...insights].reverse().map((insight) => (
            <article
              className={`insight-card ${active?.insight_id === insight.insight_id ? "active-insight" : ""}`}
              key={insight.insight_id}
            >
              <div className="insight-meta">
                <span
                  className={`source-badge source-${insight.generation.mode}`}
                >
                  {sourceLabels[insight.generation.mode]}
                </span>
                <span>
                  {formatClock(insight.window.start_sec)}–
                  {formatClock(insight.window.end_sec)}
                </span>
              </div>
              <h3>{insight.display.title}</h3>
              <p
                className="insight-narrative"
                data-testid={`narrative-${insight.insight_id}`}
              >
                {insight.narratives[audience]}
              </p>
              <div className="insight-numbers">
                <div>
                  <strong>{insight.metrics.high_recoveries}</strong>
                  <span>High recoveries</span>
                </div>
                <div>
                  <strong>{insight.metrics.linked_shots}</strong>
                  <span>Recoveries linked to shots</span>
                </div>
                <div>
                  <strong>{insight.metrics.window_seconds}s</strong>
                  <span>Analysis window</span>
                </div>
              </div>
              <div className="verification-label">
                <span aria-hidden="true">✓</span> Evidence checked{" "}
                <span>
                  ·{" "}
                  {insight.verification.method === "agent_and_code"
                    ? "Agent + code"
                    : "Code only"}
                </span>
              </div>
              <details className="evidence-details">
                <summary>
                  Explore evidence · {insight.evidence_event_ids.length} events
                </summary>
                <p className="evidence-help">
                  Select an event to highlight its recorded position. The replay
                  clock stays where it is.
                </p>
                <div className="evidence-buttons">
                  {insight.evidence_event_ids.map((id) => {
                    const event = events.find((item) => item.event_id === id);
                    return (
                      <button
                        key={id}
                        disabled={!event}
                        aria-pressed={
                          selectedEventId === id &&
                          active?.insight_id === insight.insight_id
                        }
                        onClick={() => selectEvent(id, insight.insight_id)}
                      >
                        {id}
                        <span>
                          {event
                            ? `${formatClock(event.timestamp_sec)} · ${event.type}`
                            : "Details unavailable"}
                        </span>
                      </button>
                    );
                  })}
                </div>
                <h4>Claims behind this explanation</h4>
                <ul className="claim-list">
                  {insight.claims.map((claim) => (
                    <li key={claim.claim_id}>{claim.text}</li>
                  ))}
                </ul>
                {insight.verification.rejected_claims.length > 0 && (
                  <p className="audit-note">
                    Removed claims:{" "}
                    {insight.verification.rejected_claims.join("; ")}
                  </p>
                )}
                <p className="evidence-help">
                  Checks cover supplied event references and metrics
                  {insight.verification.method === "agent_and_code"
                    ? ", with an agent review of the explanation"
                    : ""}
                  . They do not prove tactical causality.
                </p>
                <p className="source-detail">
                  Source: {insight.generation.provider}
                  {insight.generation.model
                    ? ` · ${insight.generation.model}`
                    : " · No live model"}{" "}
                  · {insight.insight_id}
                </p>
              </details>
            </article>
          ))}
          <details className="agent-details" open={snapshot.traces.length > 0}>
            <summary>
              Analysis activity{" "}
              <span>
                {snapshot.traces.length
                  ? `${snapshot.traces.length} recorded steps`
                  : "No steps reported yet"}
              </span>
            </summary>
            {snapshot.traces.length ? (
              <ol>
                {snapshot.traces.map((trace, index) => (
                  <li
                    key={`${trace.task_id}-${trace.agent}-${trace.status}-${index}`}
                  >
                    <div>
                      <strong>{trace.agent}</strong>
                      <span className={`trace-status trace-${trace.status}`}>
                        {trace.status}
                      </span>
                      <span>{trace.duration_ms} ms</span>
                    </div>
                    <p>{trace.note}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="evidence-help">
                Stages appear only when the server reports them. No live model
                activity is implied.
              </p>
            )}
          </details>
        </div>
        <div className="event-column">
          <section
            className="evidence-panel"
            aria-labelledby="evidence-heading"
          >
            <div className="evidence-panel-heading">
              <p className="eyebrow">FOLLOW THE EVIDENCE</p>
              <h3 id="evidence-heading">Where it happened</h3>
              <p>Recorded event points · No player tracking</p>
            </div>
            <div className="evidence-pitch">
              <svg
                viewBox="0 0 100 64"
                role="img"
                aria-label={
                  selected
                    ? `Recorded position of ${selected.event_id}: x ${selected.position.x}, y ${selected.position.y}`
                    : "Recorded positions of recent events or selected insight evidence"
                }
              >
                <rect x="1" y="1" width="98" height="62" rx="1" fill="none" />
                <path d="M50 1v62M1 13h16v38H1m98-38H83v38h16M1 24h6v16H1m98-16h-6v16h6" />
                <circle cx="50" cy="32" r="10" />
                {selected?.end_position && (
                  <line
                    className="selected-event-line"
                    x1={selected.position.x}
                    y1={selected.position.y * 0.64}
                    x2={selected.end_position.x}
                    y2={selected.end_position.y * 0.64}
                  />
                )}
                {pitchEvents
                  .filter((event) => event.event_id !== selected?.event_id)
                  .map((event) => (
                    <circle
                      className={`event-point point-${event.team_id}`}
                      key={event.event_id}
                      cx={event.position.x}
                      cy={event.position.y * 0.64}
                      r="1.3"
                    />
                  ))}
                {selected && (
                  <g
                    className="selected-event-point"
                    data-testid="selected-event-point"
                  >
                    <circle
                      cx={selected.position.x}
                      cy={selected.position.y * 0.64}
                      r="3"
                    />
                    <circle
                      cx={selected.position.x}
                      cy={selected.position.y * 0.64}
                      r="1.3"
                    />
                  </g>
                )}
              </svg>
            </div>
            <div className="pitch-team-key">
              <span>
                <i />
                {match.home}
              </span>
              <span>
                <i />
                {match.away}
              </span>
            </div>
            <div className="selected-event" role="status">
              {selected ? (
                <>
                  <strong>
                    {selected.event_id} · {eventLabel(selected)}
                  </strong>
                  <p>
                    {teamName(selected.team_id)} ·{" "}
                    {selected.outcome.replaceAll("_", " ")} · (
                    {selected.position.x}, {selected.position.y})
                  </p>
                </>
              ) : (
                <>
                  <strong>Select an event to look closer</strong>
                  <p>Use an evidence button or the event list below.</p>
                </>
              )}
            </div>
          </section>
          <section className="event-panel" aria-labelledby="event-heading">
            <div className="event-panel-title">
              <h3 id="event-heading">Event timeline</h3>
              <span>{events.length} observed</span>
            </div>
            {eventError && (
              <div className="event-warning" role="alert">
                <p>
                  {eventError} Some historical event details may be missing.
                </p>
                <button className="secondary-button" onClick={retryEvents}>
                  Retry event details
                </button>
              </div>
            )}
            <div
              ref={timeline}
              className="event-list"
              tabIndex={0}
              role="region"
              aria-label="Observed events"
            >
              <ol>
                {[...events].reverse().map((event) => (
                  <li key={event.event_id}>
                    <button
                      ref={
                        selectedEventId === event.event_id
                          ? selectedButton
                          : undefined
                      }
                      className={`${event.team_id === "HOME" ? "home-event" : "away-event"} ${evidenceIds.has(event.event_id) ? "evidence-event" : ""}`}
                      aria-pressed={selectedEventId === event.event_id}
                      onClick={() => selectEvent(event.event_id)}
                    >
                      <time>{formatClock(event.timestamp_sec)}</time>
                      <span>
                        <strong>{event.type.replaceAll("_", " ")}</strong>
                        <span>
                          {teamName(event.team_id)} · {event.player_id}
                        </span>
                      </span>
                      <span className="event-id">
                        {event.event_id}
                        {evidenceIds.has(event.event_id) && (
                          <i aria-label="Insight evidence">↗</i>
                        )}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
              {events.length === 0 && (
                <p className="timeline-empty">
                  Events appear as the replay advances.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
      <p className="mode-footnote">
        Casual and Analyst use the same insight, claims and evidence. Switching
        modes makes no model request.
      </p>
    </section>
  );
}
