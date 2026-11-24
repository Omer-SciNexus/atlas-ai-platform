"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AtlasMark } from "@/components/atlas-mark";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { userManager } from "@/lib/auth/manager";
import { safeReturnTo } from "@/lib/auth/return-to";

// The authorization code can be exchanged only once, but React runs effects twice in
// development. Keeping the promise here makes both runs share one exchange.
let exchange: Promise<string> | null = null;

function completeSignIn(): Promise<string> {
  exchange ??= userManager()
    .signinCallback()
    .then((user) => {
      const state = user?.state as { returnTo?: unknown } | undefined;
      return safeReturnTo(state?.returnTo);
    });
  return exchange;
}

export default function SignInCallbackPage() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    completeSignIn().then(
      (returnTo) => router.replace(returnTo),
      () => setFailed(true),
    );
  }, [router]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
      <AtlasMark className="size-12" />
      {failed ? (
        <>
          <h1 className="text-lg font-semibold">Sign-in did not finish</h1>
          <p className="max-w-sm text-sm text-muted">
            The sign-in link was already used or has expired. Start again.
          </p>
          <Button
            onClick={() => {
              exchange = null;
              router.replace("/ask");
            }}
          >
            Back to sign in
          </Button>
        </>
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted" role="status">
          <Spinner /> Signing you in…
        </p>
      )}
    </main>
  );
}
