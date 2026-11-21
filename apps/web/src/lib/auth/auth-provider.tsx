"use client";

import type { User } from "oidc-client-ts";
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { currentUser, userManager } from "./manager";

type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "signedIn"; user: User };

type AuthContextValue = AuthState & {
  signIn: (returnTo?: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function signIn(returnTo?: string): Promise<void> {
  await userManager().signinRedirect({ state: { returnTo } });
}

async function signOut(): Promise<void> {
  await userManager().signoutRedirect();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    const mgr = userManager();
    let active = true;

    const onLoaded = (user: User) => setState({ status: "signedIn", user });
    const onUnloaded = () => setState({ status: "signedOut" });
    // Fires only when the automatic renewal did not succeed in time.
    const onExpired = () => void mgr.removeUser();

    mgr.events.addUserLoaded(onLoaded);
    mgr.events.addUserUnloaded(onUnloaded);
    mgr.events.addAccessTokenExpired(onExpired);

    currentUser()
      .catch(() => null)
      .then((user) => {
        if (!active) return;
        setState((previous) => {
          // A sign-in that finished while we were reading storage wins.
          if (previous.status === "signedIn") return previous;
          return user ? { status: "signedIn", user } : { status: "signedOut" };
        });
      });

    return () => {
      active = false;
      mgr.events.removeUserLoaded(onLoaded);
      mgr.events.removeUserUnloaded(onUnloaded);
      mgr.events.removeAccessTokenExpired(onExpired);
    };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({ ...state, signIn, signOut }), [state]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
