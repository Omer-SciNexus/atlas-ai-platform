"use client";

import { type ReactNode, useState } from "react";

import { highlightQuotes, missingQuotes } from "@/lib/highlight";
import type { Source } from "@/lib/api/types";
import { cn } from "@/lib/cn";

interface SourceCardProps {
  source: Source;
  /** Text to highlight inside the passage. */
  quotes?: readonly string[];
  focused?: boolean;
  /** Show the first lines only, with a control to show the rest. */
  collapsible?: boolean;
  badge?: ReactNode;
}

/** One retrieved passage: where it comes from, how well it matched, and its text. */
export function SourceCard({
  source,
  quotes = [],
  focused = false,
  collapsible = false,
  badge,
}: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const folded = collapsible && !expanded && !focused;
  const parts = highlightQuotes(source.content, quotes);
  const notFound = missingQuotes(source.content, quotes);
  const place = [source.heading, source.page !== null ? `Page ${source.page}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className={cn(
        "rounded-xl border bg-surface p-3.5 transition-shadow",
        focused ? "border-accent ring-2 ring-accent/20" : "border-line",
      )}
    >
      <div className="flex items-start gap-2.5">
        <span className="flex h-5 min-w-5 items-center justify-center rounded-md bg-accent-soft px-1 font-mono text-[11px] font-semibold text-accent">
          {source.index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={source.document_title}>
            {source.document_title}
          </p>
          {place && <p className="truncate text-xs text-muted">{place}</p>}
        </div>
        {badge}
        <span
          className="font-mono text-[11px] text-muted"
          title="Similarity between the question and this passage (1 is identical)"
        >
          {source.score.toFixed(2)}
        </span>
      </div>

      {notFound.map((quote) => (
        <blockquote key={quote} className="mt-3 border-l-2 border-accent pl-3 text-[13px] leading-6">
          <mark>{quote}</mark>
        </blockquote>
      ))}

      <p
        className={cn(
          "mt-3 text-[13px] leading-6 break-words whitespace-pre-wrap text-ink/85",
          folded && "line-clamp-3",
        )}
      >
        {parts.map((part, index) =>
          part.highlighted ? <mark key={index}>{part.text}</mark> : <span key={index}>{part.text}</span>,
        )}
      </p>
      {collapsible && !focused && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="mt-1.5 text-xs font-medium text-accent hover:underline"
        >
          {expanded ? "Show less" : "Show all"}
        </button>
      )}
    </div>
  );
}
