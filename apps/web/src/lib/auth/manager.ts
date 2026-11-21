/**
 * Sign-in with the identity provider (OpenID Connect, authorization code flow with PKCE).
 *
 * The web app is a public client: it has no secret. Tokens are kept in sessionStorage, so
 * they survive a reload but are gone when the tab closes, and they are never sent to the
 * Next.js server. The access token is short-lived and is renewed with the refresh token.
 */
import { type User, UserManager, WebStorageStateStore } from "oidc-client-ts";

import { config } from "@/lib/config";

let manager: UserManager | null = null;

export function userManager(): UserManager {
  if (typeof window === "undefined") {
    throw new Error("Sign-in runs in the browser only");
  }
  manager ??= new UserManager({
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    redirect_uri: `${window.location.origin}/auth/callback`,
    post_logout_redirect_uri: `${window.location.origin}/`,
    response_type: "code",
    scope: "openid profile email",
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });
  return manager;
}

let renewal: Promise<User | null> | null = null;

/** The signed-in user with a valid access token, or null. Renews an expired token once. */
export async function currentUser(): Promise<User | null> {
  const mgr = userManager();
  const user = await mgr.getUser();
  if (user && !user.expired) return user;
  if (!user) return null;
  // Several requests can find the token expired at the same moment; they share one renewal.
  renewal ??= mgr
    .signinSilent()
    .catch(async () => {
      await mgr.removeUser();
      return null;
    })
    .finally(() => {
      renewal = null;
    });
  return renewal;
}

export async function accessToken(): Promise<string | null> {
  return (await currentUser())?.access_token ?? null;
}
