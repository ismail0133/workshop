"""Retriever LangChain au-dessus de l'index FAISS natif (sans vectorstore pickle)."""

from __future__ import annotations

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from .index import LoadedIndex


class FaissRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    index: LoadedIndex
    embeddings: Embeddings
    k: int = 3
    min_score: float = 0.45

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> list[Document]:
        hits = self.index.search(self.embeddings.embed_query(query), self.k)
        return [
            Document(
                page_content=chunk["text"],
                metadata={**{k: v for k, v in chunk.items() if k != "text"}, "score": score},
            )
            for chunk, score in hits
            if score >= self.min_score
        ]
