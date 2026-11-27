import { describe, expect, it } from "vitest";

import type { AuditEvent } from "@/lib/api/types";

import { actionLabel, actorLabel, isFailure } from "./labels";

function event(change: Partial<AuditEvent>): AuditEvent {
  return {
    id: 1,
    actor_user_id: null,
    actor_subject: null,
    action: "document.uploaded",
    resource_type: null,
    resource_id: null,
    request_id: null,
    details: {},
    occurred_at: "2026-11-28T12:00:00Z",
    ...change,
  };
}

describe("audit labels", () => {
  it("names known actions and shows unknown ones as they are", () => {
    expect(actionLabel("rag.asked")).toBe("Question asked");
    expect(actionLabel("agent.approved")).toBe("agent.approved");
  });

  it("marks failures", () => {
    expect(isFailure("document.ingestion_failed")).toBe(true);
    expect(isFailure("document.ingested")).toBe(false);
  });

  it("calls a person User, with or without a user row", () => {
    expect(actorLabel(event({ actor_user_id: "u1", actor_subject: "sub-1" }))).toBe("User");
    expect(actorLabel(event({ actor_subject: "770b6f23-88a0" }))).toBe("User");
  });

  it("names a background service without the system prefix", () => {
    expect(actorLabel(event({ actor_subject: "system:ingestion-worker" }))).toBe("ingestion-worker");
    expect(actorLabel(event({}))).toBe("System");
  });
});
