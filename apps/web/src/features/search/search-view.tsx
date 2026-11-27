"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Page } from "@/components/shell";
import { SourceCard } from "@/components/source-card";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { searchPassages } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/hooks";

/** The API accepts queries up to this length. */
const MAX_QUERY_CHARS = 2000;

export function SearchView() {
  const router = useRouter();
  const pathname = usePathname();
  // The query lives in the address, so a search can be linked to and survives a reload.
  const query = (useSearchParams().get("q") ?? "").trim().slice(0, MAX_QUERY_CHARS);
  const [text, setText] = useState(query);

  const results = useQuery({
    queryKey: queryKeys.search(query),
    queryFn: ({ signal }) => searchPassages(query, signal),
    enabled: query.length > 0,
  });

  return (
    <Page
      title="Search"
      description="The passages Atlas would read for a question. No answer is written."
    >
      <form
        role="search"
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const next = text.trim();
          router.replace(next ? `${pathname}?q=${encodeURIComponent(next)}` : pathname);
        }}
      >
        <div className="relative flex-1">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted"
          />
          <input
            type="search"
            aria-label="Search your documents"
            value={text}
            maxLength={MAX_QUERY_CHARS}
            autoFocus
            onChange={(event) => setText(event.target.value)}
            placeholder="Words or a question"
            className="h-11 w-full rounded-xl border border-line bg-surface pr-3 pl-10 text-[15px] outline-none placeholder:text-muted focus:border-accent"
          />
        </div>
        <Button type="submit" className="h-11 px-5" disabled={!text.trim()}>
          Search
        </Button>
      </form>

      <div className="mt-6 space-y-3">
        {query && results.isPending && (
          <p className="flex items-center gap-2 text-sm text-muted" role="status">
            <Spinner /> Searching…
          </p>
        )}
        {results.isError && <ErrorNotice error={results.error} />}
        {results.isSuccess && results.data.length === 0 && (
          <Notice>No passage matches this. Try other words, or upload a document that covers it.</Notice>
        )}
        {results.isSuccess && results.data.length > 0 && (
          <>
            <p className="text-xs text-muted">
              {results.data.length} {results.data.length === 1 ? "passage" : "passages"}, best match
              first
            </p>
            <ol className="space-y-3">
              {results.data.map((source) => (
                <li key={source.chunk_id}>
                  <SourceCard source={source} collapsible />
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </Page>
  );
}
