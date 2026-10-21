"""Index FAISS natif (IndexFlatIP sur vecteurs normalisés) + métadonnées JSON + manifeste.

Aucune désérialisation pickle : `faiss.read_index` pour les vecteurs, JSON pour les métadonnées.
Le chargement vérifie les SHA-256 du manifeste ; modèle et dimension d'embedding ne se mélangent pas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
from langchain_core.embeddings import Embeddings

from . import CHUNK_CHARS, CHUNK_OVERLAP
from .corpus import load_chunks

BATCH = 16


class IndexUnavailable(RuntimeError):
    pass


def _norm(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype="float32")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_index(
    corpus_root: Path, index_dir: Path, embeddings: Embeddings, embed_model: str
) -> dict:
    chunks, refused, corpus_sha = load_chunks(corpus_root)
    if not chunks:
        raise IndexUnavailable("CORPUS_EMPTY")
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), BATCH):
        vectors.extend(embeddings.embed_documents([c.text for c in chunks[start : start + BATCH]]))
    matrix = _norm(np.array(vectors))
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise IndexUnavailable("INVALID_EMBEDDINGS")
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "index.faiss"))
    (index_dir / "chunks.json").write_text(
        json.dumps([{**c.meta(), "text": c.text} for c in chunks], ensure_ascii=False)
    )
    version = hashlib.sha256(
        f"{corpus_sha}|{embed_model}|{CHUNK_CHARS}|{CHUNK_OVERLAP}".encode()
    ).hexdigest()[:12]
    manifest = {
        "index_version": version,
        "corpus_sha256": corpus_sha,
        "embedding_model": embed_model,
        "dimension": int(matrix.shape[1]),
        "n_chunks": len(chunks),
        "documents": sorted({c.path for c in chunks}),
        "refused": refused,
        "chunk_chars": CHUNK_CHARS,
        "chunk_overlap": CHUNK_OVERLAP,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "index_sha256": _sha(index_dir / "index.faiss"),
        "chunks_sha256": _sha(index_dir / "chunks.json"),
    }
    (index_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


@dataclass
class LoadedIndex:
    faiss_index: faiss.Index
    chunks: list[dict]
    manifest: dict

    @property
    def version(self) -> str:
        return self.manifest["index_version"]

    def search(self, vector: list[float], k: int) -> list[tuple[dict, float]]:
        query = _norm(np.array([vector]))
        if query.shape[1] != self.faiss_index.d:
            raise IndexUnavailable("EMBEDDING_DIMENSION_MISMATCH")
        scores, ids = self.faiss_index.search(query, min(k, self.faiss_index.ntotal))
        return [
            (self.chunks[i], float(s)) for s, i in zip(scores[0], ids[0], strict=True) if i >= 0
        ]


def load_index(index_dir: Path, embed_model: str) -> LoadedIndex:
    paths = {n: index_dir / n for n in ("index.faiss", "chunks.json", "manifest.json")}
    if not all(p.is_file() for p in paths.values()):
        raise IndexUnavailable("INDEX_MISSING")
    manifest = json.loads(paths["manifest.json"].read_text())
    if (
        _sha(paths["index.faiss"]) != manifest["index_sha256"]
        or _sha(paths["chunks.json"]) != manifest["chunks_sha256"]
    ):
        raise IndexUnavailable("INDEX_HASH_MISMATCH")
    if manifest["embedding_model"] != embed_model:
        raise IndexUnavailable("EMBEDDING_MODEL_MISMATCH")  # pas de mélange de modèles/dimensions
    chunks = json.loads(paths["chunks.json"].read_text())
    faiss_index = faiss.read_index(str(paths["index.faiss"]))
    if faiss_index.ntotal != len(chunks) or faiss_index.d != manifest["dimension"]:
        raise IndexUnavailable("INDEX_INCONSISTENT")
    return LoadedIndex(faiss_index, chunks, manifest)
