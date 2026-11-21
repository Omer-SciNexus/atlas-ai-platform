export const DEFAULT_RETURN_TO = "/ask";

/**
 * Where to go after sign-in. Only a path inside this app is accepted, so a crafted link
 * cannot use the sign-in flow to send the user to another site.
 */
export function safeReturnTo(value: unknown): string {
  if (typeof value !== "string") return DEFAULT_RETURN_TO;
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return DEFAULT_RETURN_TO;
  }
  if (value.startsWith("/auth/")) return DEFAULT_RETURN_TO;
  return value;
}
