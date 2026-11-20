/** Light and dark theme. The choice is the `dark` class on <html>, saved in localStorage. */

const KEY = "atlas-theme";
const CHANGED = "atlas-theme-change";

export function subscribeToTheme(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange);
  return () => window.removeEventListener(CHANGED, onChange);
}

export function isDark(): boolean {
  return document.documentElement.classList.contains("dark");
}

export function setDark(dark: boolean): void {
  document.documentElement.classList.toggle("dark", dark);
  try {
    localStorage.setItem(KEY, dark ? "dark" : "light");
  } catch {
    // Storage can be blocked; the choice then lasts until the page is reloaded.
  }
  window.dispatchEvent(new Event(CHANGED));
}

/** Runs before the first paint, so the page never flashes in the wrong theme. */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${KEY}");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;if(d)document.documentElement.classList.add("dark")}catch(e){}})()`;
