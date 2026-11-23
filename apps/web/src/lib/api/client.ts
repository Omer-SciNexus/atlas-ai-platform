import { accessToken, userManager } from "@/lib/auth/manager";
import { config } from "@/lib/config";

/** A failed API call. `message` is safe to show; `requestId` is for support. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  401: "Your session has ended. Sign in again.",
  403: "You do not have permission to do this.",
  404: "Not found.",
  413: "The file is too large.",
  429: "Too many requests. Try again in a moment.",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Read an RFC 9457 problem+json body; fall back to a message for the status code. */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  let detail: string | null = null;
  let requestId = response.headers.get("X-Request-ID");
  try {
    const body: unknown = await response.json();
    if (isRecord(body)) {
      if (typeof body.detail === "string" && body.detail) detail = body.detail;
      if (typeof body.request_id === "string") requestId = body.request_id;
    }
  } catch {
    // Not JSON (a proxy error page, for example).
  }
  const fallback =
    FALLBACK_MESSAGES[response.status] ??
    (response.status >= 500 ? "The server had a problem. Try again." : "The request failed.");
  return new ApiError(response.status, detail ?? fallback, requestId);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Try again.";
}

/** Call the API as the signed-in user. Throws ApiError for anything but a 2xx response. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  if (!token) throw new ApiError(401, FALLBACK_MESSAGES[401]!);

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${config.apiUrl}${path}`, { ...init, headers });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(0, "Cannot reach the Atlas API. Check that it is running.");
  }
  if (response.status === 401) {
    // The API no longer accepts the token: drop it, which shows the sign-in screen.
    await userManager().removeUser();
  }
  if (!response.ok) throw await errorFromResponse(response);
  return response;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  return (await response.json()) as T;
}

export function jsonBody(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
