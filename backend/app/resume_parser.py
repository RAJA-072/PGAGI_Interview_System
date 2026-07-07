import io

from pypdf import PdfReader


def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    """Extract raw text from an uploaded resume file (.pdf or .txt)."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text).strip()
    # Fallback: treat as plain text (.txt or unknown extension)
    return file_bytes.decode("utf-8", errors="ignore").strip()
