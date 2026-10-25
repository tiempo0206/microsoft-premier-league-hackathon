import type { Match } from "../../contracts/types";
import { formatClock } from "./replay";
import { historicalReference as reference } from "./historicalReference";

export function DataSources({ match }: { match?: Match }) {
  return (
    <details id="data-sources" className="data-sources">
      <summary>
        <span>About the data</span>
        <span className="data-sources-hint">
          Synthetic replay · Historical reference
        </span>
      </summary>
      <div className="data-sources-grid">
        <section aria-labelledby="replay-source-heading">
          <p className="source-status">Current replay · Synthetic</p>
          <h3 id="replay-source-heading">
            {match ? `${match.home} vs ${match.away}` : "Fictional match data"}
          </h3>
          <p>
            Original fictional teams and events. No real match date. Replay
            statistics and AI explanations use this synthetic dataset.
          </p>
        </section>
        <section aria-labelledby="historical-source-heading">
          <p className="source-status">Historical reference · Not played back</p>
          <h3 id="historical-source-heading">
            {reference.home} vs {reference.away}
          </h3>
          <p>
            <time dateTime={reference.date}>{reference.date}</time>
            {" · "}Source full-time result: {reference.fullTime.home}–
            {reference.fullTime.away}
          </p>
          <p>
            Research excerpt: first half, {formatClock(reference.clip.startSec)}–
            {formatClock(reference.clip.endSec)}, {reference.clip.events} recorded
            events. It is not connected to the replay or the model. It is used
            offline only, to check how closely our synthetic clip matches real
            football — and it did not change this replay.
          </p>
          <p>
            Data by {reference.authors.join(" and ")} ({reference.provider}).{" "}
            <a href={reference.collection}>Source collection</a>
            {" · "}
            <a href={reference.licenseUrl}>{reference.license}</a>.
          </p>
          <p className="source-changes">
            Selected one match and time window; reserialized the original fields
            and IDs. No tracking, possession or recovery events were added.
          </p>
        </section>
      </div>
    </details>
  );
}
