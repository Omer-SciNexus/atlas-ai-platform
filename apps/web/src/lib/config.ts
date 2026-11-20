/** Public settings. They are compiled into the browser bundle, so none of them is a secret. */
export const config = {
  apiUrl: (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, ""),
  oidcAuthority: process.env.NEXT_PUBLIC_OIDC_AUTHORITY ?? "http://localhost:8080/realms/atlas",
  oidcClientId: process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "atlas-web",
  /** Demo sign-in hints are shown in development only. */
  showDemoUsers: process.env.NODE_ENV !== "production",
} as const;
