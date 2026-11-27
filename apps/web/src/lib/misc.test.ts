import { describe, expect, it } from "vitest";

import { fileExtension, MAX_UPLOAD_BYTES, rejectionReason } from "@/features/documents/files";
import { errorFromResponse } from "@/lib/api/client";
import { toAskEvent } from "@/lib/api/endpoints";
import { safeReturnTo } from "@/lib/auth/return-to";
import { formatBytes, formatRelativeTime } from "@/lib/format";

describe("safeReturnTo", () => {
  it("accepts a path inside the app", () => {
    expect(safeReturnTo("/documents")).toBe("/documents");
    expect(safeReturnTo("/search?q=income")).toBe("/search?q=income");
  });

  it.each([
    ["another site", "https://evil.example/ask"],
    ["a protocol-relative address", "//evil.example"],
    ["a backslash trick", "/\\evil.example"],
    ["the sign-in callback", "/auth/callback?code=1"],
    ["a missing value", undefined],
    ["a non-string", 42],
  ])("falls back to /ask for %s", (_name, value) => {
    expect(safeReturnTo(value)).toBe("/ask");
  });
});

describe("errorFromResponse", () => {
  it("reads the detail and request id of a problem+json body", async () => {
    const response = new Response(
      JSON.stringify({ status: 415, detail: "Unsupported file type", request_id: "req-1" }),
      { status: 415, headers: { "Content-Type": "application/problem+json" } },
    );
    const error = await errorFromResponse(response);
    expect(error).toMatchObject({ status: 415, message: "Unsupported file type", requestId: "req-1" });
  });

  it("falls back to a message for the status when the body is not JSON", async () => {
    const response = new Response("<html>Bad gateway</html>", {
      status: 502,
      headers: { "X-Request-ID": "req-2" },
    });
    const error = await errorFromResponse(response);
    expect(error.message).toBe("The server had a problem. Try again.");
    expect(error.requestId).toBe("req-2");
  });
});

describe("toAskEvent", () => {
  it("separates the segment from the citation", () => {
    const event = toAskEvent({
      event: "citation",
      data: JSON.stringify({ segment: 2, source: 0, cited_text: "Revenue rose." }),
    });
    expect(event).toEqual({
      type: "citation",
      segment: 2,
      citation: { source: 0, cited_text: "Revenue rose." },
    });
  });

  it("reads a done event without a model call", () => {
    const event = toAskEvent({
      event: "done",
      data: JSON.stringify({ grounded: false, model: null, usage: null }),
    });
    expect(event).toEqual({ type: "done", grounded: false, model: null, usage: null });
  });

  it("ignores unknown events and broken data", () => {
    expect(toAskEvent({ event: "ping", data: "{}" })).toBeNull();
    expect(toAskEvent({ event: "delta", data: "{not json" })).toBeNull();
  });
});

describe("rejectionReason", () => {
  it("accepts the supported types in any letter case", () => {
    expect(rejectionReason({ name: "Report.PDF", size: 10 })).toBeNull();
    expect(rejectionReason({ name: "notes.md", size: 10 })).toBeNull();
  });

  it("rejects other types, empty files and files over the limit", () => {
    expect(rejectionReason({ name: "sheet.xlsx", size: 10 })).toMatch(/not supported/);
    expect(rejectionReason({ name: "README", size: 10 })).toMatch(/not supported/);
    expect(rejectionReason({ name: "empty.txt", size: 0 })).toMatch(/empty/);
    expect(rejectionReason({ name: "big.pdf", size: MAX_UPLOAD_BYTES + 1 })).toMatch(/25 MB/);
  });

  it("does not treat a dotfile name as an extension", () => {
    expect(fileExtension(".pdf")).toBe("");
  });
});

describe("format", () => {
  it("formats sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25.0 MB");
  });

  it("formats times relative to now", () => {
    const now = new Date("2026-11-28T12:00:00Z");
    expect(formatRelativeTime("2026-11-28T11:59:58Z", now)).toBe("just now");
    expect(formatRelativeTime("2026-11-28T11:57:00Z", now)).toBe("3 minutes ago");
    expect(formatRelativeTime("2026-11-27T12:00:00Z", now)).toBe("yesterday");
  });
});
