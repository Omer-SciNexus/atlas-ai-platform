import Link from "next/link";

import { AtlasMark } from "@/components/atlas-mark";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
      <AtlasMark className="size-12" />
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted">This address does not exist in Atlas.</p>
      <Link
        href="/ask"
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-strong"
      >
        Go to Ask
      </Link>
    </main>
  );
}
