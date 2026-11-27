import type { AuditEvent } from "@/lib/api/types";

const ACTION_LABELS: Record<string, string> = {
  "user.provisioned": "User signed in for the first time",
  "document.uploaded": "Document uploaded",
  "document.deleted": "Document deleted",
  "document.ingested": "Document prepared for questions",
  "document.ingestion_failed": "Document could not be prepared",
  "rag.asked": "Question asked",
};

/** A readable name for an audit action. An action this page does not know is shown as it is. */
export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

export function isFailure(action: string): boolean {
  return action.endsWith("_failed") || action.endsWith(".denied");
}

const SYSTEM_PREFIX = "system:";

/** Background services record themselves as "system:<name>"; everyone else is a person. */
export function isSystemActor(event: AuditEvent): boolean {
  if (event.actor_user_id) return false;
  return event.actor_subject === null || event.actor_subject.startsWith(SYSTEM_PREFIX);
}

/** A short name for who did it. The full subject id is in the event's details. */
export function actorLabel(event: AuditEvent): string {
  if (!isSystemActor(event)) return "User";
  return event.actor_subject?.slice(SYSTEM_PREFIX.length) || "System";
}
