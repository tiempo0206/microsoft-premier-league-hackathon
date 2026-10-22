import { useEffect, useRef, useState } from "react";
import type { Match, ReplaySnapshot } from "./contract";
import {
  createReplay,
  getMatches,
  subscribeToSnapshots,
  type Connection,
} from "./replay";

export function useReplay() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [snapshot, setSnapshot] = useState<ReplaySnapshot | null>(null);
  const [catalogueState, setCatalogueState] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const [sessionLoading, setSessionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [retry, setRetry] = useState(0);
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [streamAttempt, setStreamAttempt] = useState(0);
  const initialSnapshot = useRef<ReplaySnapshot | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogueState("loading");
    setError(null);
    getMatches(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setMatches(data);
        setSelectedId((previous) =>
          data.some((match) => match.match_id === previous)
            ? previous
            : (data[0]?.match_id ?? ""),
        );
        setCatalogueState("ready");
      })
      .catch((cause: Error) => {
        if (controller.signal.aborted) return;
        setCatalogueState("error");
        setError(cause.message);
      });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setSessionLoading(true);
    setSnapshot(null);
    initialSnapshot.current = null;
    setError(null);
    setStreamError(null);
    setConnection("connecting");
    createReplay(selectedId, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        initialSnapshot.current = data;
        setSnapshot(data);
        setSessionLoading(false);
      })
      .catch((cause: Error) => {
        if (controller.signal.aborted) return;
        setError(cause.message);
        setSessionLoading(false);
      });
    return () => controller.abort();
  }, [selectedId, sessionAttempt]);

  const replayId = snapshot?.replay.replay_id;
  useEffect(() => {
    if (
      !replayId ||
      !initialSnapshot.current ||
      initialSnapshot.current.replay.match_id !== selectedId
    )
      return;
    return subscribeToSnapshots({
      initial: initialSnapshot.current,
      onSnapshot: (data) => {
        initialSnapshot.current = data;
        setSnapshot(data);
      },
      onConnection: setConnection,
      onError: setStreamError,
    });
  }, [replayId, selectedId, streamAttempt]);

  return {
    matches,
    selectedId,
    selectMatch: setSelectedId,
    snapshot,
    catalogueState,
    loading: catalogueState === "loading" || sessionLoading,
    error,
    streamError,
    connection,
    retry: () =>
      catalogueState === "error"
        ? setRetry((value) => value + 1)
        : setSessionAttempt((value) => value + 1),
    reconnect: () => setStreamAttempt((value) => value + 1),
  };
}
