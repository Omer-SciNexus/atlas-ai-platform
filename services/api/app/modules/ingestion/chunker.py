"""Split parsed blocks into overlapping chunks.

Rules, in order of priority:

1. A chunk is never longer than ``size`` characters.
2. Chunks break at sentence ends. Only a single sentence longer than ``size`` is cut mid-way.
3. A new heading starts a new chunk, unless the current chunk is still very short.
4. Each chunk repeats the last sentences of the previous one (up to ``overlap`` characters),
   so a fact that sits on a boundary is whole in at least one chunk.

Every chunk is an exact slice of the document text (``text[char_start:char_end]``), which lets
a citation point back to a precise position in the source.

Sizes are in characters, not tokens. Characters are exact and cheap to count; the size is set
well below the embedding model's input limit, so a token count is not needed here.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.ingestion.parsers import Block

BLOCK_SEPARATOR = "\n\n"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    ordinal: int
    content: str
    heading: str | None
    page: int | None
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class _Unit:
    """A sentence, or a piece of one, located in the full document text."""

    start: int
    end: int
    heading: str | None
    page: int | None


def document_text(blocks: Sequence[Block]) -> str:
    return BLOCK_SEPARATOR.join(block.text for block in blocks)


def _units(blocks: Sequence[Block], size: int) -> list[_Unit]:
    units: list[_Unit] = []
    offset = 0
    for block in blocks:
        position = 0
        ends = [m.start() for m in _SENTENCE_END.finditer(block.text)] + [len(block.text)]
        next_starts = [m.end() for m in _SENTENCE_END.finditer(block.text)]
        for index, end in enumerate(ends):
            # Cut a sentence that is longer than a whole chunk into fixed-size pieces.
            while end - position > size:
                units.append(
                    _Unit(offset + position, offset + position + size, block.heading, block.page)
                )
                position += size
            if end > position:
                units.append(_Unit(offset + position, offset + end, block.heading, block.page))
            position = next_starts[index] if index < len(next_starts) else end
        offset += len(block.text) + len(BLOCK_SEPARATOR)
    return units


def chunk_blocks(blocks: Sequence[Block], *, size: int, overlap: int) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("overlap must be smaller than size")
    text = document_text(blocks)
    units = _units(blocks, size)
    chunks: list[Chunk] = []
    min_before_heading_break = size // 4

    first = 0
    while first < len(units):
        last = first
        while last + 1 < len(units):
            candidate = units[last + 1]
            length = units[last].end - units[first].start
            if candidate.end - units[first].start > size:
                break
            if candidate.heading != units[last].heading and length >= min_before_heading_break:
                break
            last += 1

        start, end = units[first].start, units[last].end
        chunks.append(
            Chunk(
                ordinal=len(chunks),
                content=text[start:end],
                heading=units[first].heading,
                page=units[first].page,
                char_start=start,
                char_end=end,
            )
        )
        if last + 1 >= len(units):
            break

        # Start the next chunk a few sentences back, but only inside the same heading and
        # never so far back that the chunk would not move forward.
        next_first = last + 1
        while (
            next_first - 1 > first
            and units[next_first - 1].heading == units[last + 1].heading
            and end - units[next_first - 1].start <= overlap
        ):
            next_first -= 1
        # The repeated sentences must leave room for at least one new sentence. Without
        # this, the next chunk would only repeat text the previous chunk already has.
        while units[last + 1].end - units[next_first].start > size:
            next_first += 1
        first = next_first
    return chunks
