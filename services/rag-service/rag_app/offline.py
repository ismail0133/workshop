"""Embeddings lexicaux déterministes pour tests et « couverture documentaire » hors Ollama.

⚠ Ne sert PAS en production et ne mesure PAS la qualité de nomic-embed-text : uniquement à vérifier
que les réponses attendues existent dans le corpus et à tester le pipeline sans réseau.
"""

from __future__ import annotations

import hashlib
import re

from langchain_core.embeddings import Embeddings

_WORD = re.compile(r"[a-zàâçéèêëîïôûùüÿœ0-9_]{3,}")
_STOP = frozenset(
    """les des une aux que qui quoi est sont pas pour par sur dans avec sans ses son sa leur leurs ces cet cette
    the and plus tout tous toute toutes elle elles nous vous ils mais donc car comme quand quel quelle quels
    quelles fait faire faut doit être avoir ont été ainsi aussi dont où ceci cela entre vers sous chez
    est-ce quelques selon depuis pendant afin lors puis très peu non oui bien encore même""".split()
)


class HashEmbeddings(Embeddings):
    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for w in _WORD.findall(text.lower()):
            if w in _STOP:
                continue
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
        return v

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)
