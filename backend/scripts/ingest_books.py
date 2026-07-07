"""
Run this ONCE (or whenever you add/change books) to build the vector knowledge base:

    cd backend
    python scripts/ingest_books.py

It reads every PDF/TXT under data/books/<role>/, chunks it, and stores the
chunks in a Chroma collection scoped to that role. The FastAPI app never
ingests anything at request time -- it only ever queries this pre-built store.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pypdf import PdfReader

from app.config import BOOKS_DIR, SUPPORTED_ROLES
from app.chunking import chunk_text, clean_text
from app.vector_store import add_chunks, get_or_create_collection


def read_file_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def ingest_role(role: str):
    role_dir = os.path.join(BOOKS_DIR, role)
    if not os.path.isdir(role_dir):
        print(f"  [skip] no folder found at {role_dir}")
        return

    files = [
        f for f in os.listdir(role_dir)
        if f.lower().endswith((".pdf", ".txt"))
    ]
    if not files:
        print(f"  [skip] no .pdf/.txt files found in {role_dir}")
        return

    # Wipe and rebuild this role's collection so re-running is always safe/idempotent
    coll = get_or_create_collection(role)
    existing_ids = coll.get()["ids"]
    if existing_ids:
        coll.delete(ids=existing_ids)

    all_chunks, all_metas, all_ids = [], [], []
    for filename in files:
        path = os.path.join(role_dir, filename)
        print(f"  reading {filename} ...")
        raw_text = clean_text(read_file_text(path))
        chunks = chunk_text(raw_text, chunk_size_words=250, overlap_words=40)
        print(f"    -> {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metas.append({"role": role, "source_book": filename, "chunk_id": i})
            all_ids.append(f"{role}::{filename}::{i}")

    if all_chunks:
        add_chunks(role, all_chunks, all_metas, all_ids)
        print(f"  ✔ ingested {len(all_chunks)} chunks for role '{role}'")


def main():
    print(f"Ingesting books from: {os.path.abspath(BOOKS_DIR)}\n")
    for role in SUPPORTED_ROLES:
        print(f"Role: {role}")
        ingest_role(role)
        print()
    print("Done. You can now start the FastAPI server.")


if __name__ == "__main__":
    main()
