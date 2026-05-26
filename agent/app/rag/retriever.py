import hashlib
import math
import re
from typing import Dict, List

from app.rag.clinical_docs import CLINICAL_DOCUMENTS


TOKEN_RE = re.compile(r"[a-zA-Z0-9áéíóúñ]+")
EMBED_DIM = 128


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def _norm(values: List[float]) -> List[float]:
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if math.isclose(min_v, max_v):
        return [1.0 for _ in values]
    span = max_v - min_v
    return [(v - min_v) / span for v in values]


def _build_idf(docs_tokens: List[List[str]]) -> Dict[str, float]:
    n_docs = len(docs_tokens)
    df: Dict[str, int] = {}
    for tokens in docs_tokens:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    return {
        token: math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
        for token, freq in df.items()
    }


def _bm25_scores(query: str) -> List[float]:
    docs_tokens = [_tokenize(d["text"]) for d in CLINICAL_DOCUMENTS]
    query_tokens = _tokenize(query)
    idf = _build_idf(docs_tokens)
    avg_len = sum(len(t) for t in docs_tokens) / max(1, len(docs_tokens))
    k1, b = 1.5, 0.75

    scores = []
    for tokens in docs_tokens:
        token_counts: Dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        doc_len = max(1, len(tokens))
        score = 0.0
        for token in query_tokens:
            tf = token_counts.get(token, 0)
            if tf == 0:
                continue
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_len / max(1, avg_len))
            score += idf.get(token, 0.0) * (numerator / denominator)
        scores.append(score)
    return scores


def _hashed_embedding(text: str, dim: int = EMBED_DIM) -> List[float]:
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (digest[5] / 255.0)
        vec[idx] += sign * weight
    return vec


def _cosine(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _dense_scores(query: str) -> List[float]:
    q_vec = _hashed_embedding(query)
    scores = []
    for doc in CLINICAL_DOCUMENTS:
        d_vec = _hashed_embedding(doc["text"])
        scores.append(_cosine(q_vec, d_vec))
    return scores


def _expand_query(query: str) -> List[str]:
    expansions = [query]
    synonyms = {
        "diabetes": "glucosa hba1c metabolismo",
        "presion": "hipertension sistolica diastolica",
        "corazon": "cardiovascular troponina bnp",
        "renal": "creatinina tfg albuminuria",
        "pulmon": "disnea epoc asma",
    }
    lower_query = query.lower()
    for key, value in synonyms.items():
        if key in lower_query:
            expansions.append(f"{query} {value}")
    expansions.append(f"evaluacion clinica {query}")
    return expansions


def retrieve_contexts(query: str, strategy: str = "hybrid", top_k: int = 4, alpha: float = 0.6) -> Dict[str, object]:
    strategy = (strategy or "hybrid").lower()
    top_k = max(1, min(top_k, 10))
    alpha = max(0.0, min(alpha, 1.0))

    bm25 = _bm25_scores(query)
    dense = _dense_scores(query)

    if strategy == "bm25":
        final_scores = bm25
    elif strategy == "dense":
        final_scores = dense
    elif strategy == "multi_query":
        aggregate = [0.0] * len(CLINICAL_DOCUMENTS)
        expanded = _expand_query(query)
        for q in expanded:
            q_bm25 = _norm(_bm25_scores(q))
            q_dense = _norm(_dense_scores(q))
            for idx in range(len(aggregate)):
                aggregate[idx] += alpha * q_bm25[idx] + (1 - alpha) * q_dense[idx]
        final_scores = [value / len(expanded) for value in aggregate]
    else:
        bm25_norm = _norm(bm25)
        dense_norm = _norm(dense)
        final_scores = [
            alpha * bm25_norm[idx] + (1 - alpha) * dense_norm[idx]
            for idx in range(len(CLINICAL_DOCUMENTS))
        ]
        strategy = "hybrid"

    ranking = sorted(
        enumerate(final_scores),
        key=lambda item: item[1],
        reverse=True,
    )[:top_k]

    contexts = []
    for index, score in ranking:
        doc = CLINICAL_DOCUMENTS[index]
        contexts.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "text": doc["text"],
                "tags": doc["tags"],
                "score": round(float(score), 4),
            }
        )

    return {
        "strategy": strategy,
        "alpha": alpha,
        "top_k": top_k,
        "total_documents": len(CLINICAL_DOCUMENTS),
        "contexts": contexts,
    }


def retrieval_stats() -> Dict[str, object]:
    return {
        "total_documents": len(CLINICAL_DOCUMENTS),
        "available_strategies": ["bm25", "dense", "hybrid", "multi_query"],
        "default_alpha": 0.6,
    }