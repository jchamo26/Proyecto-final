"""Script para construir el indice hibrido FAISS+BM25 una vez en despliegue."""

from __future__ import annotations

import argparse

from app.knowledge_base import HybridRAGIndexer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build hybrid RAG index")
    parser.add_argument("--docs-dir", type=str, default="/app/knowledge_base/documentos")
    parser.add_argument("--index-path", type=str, default="/data/faiss")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    indexer = HybridRAGIndexer(index_path=args.index_path)
    chunks = indexer.index_directory(args.docs_dir)
    print(f"Indexacion completada. Chunks generados: {chunks}")


if __name__ == "__main__":
    main()
