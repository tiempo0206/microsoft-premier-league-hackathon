import assert from "node:assert/strict";

/** Node-only adapter for manual probes; browser EventSource still handles production reconnects. */
export class HttpEventSource {
  listeners = new Map();
  onerror = null;
  controller = new AbortController();

  constructor(url) {
    this.run(url).catch((error) => {
      if (!this.controller.signal.aborted) this.onerror?.(error);
    });
  }

  addEventListener(kind, listener) {
    this.listeners.set(kind, listener);
  }

  close() {
    this.controller.abort();
  }

  async run(url) {
    const response = await fetch(url, { signal: this.controller.signal });
    assert.equal(response.status, 200);
    assert.match(
      response.headers.get("content-type") ?? "",
      /^text\/event-stream/,
    );
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        buffer = (
          buffer + decoder.decode(result.value, { stream: true })
        ).replaceAll("\r\n", "\n");
        let end;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          let kind = "";
          const data = [];
          for (const line of frame.split("\n")) {
            if (line.startsWith("event:")) kind = line.slice(6).trim();
            if (line.startsWith("data:")) data.push(line.slice(5).trim());
          }
          if (kind && data.length) {
            const event = { data: data.join("\n") };
            this.listeners.get(kind)?.(event);
            if (kind === "error") this.onerror?.(event);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}
