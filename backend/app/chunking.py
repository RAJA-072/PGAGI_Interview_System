import re


def clean_text(text: str) -> str:
    """Light cleanup: collapse whitespace, drop empty lines."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 40) -> list[str]:
    """
    Split text into overlapping word-count chunks.

    Word-count based chunking is simpler than token counting and good enough for
    a textbook-style corpus. Overlap keeps a concept from being cut in half at a
    chunk boundary.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(chunk_size_words - overlap_words, 1)
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size_words]
        if len(chunk_words) < 20:  # skip tiny trailing fragments
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size_words >= len(words):
            break
    return chunks
