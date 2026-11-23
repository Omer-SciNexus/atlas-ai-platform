import { describe, expect, it } from "vitest";

import { parseSse, type SseMessage } from "./sse";

function streamOf(chunks: Array<string | Uint8Array>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk);
      }
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SseMessage[]> {
  const messages: SseMessage[] = [];
  for await (const message of parseSse(stream)) messages.push(message);
  return messages;
}

describe("parseSse", () => {
  it("reads events with a name and data", async () => {
    const messages = await collect(
      streamOf(['event: delta\ndata: {"text":"Hi"}\n\nevent: done\ndata: {}\n\n']),
    );
    expect(messages).toEqual([
      { event: "delta", data: '{"text":"Hi"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("joins an event that arrives in several chunks", async () => {
    const messages = await collect(streamOf(["event: de", 'lta\ndata: {"te', 'xt":"Hi"}\n', "\n"]));
    expect(messages).toEqual([{ event: "delta", data: '{"text":"Hi"}' }]);
  });

  it("keeps a multi-byte character that is cut between chunks", async () => {
    const bytes = new TextEncoder().encode("data: café ✓\n\n");
    const cut = bytes.indexOf(0xc3) + 1; // inside "é"
    const messages = await collect(streamOf([bytes.slice(0, cut), bytes.slice(cut)]));
    expect(messages).toEqual([{ event: "message", data: "café ✓" }]);
  });

  it("accepts CRLF line endings", async () => {
    const messages = await collect(streamOf(["event: done\r\ndata: {}\r\n\r\n"]));
    expect(messages).toEqual([{ event: "done", data: "{}" }]);
  });

  it("joins several data lines and skips comments", async () => {
    const messages = await collect(streamOf([": keep-alive\n\ndata: one\ndata: two\n\n"]));
    expect(messages).toEqual([{ event: "message", data: "one\ntwo" }]);
  });

  it("drops an event that is cut off at the end", async () => {
    const messages = await collect(streamOf(["data: whole\n\ndata: cut o"]));
    expect(messages).toEqual([{ event: "message", data: "whole" }]);
  });

  it("cancels the stream when the reader stops early", async () => {
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new TextEncoder().encode("data: again\n\n"));
      },
      cancel() {
        cancelled = true;
      },
    });
    for await (const message of parseSse(stream)) {
      expect(message.data).toBe("again");
      break;
    }
    expect(cancelled).toBe(true);
  });
});
