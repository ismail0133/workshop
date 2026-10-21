"""Construction de l'index, HORS requête : `python -m rag_app.ingest`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langchain_ollama import OllamaEmbeddings

from .config import Settings
from .index import build_index


def main(argv=None) -> int:
    settings = Settings.load()
    parser = argparse.ArgumentParser(prog="python -m rag_app.ingest")
    parser.add_argument("--corpus", type=Path, default=settings.corpus_root)
    parser.add_argument("--out", type=Path, default=settings.index_dir)
    args = parser.parse_args(argv)
    embeddings = OllamaEmbeddings(
        model=settings.embed_model, base_url=settings.ollama_url, client_kwargs={"timeout": 60}
    )
    manifest = build_index(args.corpus, args.out, embeddings, settings.embed_model)
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in ("index_version", "n_chunks", "dimension", "embedding_model", "refused")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
