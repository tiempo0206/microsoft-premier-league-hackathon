import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { historicalReference as reference } from "../../frontend/src/historicalReference.ts";

const packageUrl = new URL(
  "../../data/extra/real-history-wyscout/",
  import.meta.url,
);
const manifest = JSON.parse(
  await readFile(new URL("manifest.json", packageUrl), "utf8"),
);
const match = JSON.parse(
  await readFile(new URL(manifest.sample.match_file, packageUrl), "utf8"),
);

test("displayed historical identity, date, score and credits agree with B's source", () => {
  assert.equal(reference.matchId, match.wyId);
  assert.equal(reference.date, match.dateutc.slice(0, 10));
  const sides = Object.values(match.teamsData);
  assert.equal(
    reference.fullTime.home,
    sides.find((t) => t.side === "home").score,
  );
  assert.equal(
    reference.fullTime.away,
    sides.find((t) => t.side === "away").score,
  );
  assert.equal(
    match.label,
    `${reference.home} - ${reference.away}, ${reference.fullTime.home} - ${reference.fullTime.away}`,
  );
  assert.equal(reference.provider, manifest.provider);
  assert.deepEqual(reference.authors, manifest.authors);
  assert.equal(reference.collection, manifest.collection);
  assert.equal(reference.license.replaceAll(" ", "-"), manifest.license);
  assert.equal(reference.licenseUrl, manifest.license_url);
  assert.equal(manifest.synthetic, false);
  assert.equal(manifest.runtime_compatible, false);
});

test("displayed excerpt count matches original first-half events in the stated window", async () => {
  const original = (
    await readFile(new URL(manifest.sample.events_file, packageUrl), "utf8")
  )
    .trim()
    .split("\n")
    .map(JSON.parse);
  const excerpt = original.filter(
    (event) =>
      event.matchId === reference.matchId &&
      event.matchPeriod === reference.clip.period &&
      reference.clip.startSec <= event.eventSec &&
      event.eventSec <= reference.clip.endSec,
  );
  assert.equal(excerpt.length, reference.clip.events);
  assert.deepEqual(
    [reference.clip.startSec, reference.clip.endSec],
    manifest.sample.clip_sec,
  );
});
