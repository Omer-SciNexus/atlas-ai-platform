"use client";

import { ArrowRight, Building2, Quote, ScrollText } from "lucide-react";
import { useState } from "react";

import { AtlasMark } from "@/components/atlas-mark";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/lib/auth/auth-provider";
import { config } from "@/lib/config";

const POINTS = [
  {
    icon: Quote,
    title: "Every statement shows its source",
    text: "Answers come with the exact quote from your document that supports them.",
  },
  {
    icon: Building2,
    title: "Your organization's data only",
    text: "The database itself keeps each organization's documents apart.",
  },
  {
    icon: ScrollText,
    title: "A record of what happened",
    text: "Uploads, deletions and questions are written to an audit log that cannot be edited.",
  },
];

const DEMO_USERS = [
  { name: "alice", organization: "Acme Financial", role: "admin" },
  { name: "bob", organization: "Acme Financial", role: "viewer" },
  { name: "carol", organization: "Globex Retail", role: "owner" },
];

export function SignInScreen() {
  const { signIn } = useAuth();
  const [state, setState] = useState<"idle" | "redirecting" | "failed">("idle");

  async function start() {
    setState("redirecting");
    try {
      await signIn(window.location.pathname + window.location.search);
    } catch {
      // The identity provider could not be reached, so no redirect happened.
      setState("failed");
    }
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-[#0b1f44] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="absolute -top-40 -right-40 size-[34rem] rounded-full bg-[#4f46e5] opacity-40 blur-3xl"
        />
        <div
          aria-hidden
          className="absolute -bottom-52 -left-32 size-[30rem] rounded-full bg-[#14b8a6] opacity-25 blur-3xl"
        />
        <div className="relative flex items-center gap-3">
          <span className="rounded-xl bg-white p-1.5">
            <AtlasMark className="size-7" />
          </span>
          <span className="text-lg font-semibold tracking-tight">Atlas</span>
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-4xl leading-tight font-semibold tracking-tight text-balance">
            Answers from your company&apos;s documents, with the proof attached.
          </h1>
          <ul className="mt-10 space-y-6">
            {POINTS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <Icon aria-hidden className="size-5 text-[#5eead4]" />
                </span>
                <div>
                  <p className="font-medium">{title}</p>
                  <p className="mt-0.5 text-sm text-white/70">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-white/50">Multi-tenant AI knowledge platform</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <AtlasMark className="size-9" />
            <span className="text-lg font-semibold tracking-tight">Atlas</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-2 text-sm text-muted">
            Use your organization account. You will be sent to your identity provider and back.
          </p>
          <Button
            className="mt-6 h-11 w-full text-[15px]"
            onClick={() => void start()}
            disabled={state === "redirecting"}
          >
            {state === "redirecting" ? <Spinner /> : null}
            Continue with single sign-on
            {state !== "redirecting" && <ArrowRight aria-hidden className="size-4" />}
          </Button>
          {state === "failed" && (
            <Notice tone="danger" className="mt-4">
              The identity provider could not be reached. Check that it is running, then try again.
            </Notice>
          )}

          {config.showDemoUsers && (
            <div className="mt-8 rounded-xl border border-dashed border-line p-4">
              <p className="text-xs font-medium tracking-wide text-muted uppercase">
                Local demo accounts
              </p>
              <table className="mt-2 w-full text-sm">
                <tbody>
                  {DEMO_USERS.map((user) => (
                    <tr key={user.name}>
                      <td className="py-1 font-mono">{user.name}</td>
                      <td className="py-1 text-muted">{user.organization}</td>
                      <td className="py-1 text-right text-muted">{user.role}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted">The password is the same as the user name.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
