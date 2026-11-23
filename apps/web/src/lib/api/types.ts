/** Shapes of the Atlas API (services/api). Keep in step with the routers there. */

export type Role = "viewer" | "editor" | "admin" | "owner";

export type Permission =
  | "documents:read"
  | "documents:write"
  | "agents:run"
  | "agents:approve"
  | "analytics:query"
  | "users:manage"
  | "audit:read"
  | "tenant:manage";

export interface Me {
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  permissions: Permission[];
  tenant: { id: string; slug: string; name: string };
}

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface AtlasDocument {
  id: string;
  title: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentPage {
  items: AtlasDocument[];
  next_cursor: string | null;
}

/** One retrieved passage. */
export interface Source {
  index: number;
  chunk_id: string;
  document_id: string;
  document_title: string;
  heading: string | null;
  page: number | null;
  score: number;
  content: string;
}

/** A quote from a source that supports one segment of an answer. */
export interface Citation {
  source: number;
  document_id: string;
  document_title: string;
  page: number | null;
  cited_text: string;
  start_char: number;
  end_char: number;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
}

/** The events of the `/v1/ask` stream. */
export type AskEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "delta"; segment: number; text: string }
  | { type: "citation"; segment: number; citation: Citation }
  | { type: "refusal"; text: string }
  | { type: "done"; grounded: boolean; model: string | null; usage: Usage | null }
  | { type: "error"; detail: string };

export interface AuditEvent {
  id: number;
  actor_user_id: string | null;
  actor_subject: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  request_id: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
}
