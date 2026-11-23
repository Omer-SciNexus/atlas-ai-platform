import { apiFetch, apiJson, ApiError, jsonBody } from "./client";
import { parseSse, type SseMessage } from "./sse";
import type {
  AskEvent,
  AtlasDocument,
  AuditEvent,
  Citation,
  DocumentPage,
  Me,
  Source,
} from "./types";

export function getMe(): Promise<Me> {
  return apiJson<Me>("/v1/me");
}

export function listDocuments(cursor: string | null): Promise<DocumentPage> {
  const query = new URLSearchParams({ limit: "20" });
  if (cursor) query.set("cursor", cursor);
  return apiJson<DocumentPage>(`/v1/documents?${query}`);
}

export interface UploadResult {
  document: AtlasDocument;
  /** False when the same file was already uploaded; the existing document is returned. */
  created: boolean;
}

export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await apiFetch("/v1/documents", { method: "POST", body: form });
  return { document: (await response.json()) as AtlasDocument, created: response.status === 201 };
}

export async function deleteDocument(id: string): Promise<void> {
  await apiFetch(`/v1/documents/${id}`, { method: "DELETE" });
}

export async function searchPassages(query: string, signal?: AbortSignal): Promise<Source[]> {
  const body = await apiJson<{ results: Source[] }>("/v1/search", {
    ...jsonBody({ query }),
    signal,
  });
  return body.results;
}

export const AUDIT_PAGE_SIZE = 50;

export function listAuditEvents(before: number | null): Promise<AuditEvent[]> {
  const query = new URLSearchParams({ limit: String(AUDIT_PAGE_SIZE) });
  if (before !== null) query.set("before", String(before));
  return apiJson<AuditEvent[]>(`/v1/audit-events?${query}`);
}

/** Turn one server-sent event into a typed event. Unknown event names are ignored. */
export function toAskEvent(message: SseMessage): AskEvent | null {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(message.data) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (message.event) {
    case "sources":
      return { type: "sources", sources: data.sources as Source[] };
    case "delta":
      return { type: "delta", segment: data.segment as number, text: data.text as string };
    case "citation": {
      const { segment, ...citation } = data;
      return { type: "citation", segment: segment as number, citation: citation as unknown as Citation };
    }
    case "refusal":
      return { type: "refusal", text: data.text as string };
    case "done":
      return {
        type: "done",
        grounded: data.grounded === true,
        model: (data.model as string | null) ?? null,
        usage: (data.usage as { input_tokens: number; output_tokens: number } | null) ?? null,
      };
    case "error":
      return { type: "error", detail: String(data.detail ?? "The answer failed.") };
    default:
      return null;
  }
}

/** Ask a question and yield the answer as it is written. Abort `signal` to stop. */
export async function* askStream(question: string, signal: AbortSignal): AsyncGenerator<AskEvent> {
  const response = await apiFetch("/v1/ask", {
    ...jsonBody({ question }),
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    signal,
  });
  if (!response.body) throw new ApiError(0, "The answer could not be read.");
  for await (const message of parseSse(response.body)) {
    const event = toAskEvent(message);
    if (event) yield event;
  }
}
