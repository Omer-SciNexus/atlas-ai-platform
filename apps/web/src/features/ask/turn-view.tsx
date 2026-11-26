"use client";

import { Check, Copy, Library, ShieldAlert, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";

import { citedSources, isActive, type Turn } from "./thread";

interface TurnViewProps {
  turn: Turn;
  /** The source shown in the side panel for this turn, if any. */
  focusedSource: number | null;
  onOpenSource: (source: number | null) => void;
}

function CitationChip({
  turn,
  source,
  focused,
  onOpen,
}: {
  turn: Turn;
  source: number;
  focused: boolean;
  onOpen: () => void;
}) {
  const title = turn.sources[source]?.document_title ?? "Source";
  return (
    <button
      type="button"
      onClick={onOpen}
      title={title}
      aria-label={`Source ${source + 1}: ${title}`}
      className={cn(
        "mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md px-1 align-baseline font-mono text-[11px] font-semibold transition-colors",
        focused
          ? "bg-accent text-accent-ink"
          : "bg-accent-soft text-accent hover:bg-accent hover:text-accent-ink",
      )}
    >
      {source + 1}
    </button>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function GroundingBadge({ turn }: { turn: Turn }) {
  if (turn.refused) return null;
  if (turn.sources.length === 0) return <Badge>No matching passages</Badge>;
  const cited = new Set(turn.segments.flatMap(citedSources)).size;
  if (turn.grounded) {
    return (
      <Badge tone="ok">
        <ShieldCheck aria-hidden className="size-3.5" />
        Grounded in {cited} {cited === 1 ? "source" : "sources"}
      </Badge>
    );
  }
  return (
    <Badge tone="warn">
      <ShieldAlert aria-hidden className="size-3.5" />
      No supporting quote
    </Badge>
  );
}

export function TurnView({ turn, focusedSource, onOpenSource }: TurnViewProps) {
  const active = isActive(turn);
  const text = turn.segments.map((s) => s.text).join("");
  const hasText = text.trim().length > 0;

  return (
    <article className="animate-rise space-y-4">
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] leading-6 whitespace-pre-wrap text-accent-ink">
          {turn.question}
        </p>
      </div>

      <div className="flex gap-3">
        <Image
          src="/images/avatar/ai-assistant.png"
          alt=""
          width={32}
          height={32}
          className="mt-0.5 size-8 shrink-0 rounded-full"
        />
        <div className="min-w-0 flex-1 space-y-3">
          {turn.phase === "retrieving" && (
            <p className="flex items-center gap-2 py-1.5 text-sm text-muted" role="status">
              <Spinner /> Searching your documents…
            </p>
          )}
          {turn.phase === "answering" && !hasText && (
            <p className="flex items-center gap-2 py-1.5 text-sm text-muted" role="status">
              <Spinner /> Reading {turn.sources.length}{" "}
              {turn.sources.length === 1 ? "passage" : "passages"}…
            </p>
          )}

          {hasText && (
            <div
              className="text-[15px] leading-7 whitespace-pre-wrap"
              // Announce the finished answer once, not every streamed word.
              aria-live="polite"
              aria-busy={active}
            >
              {turn.segments.map((segment, index) => (
                <span key={index}>
                  {segment.text}
                  {citedSources(segment).map((source) => (
                    <CitationChip
                      key={source}
                      turn={turn}
                      source={source}
                      focused={focusedSource === source}
                      onOpen={() => onOpenSource(source)}
                    />
                  ))}
                </span>
              ))}
              {active && (
                <span aria-hidden className="ml-0.5 inline-block h-4 w-0.5 animate-blink bg-accent align-middle" />
              )}
            </div>
          )}

          {turn.phase === "stopped" && <p className="text-sm text-muted">Stopped.</p>}

          {turn.phase === "failed" && (
            <Notice tone="danger">
              <p>{turn.error}</p>
              {turn.errorStatus === 503 && (
                <p className="mt-1">
                  You can still{" "}
                  <Link
                    href={`/search?q=${encodeURIComponent(turn.question)}`}
                    className="font-medium underline underline-offset-2"
                  >
                    search the passages
                  </Link>{" "}
                  for this question.
                </p>
              )}
            </Notice>
          )}

          {turn.phase === "done" && !turn.grounded && !turn.refused && turn.sources.length > 0 && (
            <Notice tone="warn">
              Nothing in this answer is backed by a quote from your documents. Check it before
              you rely on it.
            </Notice>
          )}

          {turn.phase === "done" && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
              <GroundingBadge turn={turn} />
              {turn.sources.length > 0 && (
                <Button variant="ghost" size="sm" onClick={() => onOpenSource(null)}>
                  <Library aria-hidden className="size-3.5" />
                  {turn.sources.length} {turn.sources.length === 1 ? "passage" : "passages"} read
                </Button>
              )}
              {hasText && <CopyButton text={text.trim()} />}
              {turn.model && turn.usage && (
                <span className="ml-auto font-mono text-[11px] text-muted">
                  {turn.model} · {turn.usage.input_tokens.toLocaleString("en")} in /{" "}
                  {turn.usage.output_tokens.toLocaleString("en")} out
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
