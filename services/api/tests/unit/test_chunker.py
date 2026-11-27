import itertools
import random

import pytest

from app.modules.ingestion.chunker import chunk_blocks, document_text
from app.modules.ingestion.parsers import Block


def _sentences(count: int, prefix: str = "S") -> str:
    return " ".join(f"{prefix}{i} has some words in it." for i in range(count))


def test_short_document_is_one_chunk() -> None:
    blocks = [Block("One sentence. Two sentences.", heading="Intro", page=3)]
    chunks = chunk_blocks(blocks, size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0].content == "One sentence. Two sentences."
    assert (chunks[0].heading, chunks[0].page, chunks[0].ordinal) == ("Intro", 3, 0)


def test_chunks_are_exact_slices_of_the_document_text() -> None:
    blocks = [Block(_sentences(40, "A")), Block(_sentences(40, "B"))]
    text = document_text(blocks)
    chunks = chunk_blocks(blocks, size=300, overlap=60)
    assert len(chunks) > 3
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.content
        assert len(chunk.content) <= 300
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_every_character_is_covered_and_chunks_overlap() -> None:
    blocks = [Block(_sentences(60))]
    chunks = chunk_blocks(blocks, size=300, overlap=80)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(document_text(blocks))
    for previous, current in itertools.pairwise(chunks):
        # Starts before the previous one ends (overlap), and still moves forward.
        assert previous.char_start < current.char_start < previous.char_end
        assert current.char_end > previous.char_end
        assert previous.char_end - current.char_start <= 80


def test_chunks_break_at_sentence_ends() -> None:
    chunks = chunk_blocks([Block(_sentences(50))], size=200, overlap=40)
    for chunk in chunks:
        assert chunk.content.endswith(".")
        assert chunk.content.startswith("S")


def test_no_overlap_when_overlap_is_zero() -> None:
    chunks = chunk_blocks([Block(_sentences(50))], size=200, overlap=0)
    for previous, current in itertools.pairwise(chunks):
        assert current.char_start >= previous.char_end


def test_a_new_heading_starts_a_new_chunk_without_overlap() -> None:
    blocks = [
        Block(_sentences(12, "R"), heading="Revenue"),
        Block(_sentences(12, "C"), heading="Costs"),
    ]
    chunks = chunk_blocks(blocks, size=1000, overlap=100)
    assert [c.heading for c in chunks] == ["Revenue", "Costs"]
    assert "C0" not in chunks[0].content
    assert "R11" not in chunks[1].content


def test_a_tiny_section_is_merged_into_the_next_one() -> None:
    blocks = [Block("See below.", heading="Note"), Block(_sentences(5), heading="Details")]
    chunks = chunk_blocks(blocks, size=1000, overlap=100)
    assert len(chunks) == 1
    assert chunks[0].heading == "Note"


def test_a_sentence_longer_than_a_chunk_is_cut() -> None:
    blocks = [Block("x" * 950)]
    chunks = chunk_blocks(blocks, size=300, overlap=50)
    assert [len(c.content) for c in chunks] == [300, 300, 300, 50]
    assert "".join(c.content for c in chunks) == "x" * 950


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_blocks([Block("text")], size=100, overlap=100)


def test_random_documents_keep_the_invariants() -> None:
    rng = random.Random(7)  # noqa: S311 - test data, not security
    words = ["rate", "loan", "risk", "capital", "deposit", "a", "of", "liquidity", "x" * 40]
    for _ in range(40):
        blocks = []
        for b in range(rng.randint(1, 8)):
            sentences = [
                " ".join(rng.choice(words) for _ in range(rng.randint(1, 30))) + rng.choice(".!?")
                for _ in range(rng.randint(1, 12))
            ]
            blocks.append(Block(" ".join(sentences), heading=f"H{b // 2}"))
        size = rng.randint(80, 600)
        overlap = rng.randint(0, size // 3)
        text = document_text(blocks)
        chunks = chunk_blocks(blocks, size=size, overlap=overlap)

        assert chunks[0].char_start == 0
        assert chunks[-1].char_end == len(text)
        for chunk in chunks:
            assert 0 < len(chunk.content) <= size
            assert text[chunk.char_start : chunk.char_end] == chunk.content
        for previous, current in itertools.pairwise(chunks):
            assert current.char_start > previous.char_start
            assert current.char_end > previous.char_end
            # No text is lost between two chunks (only whitespace may fall in a gap).
            assert not text[previous.char_end : current.char_start].strip()
