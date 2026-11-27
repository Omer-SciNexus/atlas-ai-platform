import pytest

from app.modules.ingestion.parsers import (
    HTML,
    MARKDOWN,
    PDF,
    TEXT,
    Block,
    DocumentParseError,
    UnsupportedFileTypeError,
    detect_mime_type,
    parse,
)
from tests.support import minimal_pdf


@pytest.mark.parametrize(
    ("filename", "head", "expected"),
    [
        ("notes.txt", b"hello", TEXT),
        ("README.MD", b"# Title", MARKDOWN),
        ("10-K.htm", b"<html>", HTML),
        ("C:\\Users\\me\\report.pdf", b"%PDF-1.7", PDF),
    ],
)
def test_type_comes_from_the_extension(filename: str, head: bytes, expected: str) -> None:
    assert detect_mime_type(filename, head) == expected


@pytest.mark.parametrize(
    ("filename", "head"),
    [
        ("malware.exe", b"MZ"),
        ("no_extension", b"text"),
        ("fake.pdf", b"<html>not a pdf</html>"),  # extension says PDF, content does not
        ("fake.txt", b"%PDF-1.7 ..."),  # a PDF renamed to .txt
        ("binary.txt", b"abc\x00def"),
    ],
)
def test_unsupported_or_mismatched_files_are_rejected(filename: str, head: bytes) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_mime_type(filename, head)


def test_text_is_split_into_paragraphs_and_cleaned() -> None:
    data = b"First   paragraph\r\nsecond line.\r\n\r\n\r\n   Second paragraph.  \n"
    assert parse(data, TEXT) == [
        Block("First paragraph\nsecond line."),
        Block("Second paragraph."),
    ]


def test_text_that_is_not_utf8_is_still_decoded() -> None:
    assert parse("café".encode("cp1252"), TEXT) == [Block("café")]


def test_markdown_headings_label_the_blocks_below_them() -> None:
    data = (
        b"Intro text.\n\n# Revenue\nRevenue rose.\n\nMore on revenue.\n\n## Costs ##\n\nCosts fell."
    )
    assert parse(data, MARKDOWN) == [
        Block("Intro text."),
        Block("Revenue rose.", heading="Revenue"),
        Block("More on revenue.", heading="Revenue"),
        Block("Costs fell.", heading="Costs"),
    ]


def test_html_keeps_text_and_drops_scripts_and_styles() -> None:
    data = b"""<html><head><title>T</title><style>p{color:red}</style></head><body>
        <script>alert("x")</script>
        <h1>Risk Factors</h1>
        <p>Rates may <b>rise</b>.</p>
        <table><tr><td>Revenue</td><td>1,204</td></tr></table>
        <h2>Liquidity</h2><div>Cash is &amp; remains strong.</div>
    </body></html>"""
    assert parse(data, HTML) == [
        Block("Rates may rise.", heading="Risk Factors"),
        Block("Revenue | 1,204", heading="Risk Factors"),
        Block("Cash is & remains strong.", heading="Liquidity"),
    ]


def test_pdf_blocks_carry_page_numbers() -> None:
    blocks = parse(minimal_pdf(["Net income was 4.2 billion.", "Deposits grew 8%."]), PDF)
    assert blocks == [
        Block("Net income was 4.2 billion.", page=1),
        Block("Deposits grew 8%.", page=2),
    ]


def test_broken_pdf_is_a_parse_error_with_a_safe_message() -> None:
    with pytest.raises(DocumentParseError, match=r"could not be read|no text layer"):
        parse(b"%PDF-1.4\nthis is not really a pdf", PDF)


def test_file_without_text_is_a_parse_error() -> None:
    with pytest.raises(DocumentParseError, match="No text"):
        parse(b"<html><script>only()</script></html>", HTML)
