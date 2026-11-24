"""Turn uploaded bytes into text blocks.

A block is one paragraph-sized piece of text, with the heading it sits under and, for PDFs,
its page number. The chunker builds chunks from blocks, so the heading and page travel with
every chunk and end up in citations.
"""

import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

TEXT = "text/plain"
MARKDOWN = "text/markdown"
HTML = "text/html"
PDF = "application/pdf"

_BY_EXTENSION = {
    ".txt": TEXT,
    ".md": MARKDOWN,
    ".markdown": MARKDOWN,
    ".html": HTML,
    ".htm": HTML,
    ".pdf": PDF,
}
SUPPORTED_EXTENSIONS = tuple(sorted(_BY_EXTENSION))


class UnsupportedFileTypeError(Exception):
    pass


class DocumentParseError(Exception):
    """The file is of a supported type but could not be read. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Block:
    text: str
    heading: str | None = None
    page: int | None = None


def detect_mime_type(filename: str, head: bytes) -> str:
    """Decide the type from the file name, then check it against the content.

    The client's Content-Type header is ignored: it is whatever the client says it is.
    """
    extension = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    mime_type = _BY_EXTENSION.get(extension)
    if mime_type is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    is_pdf = head.lstrip().startswith(b"%PDF-")
    if (mime_type == PDF) != is_pdf:
        raise UnsupportedFileTypeError("File content does not match its extension")
    if mime_type != PDF and b"\x00" in head:
        raise UnsupportedFileTypeError("File content is not text")
    return mime_type


def parse(data: bytes, mime_type: str) -> list[Block]:
    if mime_type == PDF:
        blocks = _parse_pdf(data)
    elif mime_type == HTML:
        blocks = _parse_html(_decode(data))
    elif mime_type == MARKDOWN:
        blocks = _parse_markdown(_decode(data))
    elif mime_type == TEXT:
        blocks = [Block(p) for p in _paragraphs(_decode(data))]
    else:
        raise UnsupportedFileTypeError(f"Unsupported type: {mime_type}")
    if not blocks:
        raise DocumentParseError("No text could be extracted from the file")
    return blocks


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n")


def _clean(text: str) -> str:
    lines = (_WHITESPACE.sub(" ", line).strip() for line in text.replace("\x00", "").split("\n"))
    return "\n".join(line for line in lines if line)


def _paragraphs(text: str) -> list[str]:
    return [c for c in (_clean(p) for p in _BLANK_LINES.split(text)) if c]


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")


def _parse_markdown(text: str) -> list[Block]:
    blocks: list[Block] = []
    heading: str | None = None
    for paragraph in _paragraphs(text):
        # A heading may be followed by body text without a blank line between them.
        body: list[str] = []
        for line in paragraph.split("\n"):
            match = _MD_HEADING.match(line)
            if match:
                if body:
                    blocks.append(Block("\n".join(body), heading))
                    body = []
                heading = match.group(2)[:300] or heading
            else:
                body.append(line)
        if body:
            blocks.append(Block("\n".join(body), heading))
    return blocks


_SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template", "svg", "head"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BLOCK_TAGS = _HEADING_TAGS | frozenset(
    {
        "p", "div", "section", "article", "header", "footer", "main", "aside", "nav",
        "li", "ul", "ol", "table", "tr", "blockquote", "pre", "br", "hr", "dd", "dt",
    }
)  # fmt: skip
_CELL_TAGS = frozenset({"td", "th"})


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._buffer: list[str] = []
        self._heading: str | None = None
        self._skip_depth = 0
        self._in_heading = False

    def _flush(self) -> None:
        text = _clean("".join(self._buffer))
        self._buffer = []
        if not text:
            return
        if self._in_heading:
            self._heading = text.replace("\n", " ")[:300]
        else:
            self.blocks.append(Block(text, self._heading))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._flush()
            self._in_heading = tag in _HEADING_TAGS
        elif tag in _CELL_TAGS and self._buffer:
            # Keep table cells apart, so "Revenue" and "1,204" do not become "Revenue1,204".
            self._buffer.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._flush()
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _parse_html(text: str) -> list[Block]:
    parser = _HtmlText()
    parser.feed(text)
    parser.close()
    return parser.blocks


def _parse_pdf(data: bytes) -> list[Block]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentParseError("The PDF is password-protected")
        blocks: list[Block] = []
        for number, page in enumerate(reader.pages, start=1):
            blocks.extend(Block(p, page=number) for p in _paragraphs(page.extract_text() or ""))
    except PyPdfError as exc:
        raise DocumentParseError("The PDF could not be read") from exc
    if not blocks:
        raise DocumentParseError("The PDF has no text layer (scanned PDFs are not supported yet)")
    return blocks
