"""
Indice RAG hibrido: FAISS (dense) + BM25 (sparse).
Soporta indexacion de archivos PDF, DOCX, TXT y MD.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np
from pdfminer.high_level import extract_text as pdf_extract
from rank_bm25 import BM25Okapi
import docx

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional heavy dependency
    SentenceTransformer = None

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
HASH_DIM = 384
TOKEN_RE = re.compile(r"[a-zA-Z0-9áéíóúñ]+")


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def _hashed_embedding(text: str, dim: int = HASH_DIM) -> np.ndarray:
    vector = np.zeros((dim,), dtype=np.float32)
    for token in _tokenize(text):
        idx = abs(hash(token)) % dim
        sign = 1.0 if (abs(hash(f"{token}:s")) % 2 == 0) else -1.0
        vector[idx] += sign
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm
    return vector


class HybridRAGIndexer:
    def __init__(self, index_path: str, embedding_model: str = EMBEDDING_MODEL):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.encoder = SentenceTransformer(embedding_model) if SentenceTransformer else None
        self.chunks: List[Dict] = []
        self.faiss_index = None
        self.bm25 = None

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        if self.encoder is not None:
            return self.encoder.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                normalize_embeddings=True,
            ).astype(np.float32)
        return np.array([_hashed_embedding(text) for text in texts], dtype=np.float32)

    def load_document(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        if ext == ".pdf":
            return pdf_extract(filepath)
        if ext == ".docx":
            doc = docx.Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        if ext in {".txt", ".md"}:
            return Path(filepath).read_text(encoding="utf-8")
        raise ValueError(f"Formato no soportado: {ext}")

    def chunk_text(self, text: str, source: str) -> List[Dict]:
        words = (text or "").split()
        chunks: List[Dict] = []
        i = 0
        while i < len(words):
            chunk_words = words[i : i + CHUNK_SIZE]
            chunk_text = " ".join(chunk_words)
            if len(chunk_text.strip()) > 50:
                chunks.append(
                    {
                        "id": f"{Path(source).stem}_{i}",
                        "text": chunk_text,
                        "source": source,
                        "word_start": i,
                    }
                )
            i += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def index_directory(self, docs_dir: str) -> int:
        docs_path = Path(docs_dir)
        all_chunks: List[Dict] = []

        for filepath in docs_path.glob("**/*"):
            if filepath.suffix.lower() not in {".pdf", ".docx", ".txt", ".md"}:
                continue
            try:
                text = self.load_document(filepath.as_posix())
                all_chunks.extend(self.chunk_text(text, filepath.as_posix()))
            except Exception:
                continue

        self.chunks = all_chunks
        if self.chunks:
            self._build_indexes()
        return len(self.chunks)

    def _build_indexes(self) -> None:
        texts = [c["text"] for c in self.chunks]
        embeddings = self._encode_texts(texts)

        dim = embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(dim)
        self.faiss_index.add(embeddings)

        tokenized = [t.lower().split() for t in texts]
        self.bm25 = BM25Okapi(tokenized)

        faiss.write_index(self.faiss_index, str(self.index_path / "index.faiss"))
        with open(self.index_path / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        with open(self.index_path / "bm25.pkl", "wb") as f:
            pickle.dump(self.bm25, f)

    def load_indexes(self) -> None:
        self.faiss_index = faiss.read_index(str(self.index_path / "index.faiss"))
        with open(self.index_path / "chunks.json", "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        with open(self.index_path / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)

    def search(self, query: str, top_k: int = 5, alpha: float = 0.6) -> List[Dict]:
        if self.faiss_index is None or self.bm25 is None:
            raise RuntimeError("Indices no cargados")

        query_emb = self._encode_texts([query])
        dense_scores, dense_indices = self.faiss_index.search(query_emb, max(top_k * 3, top_k))

        dense_scores = dense_scores[0]
        dense_indices = dense_indices[0]

        if dense_scores.size and dense_scores.max() > dense_scores.min():
            dense_norm = (dense_scores - dense_scores.min()) / (dense_scores.max() - dense_scores.min())
        else:
            dense_norm = np.ones_like(dense_scores)

        bm25_scores = np.array(self.bm25.get_scores(query.lower().split()))
        if bm25_scores.size and bm25_scores.max() > 0:
            bm25_norm = bm25_scores / bm25_scores.max()
        else:
            bm25_norm = np.zeros_like(bm25_scores)

        results: List[Dict] = []
        seen = set()
        for d_score, d_norm, idx in zip(dense_scores, dense_norm, dense_indices):
            if idx < 0 or idx in seen:
                continue
            seen.add(int(idx))
            combined = alpha * float(d_norm) + (1.0 - alpha) * float(bm25_norm[idx])
            chunk = self.chunks[idx]
            results.append(
                {
                    **chunk,
                    "score_dense": float(d_score),
                    "score_bm25": float(bm25_norm[idx]),
                    "score_combined": float(combined),
                }
            )

        results.sort(key=lambda x: x["score_combined"], reverse=True)
        return results[:top_k]
