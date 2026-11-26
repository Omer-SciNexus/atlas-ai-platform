"use client";

import { ArrowUp, Square } from "lucide-react";
import { type KeyboardEvent, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/** The API accepts questions up to this length. */
export const MAX_QUESTION_CHARS = 4000;

interface ComposerProps {
  busy: boolean;
  onAsk: (question: string) => void;
  onStop: () => void;
}

export function Composer({ busy, onAsk, onStop }: ComposerProps) {
  const [text, setText] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);
  const question = text.trim();
  const tooLong = question.length > MAX_QUESTION_CHARS;
  const canSend = !busy && question.length > 0 && !tooLong;

  // Grow with the text, up to the CSS max height.
  useLayoutEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  }, [text]);

  function send() {
    if (!canSend) return;
    onAsk(question);
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter adds a line. Enter while composing (IME) belongs to the IME.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  }

  return (
    <div className="shrink-0 px-4 pb-4 md:px-8">
      <form
        className="mx-auto w-full max-w-3xl"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <div
          className={cn(
            "flex items-end gap-2 rounded-2xl border bg-surface p-2 pl-4 shadow-lg shadow-black/5 transition-colors",
            "focus-within:border-accent",
            tooLong ? "border-danger" : "border-line",
          )}
        >
          <label htmlFor="question" className="sr-only">
            Question
          </label>
          <textarea
            id="question"
            ref={textarea}
            rows={1}
            value={text}
            autoFocus
            onChange={(event) => setText(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question about your documents"
            className="max-h-48 min-h-9 flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-6 outline-none placeholder:text-muted"
          />
          {busy ? (
            <Button variant="secondary" size="icon" aria-label="Stop the answer" onClick={onStop}>
              <Square aria-hidden className="size-3.5 fill-current" />
            </Button>
          ) : (
            <Button type="submit" size="icon" aria-label="Ask" disabled={!canSend}>
              <ArrowUp aria-hidden className="size-4" />
            </Button>
          )}
        </div>
        <p className={cn("mt-2 text-center text-xs", tooLong ? "text-danger" : "text-muted")}>
          {tooLong
            ? `The question is ${question.length - MAX_QUESTION_CHARS} characters too long.`
            : "Answers use only your organization's documents. Each question is answered on its own."}
        </p>
      </form>
    </div>
  );
}
