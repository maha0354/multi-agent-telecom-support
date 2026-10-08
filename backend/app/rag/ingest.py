"""Split the support docs into one chunk per heading section and index them in Chroma.

Run with: uv run python -m app.rag.ingest
"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import DOCS_DIR
from app.rag.store import get_collection, reset_collection

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass(frozen=True)
class Chunk:
    id: str             # stable: "<file stem>#<heading-path slug>"
    source: str         # file name
    heading_path: str   # e.g. "Roaming > Zone 4: Asia-Pacific"
    body: str

    @property
    def text(self) -> str:
        """What gets embedded: the heading path gives each section its context."""
        return f"{self.heading_path}\n\n{self.body}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def chunk_markdown(markdown: str, source: str) -> list[Chunk]:
    """One chunk per heading section; sections with no body text are skipped."""
    chunks: list[Chunk] = []
    headings: list[str] = []
    body_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(body_lines).strip()
        if headings and body:
            path = " > ".join(headings)
            chunks.append(Chunk(f"{Path(source).stem}#{_slug(path)}", source, path, body))
        body_lines.clear()

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            headings[:] = headings[: level - 1] + [match.group(2)]
        else:
            body_lines.append(line)
    flush()
    return chunks


def load_chunks(docs_dir: Path = DOCS_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.name))
    return chunks


def ingest(docs_dir: Path = DOCS_DIR) -> int:
    chunks = load_chunks(docs_dir)
    reset_collection()
    get_collection().add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{"source": c.source, "heading_path": c.heading_path} for c in chunks],
    )
    return len(chunks)


if __name__ == "__main__":
    print(f"Indexed {ingest()} chunks")
