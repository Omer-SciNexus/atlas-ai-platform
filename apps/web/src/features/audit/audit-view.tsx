"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronRight, Lock } from "lucide-react";
import { useState } from "react";

import { Page } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { AUDIT_PAGE_SIZE, listAuditEvents } from "@/lib/api/endpoints";
import { queryKeys, useCan } from "@/lib/api/hooks";
import type { AuditEvent } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

import { actionLabel, actorLabel, isFailure, isSystemActor } from "./labels";

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium tracking-wide text-muted uppercase">{label}</dt>
      <dd className="mt-0.5 font-mono text-xs break-all">{value}</dd>
    </div>
  );
}

function EventRow({ event }: { event: AuditEvent }) {
  const [open, setOpen] = useState(false);
  const hasDetails = Object.keys(event.details).length > 0;
  const resource = event.resource_type
    ? `${event.resource_type}${event.resource_id ? ` ${event.resource_id}` : ""}`
    : null;

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-raised/60"
      >
        <ChevronRight
          aria-hidden
          className={cn("size-4 shrink-0 text-muted transition-transform", open && "rotate-90")}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{actionLabel(event.action)}</p>
          <p className="truncate font-mono text-xs text-muted">{event.action}</p>
        </div>
        <Badge tone={isFailure(event.action) ? "danger" : isSystemActor(event) ? "neutral" : "accent"}>
          {actorLabel(event)}
        </Badge>
        <time
          dateTime={event.occurred_at}
          className="hidden w-48 shrink-0 text-right text-xs text-muted sm:block"
        >
          {formatDateTime(event.occurred_at)}
        </time>
      </button>
      {open && (
        <div className="space-y-3 border-t border-line bg-raised/40 px-4 py-3 pl-11">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Field label="When" value={formatDateTime(event.occurred_at)} />
            <Field label="Resource" value={resource} />
            <Field label="Subject" value={event.actor_subject} />
            <Field label="Request" value={event.request_id} />
          </dl>
          {hasDetails && (
            <pre className="overflow-x-auto rounded-lg border border-line bg-surface p-3 font-mono text-xs leading-5">
              {JSON.stringify(event.details, null, 2)}
            </pre>
          )}
        </div>
      )}
    </li>
  );
}

function AuditEvents() {
  const events = useInfiniteQuery({
    queryKey: queryKeys.audit,
    queryFn: ({ pageParam }) => listAuditEvents(pageParam),
    initialPageParam: null as number | null,
    // A full page means there may be older events; ask for those before its last id.
    getNextPageParam: (last) =>
      last.length === AUDIT_PAGE_SIZE ? (last.at(-1)?.id ?? undefined) : undefined,
  });
  const items = events.data?.pages.flat() ?? [];

  if (events.isPending) {
    return (
      <p className="flex items-center gap-2 py-10 text-sm text-muted" role="status">
        <Spinner /> Loading events…
      </p>
    );
  }
  if (events.isError) return <ErrorNotice error={events.error} />;
  if (items.length === 0) return <Notice>Nothing has been recorded yet.</Notice>;

  return (
    <>
      <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {items.map((event) => (
          <EventRow key={event.id} event={event} />
        ))}
      </ul>
      {events.hasNextPage && (
        <div className="mt-4 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => void events.fetchNextPage()}
            disabled={events.isFetchingNextPage}
          >
            {events.isFetchingNextPage && <Spinner />}
            Show older events
          </Button>
        </div>
      )}
    </>
  );
}

export function AuditView() {
  const canRead = useCan("audit:read");
  return (
    <Page
      title="Audit log"
      description="What happened in your organization, newest first. Entries cannot be changed or removed."
    >
      {canRead ? (
        <AuditEvents />
      ) : (
        <div className="flex flex-col items-center rounded-2xl border border-line bg-surface px-6 py-12 text-center">
          <span className="flex size-11 items-center justify-center rounded-full bg-raised text-muted">
            <Lock aria-hidden className="size-5" />
          </span>
          <p className="mt-3 text-base font-medium">Admins only</p>
          <p className="mt-1 max-w-sm text-sm text-muted">
            Your role cannot read the audit log. Ask an admin or the owner of your organization.
          </p>
        </div>
      )}
    </Page>
  );
}
