import http from "node:http";

// Manual browser fault injection; never imported by the app or run in CI.
// Start the upstream with MATCHMIND_MODEL_PROVIDER=mock. Health alone cannot
// attest which provider was configured. SIGUSR2 cuts the active SSE responses.
const usage = "node tests/frontend/browser-reconnect-proxy.mjs --upstream http://127.0.0.1:18400 --port 18401";
const log = (type, fields = {}) => console.log(JSON.stringify({ at: new Date().toISOString(), type, ...fields }));
const args = process.argv.slice(2);
if (args.length === 1 && args[0] === "--help") {
  console.log(`${usage}\nExplicit offline upstream required. Send SIGUSR2 to the printed PID once connected; Ctrl+C stops the proxy.`);
  process.exit(0);
}
const options = {};
for (let i = 0; i < args.length; i += 2) {
  if (!["--upstream", "--port"].includes(args[i]) || !args[i + 1] || options[args[i]]) {
    console.error(usage);
    process.exit(2);
  }
  options[args[i]] = args[i + 1];
}
let upstream;
const port = Number(options["--port"]);
try {
  upstream = new URL(options["--upstream"]);
  if (upstream.protocol !== "http:" || upstream.hostname !== "127.0.0.1" ||
      upstream.username || upstream.password || upstream.pathname !== "/" ||
      upstream.search || upstream.hash || !/^\d+$/.test(options["--port"] ?? "") ||
      !Number.isInteger(port) || port < 1024 || port > 65535 || Number(upstream.port || 80) === port) {
    throw new Error("loopback upstream and a distinct unprivileged port required");
  }
  const response = await fetch(new URL("/api/v1/health", upstream), {
    redirect: "error", signal: AbortSignal.timeout(5000),
  });
  const health = await response.json();
  if (!response.ok || health.contract_version !== "2.0.0" ||
      health.mode === "production" || health.model_ready !== false) {
    throw new Error("refusing production or model-ready upstream; use the explicit mock provider");
  }
} catch (error) {
  console.error(`Offline proxy refused: ${error.message}`);
  process.exit(2);
}

const streams = new Set();
const sockets = new Set();
let streamNumber = 0;
const server = http.createServer((request, response) => {
  if (!request.url?.startsWith("/") || request.url.startsWith("//")) {
    response.writeHead(400).end();
    return;
  }
  const isStream = /^\/api\/v1\/replays\/[^/]+\/stream$/.test(request.url);
  const record = { response, number: isStream ? ++streamNumber : null, cut: false };
  if (isStream) {
    streams.add(record);
    log("stream_request", { number: record.number, path: request.url,
      lastEventId: request.headers["last-event-id"] ?? null });
  }
  const outgoing = http.request(upstream, {
    method: request.method, path: request.url,
    headers: { ...request.headers, host: upstream.host },
  }, (incoming) => {
    response.writeHead(incoming.statusCode, incoming.headers);
    incoming.pipe(response);
    incoming.on("error", () => response.destroy());
  });
  outgoing.on("error", (error) => {
    if (!record.cut && !response.destroyed) {
      log("upstream_error", { code: error.code });
      if (!response.headersSent) response.writeHead(502);
      response.end();
    }
  });
  response.on("close", () => {
    if (isStream) {
      streams.delete(record);
      log("stream_closed", { number: record.number, injected: record.cut });
    }
    outgoing.destroy();
  });
  request.on("error", () => outgoing.destroy());
  request.pipe(outgoing);
});
server.on("connection", (socket) => {
  sockets.add(socket);
  socket.on("close", () => sockets.delete(socket));
});
process.on("SIGUSR2", () => {
  log("cut_requested", { activeStreams: streams.size });
  for (const record of streams) {
    record.cut = true;
    record.response.destroy();
  }
});
let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  log("stopping");
  server.close();
  for (const socket of sockets) socket.destroy();
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
server.on("error", (error) => {
  log("proxy_error", { code: error.code });
  process.exitCode = 1;
  stop();
});
server.listen(port, "127.0.0.1", () => log("ready", {
  pid: process.pid, origin: `http://127.0.0.1:${port}`, upstream: upstream.origin,
  faultSignal: "SIGUSR2", modelReady: false,
}));
