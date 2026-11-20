const UNITS = ["B", "KB", "MB", "GB"] as const;

export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  return `${value.toFixed(digits)} ${UNITS[unit]}`;
}

const STEPS: Array<[limit: number, seconds: number, unit: Intl.RelativeTimeFormatUnit]> = [
  [60, 1, "second"],
  [3600, 60, "minute"],
  [86_400, 3600, "hour"],
  [2_592_000, 86_400, "day"],
  [31_536_000, 2_592_000, "month"],
  [Infinity, 31_536_000, "year"],
];

/** "3 minutes ago". `now` is a parameter so the function can be tested. */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 10) return "just now";
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [limit, size, unit] of STEPS) {
    if (absolute < limit) return formatter.format(Math.round(seconds / size), unit);
  }
  return formatter.format(Math.round(seconds / 31_536_000), "year");
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "medium" }).format(
    new Date(iso),
  );
}
