export interface TextPart {
  text: string;
  highlighted: boolean;
}

/**
 * Split `content` into parts, marking where the quotes occur.
 *
 * Quotes come from the model API as exact text from the passage, so a plain search finds
 * them. A quote that is not found is left out; the caller shows it on its own.
 */
export function highlightQuotes(content: string, quotes: readonly string[]): TextPart[] {
  const ranges: Array<[start: number, end: number]> = [];
  for (const quote of quotes) {
    const needle = quote.trim();
    if (!needle) continue;
    const start = content.indexOf(needle);
    if (start !== -1) ranges.push([start, start + needle.length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);

  const parts: TextPart[] = [];
  let position = 0;
  for (const [start, end] of ranges) {
    if (end <= position) continue; // inside the previous highlight
    const from = Math.max(start, position);
    if (from > position) parts.push({ text: content.slice(position, from), highlighted: false });
    const last = parts.at(-1);
    // Quotes that touch or overlap become one highlight.
    if (last?.highlighted && from === position) last.text += content.slice(from, end);
    else parts.push({ text: content.slice(from, end), highlighted: true });
    position = end;
  }
  if (position < content.length) parts.push({ text: content.slice(position), highlighted: false });
  return parts;
}

export function missingQuotes(content: string, quotes: readonly string[]): string[] {
  return quotes.filter((quote) => quote.trim() && !content.includes(quote.trim()));
}
