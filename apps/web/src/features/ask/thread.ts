/**
 * The state of the question-and-answer thread.
 *
 * An answer is a list of segments. A segment is a piece of text with the quotes that
 * support it, so the page can show "text [1]" without parsing markers out of the text.
 */
import type { AskEvent, Citation, Source, Usage } from "@/lib/api/types";

export type TurnPhase =
  | "retrieving" // waiting for the passages
  | "answering" // the model is writing
  | "done"
  | "stopped" // the user stopped it
  | "failed";

export interface Segment {
  text: string;
  citations: Citation[];
}

export interface Turn {
  id: string;
  question: string;
  phase: TurnPhase;
  sources: Source[];
  segments: Segment[];
  /** True when at least one statement cites a source. Null until the answer is finished. */
  grounded: boolean | null;
  refused: boolean;
  model: string | null;
  usage: Usage | null;
  error: string | null;
  /** HTTP status when the request itself failed (503: answers are not configured). */
  errorStatus: number | null;
}

export type ThreadAction =
  | { type: "asked"; id: string; question: string }
  | { type: "event"; id: string; event: AskEvent }
  | { type: "closed"; id: string }
  | { type: "stopped"; id: string }
  | { type: "failed"; id: string; message: string; status: number | null }
  | { type: "cleared" };

export function isActive(turn: Turn): boolean {
  return turn.phase === "retrieving" || turn.phase === "answering";
}

function newTurn(id: string, question: string): Turn {
  return {
    id,
    question,
    phase: "retrieving",
    sources: [],
    segments: [],
    grounded: null,
    refused: false,
    model: null,
    usage: null,
    error: null,
    errorStatus: null,
  };
}

function withSegment(segments: Segment[], index: number, change: (s: Segment) => Segment): Segment[] {
  const next = segments.slice();
  // Segment numbers normally arrive in order; fill any gap so the index is valid.
  while (next.length <= index) next.push({ text: "", citations: [] });
  next[index] = change(next[index]!);
  return next;
}

function applyEvent(turn: Turn, event: AskEvent): Turn {
  switch (event.type) {
    case "sources":
      return { ...turn, phase: "answering", sources: event.sources };
    case "delta":
      return {
        ...turn,
        segments: withSegment(turn.segments, event.segment, (s) => ({
          ...s,
          text: s.text + event.text,
        })),
      };
    case "citation":
      // A quote can only be shown next to a passage we were given.
      if (!turn.sources[event.citation.source]) return turn;
      return {
        ...turn,
        segments: withSegment(turn.segments, event.segment, (s) => ({
          ...s,
          citations: [...s.citations, event.citation],
        })),
      };
    case "refusal":
      // Text written before a refusal is partial; replace it.
      return { ...turn, refused: true, segments: [{ text: event.text, citations: [] }] };
    case "done":
      return {
        ...turn,
        phase: "done",
        grounded: event.grounded,
        model: event.model,
        usage: event.usage,
      };
    case "error":
      return { ...turn, phase: "failed", error: event.detail };
  }
}

export function threadReducer(turns: Turn[], action: ThreadAction): Turn[] {
  if (action.type === "cleared") return [];
  if (action.type === "asked") return [...turns, newTurn(action.id, action.question)];

  return turns.map((turn) => {
    if (turn.id !== action.id) return turn;
    switch (action.type) {
      case "event":
        // Nothing may change a turn after it has ended.
        return isActive(turn) ? applyEvent(turn, action.event) : turn;
      case "closed":
        // The stream ended without a "done" event.
        return isActive(turn)
          ? { ...turn, phase: "failed", error: "The answer was cut off. Ask again." }
          : turn;
      case "stopped":
        return isActive(turn) ? { ...turn, phase: "stopped" } : turn;
      case "failed":
        return isActive(turn)
          ? { ...turn, phase: "failed", error: action.message, errorStatus: action.status }
          : turn;
    }
  });
}

/** The distinct sources a segment cites, in the order they were cited. */
export function citedSources(segment: Segment): number[] {
  return [...new Set(segment.citations.map((c) => c.source))];
}

/** Every quote the answer takes from one source. */
export function quotesFrom(turn: Turn, source: number): string[] {
  const quotes = turn.segments.flatMap((s) =>
    s.citations.filter((c) => c.source === source).map((c) => c.cited_text),
  );
  return [...new Set(quotes)];
}
