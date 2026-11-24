"use client";

import type { ReactNode } from "react";

import { AtlasMark } from "@/components/atlas-mark";
import { SignInScreen } from "@/components/sign-in-screen";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { useMe } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth/auth-provider";

function Splash({ label }: { label: string }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4" role="status">
      <AtlasMark className="size-12" />
      <p className="flex items-center gap-2 text-sm text-muted">
        <Spinner /> {label}
      </p>
    </div>
  );
}

/** Loads the user's profile. A user whose organization is not set up in Atlas stops here. */
function ProfileGate({ children }: { children: ReactNode }) {
  const me = useMe();
  const { signOut } = useAuth();

  if (me.isPending) return <Splash label="Loading your workspace…" />;
  if (me.isError) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6">
        <AtlasMark className="size-12" />
        <h1 className="text-lg font-semibold">Atlas could not load your workspace</h1>
        <ErrorNotice error={me.error} className="max-w-md" />
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void signOut()}>
            Sign out
          </Button>
          <Button onClick={() => void me.refetch()}>Try again</Button>
        </div>
      </div>
    );
  }
  return children;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (auth.status === "loading") return <Splash label="Starting Atlas…" />;
  if (auth.status === "signedOut") return <SignInScreen />;
  return <ProfileGate>{children}</ProfileGate>;
}
