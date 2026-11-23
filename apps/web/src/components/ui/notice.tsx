import { CircleAlert, Info } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError, errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/cn";

export function Notice({
  tone = "info",
  className,
  children,
}: {
  tone?: "info" | "danger" | "warn";
  className?: string;
  children: ReactNode;
}) {
  const Icon = tone === "info" ? Info : CircleAlert;
  return (
    <div
      role={tone === "info" ? "status" : "alert"}
      className={cn(
        "flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm",
        tone === "info" && "bg-raised text-ink",
        tone === "warn" && "bg-warn-soft text-warn",
        tone === "danger" && "bg-danger-soft text-danger",
        className,
      )}
    >
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/** An API failure, with the request id to quote when asking for help. */
export function ErrorNotice({ error, className }: { error: unknown; className?: string }) {
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <Notice tone="danger" className={className}>
      <p>{errorMessage(error)}</p>
      {requestId && <p className="mt-1 font-mono text-xs opacity-80">Request {requestId}</p>}
    </Notice>
  );
}
