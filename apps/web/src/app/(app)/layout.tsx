"use client";

import type { ReactNode } from "react";

import { AuthGate } from "@/components/auth-gate";
import { Shell } from "@/components/shell";
import { AskProvider } from "@/features/ask/ask-provider";

/** Everything in this group needs a signed-in user. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AskProvider>
        <Shell>{children}</Shell>
      </AskProvider>
    </AuthGate>
  );
}
