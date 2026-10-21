"""Corpus : liste blanche stricte, découpage par titres Markdown, métadonnées de citation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from . import CHUNK_CHARS, CHUNK_OVERLAP

# Liste blanche (RAG_DESIGN) : architecture, catalogue, contrats, runbooks, SC-01, PCA/PRA,
# gouvernance, limites connues et résultats d'essais validés. Rien d'autre n'est lu.
ALLOWED_GLOBS: tuple[str, ...] = (
    "docs/architecture/*.md",
    "docs/api/API_CONTRACTS.md",
    "docs/api/PHASE1_CONTRACT_CHANGES.md",
    "docs/security/*.md",
    "docs/pca-pra/*.md",
    "docs/runbooks/*.md",
    "docs/ebios/*.md",
    "docs/compliance/*.md",
    "docs/governance/*.md",
    "docs/ml/*.md",
    "docs/rag/*.md",
    "docs/observability/*.md",
    "security/attack-scenarios/*.md",
    "security/siem/README.md",
    "security/hardening/README.md",
)

# Défense en profondeur : même dans la liste blanche, un fichier contenant ceci est refusé.
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AGE-SECRET-KEY-[A-Z0-9]+"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9+/_=-]{16,}"),
)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    path: str
    section: str
    text: str
    sha256: str

    def meta(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "path": self.path,
            "section": self.section,
            "sha256": self.sha256,
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def discover(root: Path) -> tuple[list[Path], list[str]]:
    """Retourne (fichiers autorisés, fichiers refusés avec motif). Aucun lien symbolique suivi
    hors racine ; seuls les .md de la liste blanche sont lus."""
    root = root.resolve()
    found: dict[str, Path] = {}
    for pattern in ALLOWED_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.suffix != ".md" or not path.is_file():
                continue
            resolved = path.resolve()
            if root not in resolved.parents:
                continue  # lien symbolique sortant de la racine
            found[str(resolved.relative_to(root))] = resolved
    allowed, refused = [], []
    for rel, path in sorted(found.items()):
        if contains_secret(path.read_text(encoding="utf-8", errors="replace")):
            refused.append(f"{rel}: SECRET_PATTERN")
        else:
            allowed.append(path)
    return allowed, refused


def split_markdown(text: str) -> list[tuple[str, str]]:
    """Découpe par titres puis par taille ; retourne (section, texte)."""
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    sections = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers, strip_headers=False
    ).split_text(text)
    sizer = RecursiveCharacterTextSplitter(chunk_size=CHUNK_CHARS, chunk_overlap=CHUNK_OVERLAP)
    out: list[tuple[str, str]] = []
    for doc in sections:
        section = (
            " > ".join(doc.metadata[k] for k in ("h1", "h2", "h3") if k in doc.metadata)
            or "(introduction)"
        )
        for piece in sizer.split_text(doc.page_content):
            piece = re.sub(
                r"\[([^\]]+)\]\((?:https?:)?//[^)]*\)", r"\1", piece
            ).strip()  # liens externes
            if len(piece) >= 40:
                out.append((section, piece))
    return out


def load_chunks(root: Path) -> tuple[list[Chunk], list[str], str]:
    """Retourne (chunks, refusés, corpus_sha256)."""
    files, refused = discover(root)
    root = root.resolve()
    chunks: list[Chunk] = []
    digest = hashlib.sha256()
    for path in files:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        digest.update(rel.encode() + b"\0" + sha256_text(text).encode())
        document_id = re.sub(r"[^a-z0-9]+", "-", rel.removesuffix(".md").lower()).strip("-")
        for n, (section, piece) in enumerate(split_markdown(text)):
            chunks.append(
                Chunk(
                    f"{document_id}#{n:03d}", document_id, rel, section, piece, sha256_text(piece)
                )
            )
    return chunks, refused, digest.hexdigest()
