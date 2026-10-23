import { useEffect, useRef, useState } from "react";
import type { ControlReplay, Event, Match, ReplaySnapshot } from "./contract";
import {
  applyStreamMessage,
  controlReplay,
  createReplay,
  getEvents,
  getMatches,
  getReplay,
  mergeEvents,
  replaceSnapshot,
  subscribeToReplay,
  type Connection,
  type ReplayView,
} from "./replay";

type Operation = {
  initial: ReplaySnapshot;
  command: ControlReplay;
  key: string;
};

export function useReplay() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [view, setView] = useState<ReplayView | null>(null);
  const viewRef = useRef<ReplayView | null>(null);
  const [catalogueState, setCatalogueState] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const [sessionLoading, setSessionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [pending, setPending] = useState(false);
  const [retry, setRetry] = useState(0);
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [streamAttempt, setStreamAttempt] = useState(0);
  const [eventAttempt, setEventAttempt] = useState(0);
  const [eventCatalogue, setEventCatalogue] = useState<Event[]>([]);
  const createKey = useRef<{ matchId: string; key: string } | null>(null);
  const operation = useRef<Operation | null>(null);
  const controlRequest = useRef<AbortController | null>(null);

  function commit(next: ReplayView | null) {
    viewRef.current = next;
    setView(next);
  }

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
        if (!controller.signal.aborted) {
          setCatalogueState("error");
          setError(cause.message);
        }
      });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setSessionLoading(true);
    commit(null);
    setError(null);
    setStreamError(null);
    setControlError(null);
    setPending(false);
    operation.current = null;
    setConnection("connecting");
    if (createKey.current?.matchId !== selectedId)
      createKey.current = { matchId: selectedId, key: crypto.randomUUID() };
    createReplay(selectedId, controller.signal, createKey.current.key)
      .then((data) => {
        if (controller.signal.aborted) return;
        commit(replaceSnapshot(null, data));
        setSessionLoading(false);
      })
      .catch((cause: Error) => {
        if (!controller.signal.aborted) {
          setError(cause.message);
          setSessionLoading(false);
        }
      });
    return () => {
      controller.abort();
      controlRequest.current?.abort();
      controlRequest.current = null;
    };
  }, [selectedId, sessionAttempt]);

  useEffect(() => {
    const controller = new AbortController();
    setEventCatalogue([]);
    setEventError(null);
    if (selectedId)
      getEvents(selectedId, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) setEventCatalogue(data);
        })
        .catch((cause: Error) => {
          if (!controller.signal.aborted) setEventError(cause.message);
        });
    return () => controller.abort();
  }, [selectedId, eventAttempt]);

  const replayId = view?.snapshot.replay.replay_id;
  useEffect(() => {
    const initial = viewRef.current?.snapshot;
    if (!initial || initial.replay.match_id !== selectedId) return;
    return subscribeToReplay({
      initial,
      getCurrent: () => viewRef.current?.snapshot ?? initial,
      onMessage: (message) => {
        if (viewRef.current)
          commit(applyStreamMessage(viewRef.current, message));
      },
      onConnection: setConnection,
      onError: setStreamError,
    });
  }, [replayId, selectedId, streamAttempt]);

  async function sendOperation(next: Operation) {
    if (controlRequest.current) return;
    const controller = new AbortController();
    controlRequest.current = controller;
    operation.current = next;
    setPending(true);
    setControlError(null);
    try {
      const data = await controlReplay(
        next.initial,
        next.command,
        next.key,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (viewRef.current) commit(replaceSnapshot(viewRef.current, data));
      operation.current = null;
    } catch (cause) {
      if (!controller.signal.aborted) setControlError((cause as Error).message);
    } finally {
      if (controlRequest.current === controller) {
        controlRequest.current = null;
        setPending(false);
      }
    }
  }

  async function synchronize() {
    const initial = viewRef.current?.snapshot;
    if (!initial || controlRequest.current) return;
    const controller = new AbortController();
    controlRequest.current = controller;
    setPending(true);
    try {
      const data = await getReplay(initial, controller.signal);
      if (controller.signal.aborted) return;
      if (viewRef.current) commit(replaceSnapshot(viewRef.current, data));
      operation.current = null;
      setControlError(null);
    } catch (cause) {
      if (!controller.signal.aborted) setControlError((cause as Error).message);
    } finally {
      if (controlRequest.current === controller) {
        controlRequest.current = null;
        setPending(false);
      }
    }
  }

  const snapshot =
    view?.snapshot.replay.match_id === selectedId ? view.snapshot : null;
  const events = snapshot
    ? mergeEvents([
        ...eventCatalogue.filter(
          (e) => e.timestamp_sec <= snapshot.replay.clock_sec,
        ),
        ...(view?.events ?? []),
      ]).filter((e) => e.timestamp_sec <= snapshot.replay.clock_sec)
    : [];
  return {
    matches,
    selectedId,
    selectMatch: setSelectedId,
    snapshot,
    events,
    catalogueState,
    loading: catalogueState === "loading" || sessionLoading,
    error,
    streamError,
    controlError,
    eventError,
    analysisError: view?.analysisError ?? null,
    connection,
    pending,
    controlsDisabled: !snapshot || pending || !!controlError,
    control: (command: ControlReplay) => {
      const initial = viewRef.current?.snapshot;
      if (initial && !controlRequest.current && !operation.current)
        void sendOperation({ initial, command, key: crypto.randomUUID() });
    },
    retryControl: () => {
      if (operation.current) void sendOperation(operation.current);
    },
    synchronize: () => void synchronize(),
    retryEvents: () => setEventAttempt((value) => value + 1),
    retry: () =>
      catalogueState === "error"
        ? setRetry((value) => value + 1)
        : setSessionAttempt((value) => value + 1),
    reconnect: () => setStreamAttempt((value) => value + 1),
  };
}
