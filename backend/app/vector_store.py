"""
Thin wrapper around a persistent ChromaDB client.

One Chroma collection per role keeps retrieval strictly scoped -- a candidate
who picks "ai_ml" can never accidentally get chunks back from the
"data_science" book collection.

A local sentence-transformers model (all-MiniLM-L6-v2) is used for both
ingestion and querying, so we never have to manage raw embeddings ourselves.
"""
import chromadb
from chromadb.utils import embedding_functions

from app.config import CHROMA_DB_DIR, TOP_K

_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def _collection_name(role: str) -> str:
    return f"role_{role}"


def get_or_create_collection(role: str):
    return _client.get_or_create_collection(
        name=_collection_name(role), embedding_function=_embedding_fn
    )


def collection_is_empty(role: str) -> bool:
    coll = get_or_create_collection(role)
    return coll.count() == 0


def add_chunks(role: str, chunks: list[str], metadatas: list[dict], ids: list[str]):
    coll = get_or_create_collection(role)
    # Chroma has upper limits on batch size; ingest in batches to be safe.
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        coll.add(
            documents=chunks[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
            ids=ids[i : i + batch_size],
        )


def query(role: str, query_text: str, top_k: int = TOP_K) -> list[dict]:
    """Return top_k relevant chunks for a single query string, scoped to role."""
    coll = get_or_create_collection(role)
    if coll.count() == 0:
        return []
    n_results = min(top_k, coll.count())
    result = coll.query(query_texts=[query_text], n_results=n_results)

    out = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        out.append({"text": doc, "source": meta.get("source_book", "unknown"), "chunk_id": meta.get("chunk_id")})
    return out


def query_multi(role: str, query_texts: list[str], top_k: int = TOP_K) -> list[dict]:
    """Run several queries and return a de-duplicated pool of retrieved chunks."""
    seen = set()
    pooled = []
    for q in query_texts:
        for chunk in query(role, q, top_k=top_k):
            key = (chunk["source"], chunk["text"][:50])
            if key not in seen:
                seen.add(key)
                pooled.append(chunk)
    return pooled
