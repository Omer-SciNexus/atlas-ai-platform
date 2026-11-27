"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, UploadCloud, X } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/api/client";
import { uploadDocument } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/hooks";
import { cn } from "@/lib/cn";

import { ACCEPTED_EXTENSIONS, rejectionReason } from "./files";

interface Upload {
  id: number;
  name: string;
  state: "uploading" | "uploaded" | "duplicate" | "failed";
  message?: string;
}

const STATE_TEXT: Record<Exclude<Upload["state"], "failed">, string> = {
  uploading: "Uploading…",
  uploaded: "Uploaded. It is being prepared for questions.",
  duplicate: "This file was already uploaded.",
};

export function UploadZone() {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const nextId = useRef(0);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragging, setDragging] = useState(false);

  function update(id: number, change: Partial<Upload>) {
    setUploads((list) => list.map((u) => (u.id === id ? { ...u, ...change } : u)));
  }

  async function uploadOne(file: File) {
    nextId.current += 1;
    const id = nextId.current;
    const rejected = rejectionReason(file);
    setUploads((list) => [
      { id, name: file.name, state: rejected ? "failed" : "uploading", message: rejected ?? undefined },
      ...list,
    ]);
    if (rejected) return;
    try {
      const result = await uploadDocument(file);
      update(id, { state: result.created ? "uploaded" : "duplicate" });
      await queryClient.invalidateQueries({ queryKey: queryKeys.documents });
    } catch (error) {
      update(id, { state: "failed", message: errorMessage(error) });
    }
  }

  function addFiles(files: FileList | null) {
    if (!files) return;
    for (const file of files) void uploadOne(file);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          dragging ? "border-accent bg-accent-soft" : "border-line bg-surface",
        )}
      >
        <span className="flex size-11 items-center justify-center rounded-full bg-accent-soft text-accent">
          <UploadCloud aria-hidden className="size-5" />
        </span>
        <div>
          <p className="text-sm font-medium">Drop files here to upload</p>
          <p className="mt-1 text-xs text-muted">Text, Markdown, HTML or PDF, up to 25 MB each</p>
        </div>
        <Button variant="secondary" onClick={() => input.current?.click()}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = ""; // so the same file can be chosen again
          }}
        />
      </div>

      {uploads.length > 0 && (
        <ul className="mt-3 space-y-2" aria-live="polite">
          {uploads.map((upload) => (
            <li
              key={upload.id}
              className="flex items-start gap-2.5 rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm"
            >
              {upload.state === "uploading" && <Spinner className="mt-0.5 text-accent" />}
              {(upload.state === "uploaded" || upload.state === "duplicate") && (
                <CircleCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-ok" />
              )}
              {upload.state === "failed" && (
                <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-danger" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{upload.name}</p>
                <p className={cn("text-xs", upload.state === "failed" ? "text-danger" : "text-muted")}>
                  {upload.state === "failed" ? upload.message : STATE_TEXT[upload.state]}
                </p>
              </div>
              {upload.state !== "uploading" && (
                <button
                  type="button"
                  aria-label={`Dismiss ${upload.name}`}
                  onClick={() => setUploads((list) => list.filter((u) => u.id !== upload.id))}
                  className="rounded-md p-1 text-muted hover:bg-raised hover:text-ink"
                >
                  <X aria-hidden className="size-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
