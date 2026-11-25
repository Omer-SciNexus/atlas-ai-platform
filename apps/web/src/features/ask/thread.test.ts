import { describe, expect, it } from "vitest";

import type { AskEvent, Citation, Source } from "@/lib/api/types";

import { citedSources, quotesFrom, threadReducer, type Turn } from "./thread";

function source(index: number): Source {
  return {
    index,
    chunk_id: `chunk-${index}`,
    document_id: "doc",
    document_title: "Annual report",
    heading: null,
    page: 1,
    score: 0.8,
    content: "Revenue rose 12%. Costs fell 3%.",
  };
}

function citation(sourceIndex: number, text: string): Citation {
  return {
    source: sourceIndex,
    document_id: "doc",
    document_title: "Annual report",
    page: 1,
    cited_text: text,
    start_char: 0,
    end_char: text.length,
  };
}

function play(events: AskEvent[]): Turn {
  let turns = threadReducer([], { type: "asked", id: "t1", question: "How did revenue change?" });
  for (const event of events) turns = threadReducer(turns, { type: "event", id: "t1", event });
  return turns[0]!;
}

const DONE: AskEvent = {
  type: "done",
  grounded: true,
  model: "claude",
  usage: { input_tokens: 10, output_tokens: 5 },
};

describe("threadReducer", () => {
  it("starts a turn that is waiting for passages", () => {
    const turn = play([]);
    expect(turn.phase).toBe("retrieving");
    expect(turn.segments).toEqual([]);
  });

  it("builds an answer from sources, text and citations", () => {
    const turn = play([
      { type: "sources", sources: [source(0), source(1)] },
      { type: "delta", segment: 0, text: "Revenue " },
      { type: "delta", segment: 0, text: "rose 12%." },
      { type: "citation", segment: 0, citation: citation(1, "Revenue rose 12%.") },
      { type: "delta", segment: 1, text: " Costs fell." },
      DONE,
    ]);
    expect(turn.phase).toBe("done");
    expect(turn.grounded).toBe(true);
    expect(turn.segments.map((s) => s.text)).toEqual(["Revenue rose 12%.", " Costs fell."]);
    expect(citedSources(turn.segments[0]!)).toEqual([1]);
    expect(turn.usage).toEqual({ input_tokens: 10, output_tokens: 5 });
  });

  it("moves to answering when the passages arrive", () => {
    expect(play([{ type: "sources", sources: [source(0)] }]).phase).toBe("answering");
  });

  it("ignores a citation for a passage it was not given", () => {
    const turn = play([
      { type: "sources", sources: [source(0)] },
      { type: "delta", segment: 0, text: "Text." },
      { type: "citation", segment: 0, citation: citation(5, "Text.") },
    ]);
    expect(turn.segments[0]!.citations).toEqual([]);
  });

  it("replaces partial text when the model refuses", () => {
    const turn = play([
      { type: "sources", sources: [source(0)] },
      { type: "delta", segment: 0, text: "Partial" },
      { type: "refusal", text: "I can't help with this request." },
      { ...DONE, grounded: false },
    ]);
    expect(turn.refused).toBe(true);
    expect(turn.segments).toEqual([{ text: "I can't help with this request.", citations: [] }]);
  });

  it("keeps the text written before an error in the stream", () => {
    const turn = play([
      { type: "sources", sources: [source(0)] },
      { type: "delta", segment: 0, text: "Revenue" },
      { type: "error", detail: "The model is temporarily unavailable." },
    ]);
    expect(turn.phase).toBe("failed");
    expect(turn.error).toBe("The model is temporarily unavailable.");
    expect(turn.segments[0]!.text).toBe("Revenue");
  });

  it("fails a turn whose stream ends without a done event", () => {
    let turns = threadReducer([], { type: "asked", id: "t1", question: "q" });
    turns = threadReducer(turns, { type: "closed", id: "t1" });
    expect(turns[0]!.phase).toBe("failed");
  });

  it("leaves a finished turn alone when the stream closes", () => {
    let turns = [play([{ type: "sources", sources: [] }, DONE])];
    turns = threadReducer(turns, { type: "closed", id: "t1" });
    expect(turns[0]!.phase).toBe("done");
  });

  it("does not change a stopped turn when late events arrive", () => {
    let turns = threadReducer([], { type: "asked", id: "t1", question: "q" });
    turns = threadReducer(turns, { type: "stopped", id: "t1" });
    turns = threadReducer(turns, {
      type: "event",
      id: "t1",
      event: { type: "delta", segment: 0, text: "late" },
    });
    expect(turns[0]!.phase).toBe("stopped");
    expect(turns[0]!.segments).toEqual([]);
  });

  it("records the status of a request that failed before streaming", () => {
    let turns = threadReducer([], { type: "asked", id: "t1", question: "q" });
    turns = threadReducer(turns, { type: "failed", id: "t1", message: "Not configured", status: 503 });
    expect(turns[0]).toMatchObject({ phase: "failed", error: "Not configured", errorStatus: 503 });
  });

  it("only changes the turn the action names", () => {
    let turns = threadReducer([], { type: "asked", id: "t1", question: "first" });
    turns = threadReducer(turns, { type: "asked", id: "t2", question: "second" });
    turns = threadReducer(turns, { type: "stopped", id: "t2" });
    expect(turns.map((t) => t.phase)).toEqual(["retrieving", "stopped"]);
  });

  it("clears the thread", () => {
    expect(threadReducer([play([])], { type: "cleared" })).toEqual([]);
  });
});

describe("quotesFrom", () => {
  it("lists each quote from a source once", () => {
    const turn = play([
      { type: "sources", sources: [source(0), source(1)] },
      { type: "delta", segment: 0, text: "A." },
      { type: "citation", segment: 0, citation: citation(0, "Revenue rose 12%.") },
      { type: "delta", segment: 1, text: "B." },
      { type: "citation", segment: 1, citation: citation(0, "Revenue rose 12%.") },
      { type: "citation", segment: 1, citation: citation(1, "Costs fell 3%.") },
    ]);
    expect(quotesFrom(turn, 0)).toEqual(["Revenue rose 12%."]);
    expect(quotesFrom(turn, 1)).toEqual(["Costs fell 3%."]);
  });
});
