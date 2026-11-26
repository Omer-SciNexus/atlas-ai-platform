"use client";

import { Plus, Upload } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, buttonClass } from "@/components/ui/button";
import { useCan, useDocuments } from "@/lib/api/hooks";

import { useAsk } from "./ask-provider";
import { Composer } from "./composer";
import { SourcesPanel } from "./sources-panel";
import { TurnView } from "./turn-view";

/** Which answer's sources are open, and which source is in focus. */
interface Selection {
  turnId: string;
  source: number | null;
}

function EmptyThread() {
  const documents = useDocuments();
  const canUpload = useCan("documents:write");
  const hasReady = documents.data?.pages.some((p) => p.items.some((d) => d.status === "ready"));
  const nothingToAsk = documents.isSuccess && !hasReady;

  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 py-10 text-center">
      <Image
        src="/images/empty-states/no-conversations.png"
        alt=""
        width={168}
        height={168}
        priority
      />
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Ask your documents</h1>
      <p className="mt-2 max-w-md text-sm text-balance text-muted">
        {nothingToAsk
          ? "There are no documents ready to answer from yet."
          : "Atlas answers from your organization's documents and shows the quote behind each statement."}
      </p>
      {nothingToAsk && (
        <Link href="/documents" className={`${buttonClass("primary")} mt-5`}>
          <Upload aria-hidden className="size-4" />
          {canUpload ? "Upload a document" : "See documents"}
        </Link>
      )}
    </div>
  );
}

export function AskView() {
  const { turns, busy, ask, stop, clear } = useAsk();
  const [selection, setSelection] = useState<Selection | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  // Follow the answer as it grows, unless the user has scrolled up to read.
  const following = useRef(true);

  useEffect(() => {
    const element = scroller.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [turns]);

  const closeSources = useCallback(() => setSelection(null), []);
  const selectedTurn = selection ? turns.find((t) => t.id === selection.turnId) : undefined;

  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        {turns.length > 0 && (
          <div className="flex h-12 shrink-0 items-center justify-end px-4 md:px-8">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                clear();
                setSelection(null);
              }}
            >
              <Plus aria-hidden className="size-4" />
              New thread
            </Button>
          </div>
        )}
        <div
          ref={scroller}
          className="min-h-0 flex-1 overflow-y-auto"
          onScroll={(event) => {
            const element = event.currentTarget;
            following.current =
              element.scrollHeight - element.scrollTop - element.clientHeight < 80;
          }}
        >
          {turns.length === 0 ? (
            <EmptyThread />
          ) : (
            <div className="mx-auto w-full max-w-3xl space-y-10 px-4 pt-2 pb-10 md:px-8">
              {turns.map((turn) => (
                <TurnView
                  key={turn.id}
                  turn={turn}
                  focusedSource={selection?.turnId === turn.id ? selection.source : null}
                  onOpenSource={(source) => setSelection({ turnId: turn.id, source })}
                />
              ))}
            </div>
          )}
        </div>
        <Composer
          busy={busy}
          onStop={stop}
          onAsk={(question) => {
            following.current = true;
            ask(question);
          }}
        />
      </section>

      {selectedTurn && selection && (
        <SourcesPanel turn={selectedTurn} focusedSource={selection.source} onClose={closeSources} />
      )}
    </div>
  );
}
