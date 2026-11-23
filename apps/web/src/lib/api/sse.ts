/**
 * A parser for server-sent events read from `fetch`.
 *
 * The browser's EventSource cannot be used for `/v1/ask`: it only sends GET requests and
 * cannot set the Authorization header.
 */

export interface SseMessage {
  event: string;
  data: string;
}

const BLANK_LINE = /\r?\n\r?\n/;

function parseBlock(block: string): SseMessage | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line === "" || line.startsWith(":")) continue; // empty or a comment (keep-alive)
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length > 0 ? { event, data: data.join("\n") } : null;
}

/**
 * Yield each complete event. Network chunks do not line up with events (one event can
 * arrive in pieces, and a multi-byte character can be cut in two), so text is buffered
 * until a blank line ends the event. An event that is cut off at the end is dropped.
 */
export async function* parseSse(stream: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  try {
    while (!finished) {
      const { done, value } = await reader.read();
      finished = done;
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      for (let match = BLANK_LINE.exec(buffer); match; match = BLANK_LINE.exec(buffer)) {
        const message = parseBlock(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
        if (message) yield message;
      }
    }
  } finally {
    // The consumer stopped early (or the read failed): tell the server we are done.
    if (!finished) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
