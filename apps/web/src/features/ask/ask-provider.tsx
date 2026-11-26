"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";

import { ApiError, errorMessage } from "@/lib/api/client";
import { askStream } from "@/lib/api/endpoints";

import { isActive, threadReducer, type Turn } from "./thread";

interface AskContextValue {
  turns: Turn[];
  /** True while an answer is being written. */
  busy: boolean;
  ask: (question: string) => void;
  stop: () => void;
  clear: () => void;
}

const AskContext = createContext<AskContextValue | null>(null);

/**
 * Holds the thread above the pages, so an answer keeps streaming (and the thread is still
 * there) when the user looks at another page. The API does not store conversations yet,
 * so the thread lasts until the page is reloaded.
 */
export function AskProvider({ children }: { children: ReactNode }) {
  const [turns, dispatch] = useReducer(threadReducer, []);
  const running = useRef<AbortController | null>(null);
  const counter = useRef(0);

  const stop = useCallback(() => running.current?.abort(), []);

  const ask = useCallback((question: string) => {
    running.current?.abort();
    const controller = new AbortController();
    running.current = controller;
    counter.current += 1;
    const id = `turn-${counter.current}`;
    dispatch({ type: "asked", id, question });

    void (async () => {
      try {
        for await (const event of askStream(question, controller.signal)) {
          dispatch({ type: "event", id, event });
        }
        dispatch({ type: "closed", id });
      } catch (error) {
        if (controller.signal.aborted) {
          dispatch({ type: "stopped", id });
        } else {
          dispatch({
            type: "failed",
            id,
            message: errorMessage(error),
            status: error instanceof ApiError ? error.status : null,
          });
        }
      } finally {
        if (running.current === controller) running.current = null;
      }
    })();
  }, []);

  const clear = useCallback(() => {
    running.current?.abort();
    dispatch({ type: "cleared" });
  }, []);

  // Leaving the app (sign-out) stops a running answer.
  useEffect(() => () => running.current?.abort(), []);

  const value = useMemo<AskContextValue>(() => {
    const last = turns.at(-1);
    return { turns, busy: last ? isActive(last) : false, ask, stop, clear };
  }, [turns, ask, stop, clear]);

  return <AskContext.Provider value={value}>{children}</AskContext.Provider>;
}

export function useAsk(): AskContextValue {
  const value = useContext(AskContext);
  if (!value) throw new Error("useAsk must be used inside AskProvider");
  return value;
}
