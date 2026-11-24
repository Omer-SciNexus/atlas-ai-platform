"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { isDark, setDark, subscribeToTheme } from "@/lib/theme";

export function ThemeToggle() {
  // The server does not know the theme; it renders the light icon and the browser corrects it.
  const dark = useSyncExternalStore(subscribeToTheme, isDark, () => false);
  const label = dark ? "Switch to light theme" : "Switch to dark theme";
  return (
    <Button variant="ghost" size="icon" aria-label={label} title={label} onClick={() => setDark(!dark)}>
      {dark ? <Sun aria-hidden className="size-4" /> : <Moon aria-hidden className="size-4" />}
    </Button>
  );
}
