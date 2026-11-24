"use client";

import { FileText, LogOut, type LucideIcon, MessagesSquare, ScrollText, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AtlasMark } from "@/components/atlas-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMe } from "@/lib/api/hooks";
import type { Permission } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/cn";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  permission?: Permission;
}

const NAV: NavItem[] = [
  { href: "/ask", label: "Ask", icon: MessagesSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/search", label: "Search", icon: Search },
  { href: "/audit", label: "Audit log", icon: ScrollText, permission: "audit:read" },
];

function initials(name: string): string {
  const words = name.trim().split(/\s+/);
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? (words.at(-1)?.[0] ?? "") : "")).toUpperCase();
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { signOut } = useAuth();
  const me = useMe().data;
  if (!me) return null;

  const items = NAV.filter((item) => !item.permission || me.permissions.includes(item.permission));
  const name = me.display_name ?? me.email ?? "Signed in";
  const isCurrent = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="flex h-dvh">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="flex h-16 items-center gap-2.5 px-5">
          <AtlasMark className="size-8" />
          <span className="text-[17px] font-semibold tracking-tight">Atlas</span>
        </div>

        <nav aria-label="Main" className="flex-1 space-y-1 px-3 py-2">
          {items.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isCurrent(href) ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isCurrent(href)
                  ? "bg-accent-soft text-accent"
                  : "text-muted hover:bg-raised hover:text-ink",
              )}
            >
              <Icon aria-hidden className="size-[18px]" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          <div className="rounded-xl bg-raised/60 p-3">
            <p className="text-[11px] font-medium tracking-wide text-muted uppercase">Organization</p>
            <p className="mt-0.5 truncate text-sm font-medium" title={me.tenant.name}>
              {me.tenant.name}
            </p>
          </div>
          <div className="mt-3 flex items-center gap-2.5 px-1">
            <span
              aria-hidden
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-ink"
            >
              {initials(name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium" title={name}>
                {name}
              </p>
              <Badge tone="teal" className="mt-0.5 capitalize">
                {me.role}
              </Badge>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut aria-hidden className="size-4" />
              Sign out
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2.5 border-b border-line bg-surface px-4 md:hidden">
          <AtlasMark className="size-7" />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="text-sm font-semibold">Atlas</p>
            <p className="truncate text-xs text-muted">{me.tenant.name}</p>
          </div>
          <ThemeToggle />
          <Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => void signOut()}>
            <LogOut aria-hidden className="size-4" />
          </Button>
        </header>

        <main className="flex min-h-0 flex-1 flex-col">{children}</main>

        <nav
          aria-label="Main"
          className="flex shrink-0 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        >
          {items.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isCurrent(href) ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium",
                isCurrent(href) ? "text-accent" : "text-muted",
              )}
            >
              <Icon aria-hidden className="size-5" />
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}

/** The standard page body: scrolls, with a centered column. */
export function Page({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8 md:py-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted">{description}</p>
          </div>
          {actions}
        </div>
        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
