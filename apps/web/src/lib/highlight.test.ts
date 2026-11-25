import { describe, expect, it } from "vitest";

import { highlightQuotes, missingQuotes } from "./highlight";

const TEXT = "Revenue rose 12%. Costs fell 3%. Margins widened.";

describe("highlightQuotes", () => {
  it("returns the whole text when there are no quotes", () => {
    expect(highlightQuotes(TEXT, [])).toEqual([{ text: TEXT, highlighted: false }]);
  });

  it("marks a quote inside the text", () => {
    expect(highlightQuotes(TEXT, ["Costs fell 3%."])).toEqual([
      { text: "Revenue rose 12%. ", highlighted: false },
      { text: "Costs fell 3%.", highlighted: true },
      { text: " Margins widened.", highlighted: false },
    ]);
  });

  it("marks several quotes in text order", () => {
    const parts = highlightQuotes(TEXT, ["Margins widened.", "Revenue rose 12%."]);
    expect(parts.filter((p) => p.highlighted).map((p) => p.text)).toEqual([
      "Revenue rose 12%.",
      "Margins widened.",
    ]);
  });

  it("merges quotes that overlap", () => {
    const parts = highlightQuotes(TEXT, ["Revenue rose 12%. Costs", "Costs fell 3%."]);
    expect(parts[0]).toEqual({ text: "Revenue rose 12%. Costs fell 3%.", highlighted: true });
  });

  it("ignores the whitespace around a quote", () => {
    const parts = highlightQuotes(TEXT, ["  Costs fell 3%.\n"]);
    expect(parts[1]).toEqual({ text: "Costs fell 3%.", highlighted: true });
  });

  it("never loses or repeats text", () => {
    const parts = highlightQuotes(TEXT, ["rose 12%. Costs", "Costs", "12%", "not there"]);
    expect(parts.map((p) => p.text).join("")).toBe(TEXT);
  });
});

describe("missingQuotes", () => {
  it("lists the quotes that are not in the text", () => {
    expect(missingQuotes(TEXT, ["Costs fell 3%.", "Profit doubled."])).toEqual(["Profit doubled."]);
  });
});
