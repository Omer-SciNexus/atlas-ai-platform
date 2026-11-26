"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SourceCard } from "@/components/source-card";

import { quotesFrom, type Turn } from "./thread";

interface SourcesPanelProps {
  turn: Turn;
  /** The source to bring into view, or null to show the list from the top. */
  focusedSource: number | null;
  onClose: () => void;
}

/** The passages the answer was written from. A column on wide screens, an overlay on small ones. */
export function SourcesPanel({ turn, focusedSource, onClose }: SourcesPanelProps) {
  const focused = useRef<HTMLLIElement>(null);

  useEffect(() => {
    focused.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [turn.id, focusedSource]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div aria-hidden onClick={onClose} className="fixed inset-0 z-20 bg-[#080e1c]/50 lg:hidden" />
      <aside
        aria-label="Sources"
        className="fixed inset-y-0 right-0 z-30 flex w-[min(26rem,100vw)] animate-slide-in flex-col border-l border-line bg-surface shadow-2xl lg:static lg:z-auto lg:w-[26rem] lg:shrink-0 lg:shadow-none"
      >
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line px-4">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Sources</h2>
            <p className="truncate text-xs text-muted" title={turn.question}>
              {turn.question}
            </p>
          </div>
          <Button variant="ghost" size="icon" aria-label="Close sources" onClick={onClose}>
            <X aria-hidden className="size-4" />
          </Button>
        </header>
        <ol className="flex-1 space-y-3 overflow-y-auto p-4">
          {turn.sources.map((source) => {
            const quotes = quotesFrom(turn, source.index);
            const isFocused = source.index === focusedSource;
            return (
              <li key={source.chunk_id} ref={isFocused ? focused : undefined}>
                <SourceCard
                  source={source}
                  quotes={quotes}
                  focused={isFocused}
                  // Passages the answer did not quote start folded, to keep the quoted ones in view.
                  collapsible={quotes.length === 0}
                  badge={quotes.length > 0 ? <Badge tone="ok">Quoted</Badge> : undefined}
                />
              </li>
            );
          })}
        </ol>
      </aside>
    </>
  );
}
