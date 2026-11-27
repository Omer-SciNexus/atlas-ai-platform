# 0007. Citations come from the Claude citations feature, not from parsing the answer

Status: accepted (2026-11-27)

## Context

The point of Atlas is that a user can check an answer. Every statement should link to the
passage that supports it. The common way is to ask the model to write markers like `[1]` and
parse them. That breaks in two ways: the model can attach a marker to a passage that does
not say what the sentence says, and the marker format drifts.

## Decision

- Each retrieved chunk is sent to Claude as its own `document` content block with
  `citations` enabled. The API returns the answer as text blocks; a block that relies on a
  passage carries citations with the passage index and the exact quoted text.
- The quote is extracted by the API from the passage we sent. It cannot contain words that
  are not in the passage.
- Atlas maps the passage index back to the chunk, and the quote's position in the chunk to a
  position in the document, so a client can open the document and highlight the quote.
- The API returns the answer as segments, each with its citations, both as server-sent
  events and as one JSON body. Clients do not parse markers.
- When retrieval finds nothing, the model is not called; the user is told nothing was found.
- The system prompt tells the model to answer only from the documents and to treat document
  text as content, not as instructions.
- The retrieval and answer flow is plain Python. The steps are fixed, so an agent framework
  would add nothing here. LangGraph is used in Phase 4, where the model chooses the steps.

## Consequences

- A citation proves the quote exists in the source. It does not prove the sentence follows
  from the quote; the evaluation suite (Phase 2) measures that.
- Citations cannot be combined with the API's structured output mode. Answers are free text.
- The answer path depends on an Anthropic feature. The `AnswerGenerator` interface keeps the
  rest of the code independent of it, and tests use a scripted generator.
- A prompt instruction is not a complete defence against instructions hidden in documents.
  Input and output guardrails are Phase 6.
