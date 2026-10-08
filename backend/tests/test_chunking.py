from app.rag.ingest import chunk_markdown, load_chunks

SAMPLE = """# Roaming

Intro text.

## Zone 4: Asia-Pacific

Countries: Japan.

### Fair use

20 GB per month.

## Empty section

## Zone 1

EU countries.
"""


def test_one_chunk_per_section_with_heading_path():
    chunks = chunk_markdown(SAMPLE, "roaming.md")
    assert [c.heading_path for c in chunks] == [
        "Roaming",
        "Roaming > Zone 4: Asia-Pacific",
        "Roaming > Zone 4: Asia-Pacific > Fair use",
        "Roaming > Zone 1",
    ]


def test_heading_path_is_prepended_to_embedded_text():
    chunk = chunk_markdown(SAMPLE, "roaming.md")[1]
    assert chunk.text.startswith("Roaming > Zone 4: Asia-Pacific\n\n")
    assert "Japan" in chunk.text


def test_stable_ids():
    chunk = chunk_markdown(SAMPLE, "roaming.md")[1]
    assert chunk.id == "roaming#roaming-zone-4-asia-pacific"


def test_real_docs_have_unique_ids_and_japan_with_its_conditions():
    chunks = load_chunks()
    assert len({c.id for c in chunks}) == len(chunks)
    zone4 = next(c for c in chunks if "Zone 4" in c.heading_path)
    assert "Japan" in zone4.body and "fair-use" in zone4.body
