"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2 } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { Page } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ErrorNotice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { deleteDocument } from "@/lib/api/endpoints";
import { queryKeys, useCan, useDocuments } from "@/lib/api/hooks";
import type { AtlasDocument } from "@/lib/api/types";
import { formatBytes, formatDateTime, formatRelativeTime } from "@/lib/format";

import { UploadZone } from "./upload-zone";

function StatusBadge({ document }: { document: AtlasDocument }) {
  switch (document.status) {
    case "pending":
      return <Badge>Waiting</Badge>;
    case "processing":
      return (
        <Badge tone="accent">
          <Spinner className="size-3" /> Preparing
        </Badge>
      );
    case "ready":
      return <Badge tone="ok">Ready</Badge>;
    case "failed":
      return <Badge tone="danger">Failed</Badge>;
  }
}

function DocumentRow({
  document,
  onDelete,
}: {
  document: AtlasDocument;
  onDelete?: () => void;
}) {
  const details = [
    document.title !== document.filename ? document.filename : null,
    formatBytes(document.size_bytes),
    document.status === "ready"
      ? `${document.chunk_count} ${document.chunk_count === 1 ? "passage" : "passages"}`
      : null,
  ].filter(Boolean);

  return (
    <li className="flex items-center gap-3.5 px-4 py-3.5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
        <FileText aria-hidden className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" title={document.title}>
          {document.title}
        </p>
        <p className="truncate text-xs text-muted">
          {details.join(" · ")}
          {" · "}
          <time dateTime={document.created_at} title={formatDateTime(document.created_at)}>
            {formatRelativeTime(document.created_at)}
          </time>
        </p>
        {document.status === "failed" && document.error && (
          <p className="mt-1 text-xs text-danger">{document.error}</p>
        )}
      </div>
      <StatusBadge document={document} />
      {onDelete && (
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Delete ${document.title}`}
          onClick={onDelete}
          className="hover:bg-danger-soft hover:text-danger"
        >
          <Trash2 aria-hidden className="size-4" />
        </Button>
      )}
    </li>
  );
}

export function DocumentsView() {
  const canWrite = useCan("documents:write");
  const documents = useDocuments();
  const queryClient = useQueryClient();
  const [toDelete, setToDelete] = useState<AtlasDocument | null>(null);

  const remove = useMutation({
    mutationFn: (document: AtlasDocument) => deleteDocument(document.id),
    onSuccess: () => setToDelete(null),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.documents }),
  });

  const items = documents.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Page
      title="Documents"
      description="The files Atlas answers from. Only people in your organization can see them."
    >
      {canWrite && (
        <div className="mb-6">
          <UploadZone />
        </div>
      )}

      {documents.isPending && (
        <p className="flex items-center gap-2 py-10 text-sm text-muted" role="status">
          <Spinner /> Loading documents…
        </p>
      )}
      {documents.isError && <ErrorNotice error={documents.error} />}

      {documents.isSuccess && items.length === 0 && (
        <div className="flex flex-col items-center rounded-2xl border border-line bg-surface px-6 py-10 text-center">
          <Image src="/images/empty-states/no-documents.png" alt="" width={140} height={140} />
          <p className="mt-2 text-base font-medium">No documents yet</p>
          <p className="mt-1 max-w-sm text-sm text-muted">
            {canWrite
              ? "Upload a file above. It is ready for questions a few seconds later."
              : "Your role can read documents but not upload them. Ask an editor or admin to add some."}
          </p>
        </div>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
          {items.map((document) => (
            <DocumentRow
              key={document.id}
              document={document}
              onDelete={
                canWrite
                  ? () => {
                      remove.reset();
                      setToDelete(document);
                    }
                  : undefined
              }
            />
          ))}
        </ul>
      )}

      {documents.hasNextPage && (
        <div className="mt-4 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => void documents.fetchNextPage()}
            disabled={documents.isFetchingNextPage}
          >
            {documents.isFetchingNextPage && <Spinner />}
            Show more
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this document?"
        confirmLabel="Delete"
        busy={remove.isPending}
        onCancel={() => setToDelete(null)}
        onConfirm={() => toDelete && remove.mutate(toDelete)}
      >
        <p>
          <span className="font-medium text-ink">{toDelete?.title}</span> and its passages will be
          removed. Atlas will no longer answer from it. This cannot be undone.
        </p>
        {remove.isError && <ErrorNotice error={remove.error} className="mt-3" />}
      </ConfirmDialog>
    </Page>
  );
}
