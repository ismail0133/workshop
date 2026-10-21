"""Recette du RAG : rappel@3 des références, séparation documentaire/hors corpus, injection.

    python -m rag_app.evaluate --corpus /repo --offline            # couverture du corpus, sans Ollama
    python -m rag_app.evaluate --corpus /repo                      # embeddings Ollama réels
    python -m rag_app.evaluate --corpus /repo --generate           # + génération réelle (injection, citations)

Les chiffres `--offline` ne mesurent PAS la qualité des embeddings réels. Seule l'exécution avec Ollama
sur le PC Hôte valide RAG-01 (≥ 8 bonnes références sur 10) et fixe RAG_MIN_SCORE.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .chain import RagChain
from .config import Settings
from .index import build_index, load_index
from .retriever import FaissRetriever

QUESTIONS = Path(__file__).resolve().parents[1] / "rag_eval" / "questions.json"


def run(corpus: Path, embeddings, embed_model: str, k: int = 3, llm=None, min_score: float = 0.0) -> dict:
    data = json.loads(QUESTIONS.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        manifest = build_index(corpus, Path(tmp), embeddings, embed_model)
        index = load_index(Path(tmp), embed_model)
        retriever = FaissRetriever(index=index, embeddings=embeddings, k=k, min_score=-1.0)

        def top(question: str):
            return [(d.metadata["path"], d.metadata["score"]) for d in retriever.invoke(question)]

        doc_rows, hits, rr = [], 0, 0.0
        for item in data["documentary"]:
            found = top(item["q"])
            paths = [p for p, _ in found]
            rank = next((i + 1 for i, p in enumerate(paths) if p in item["expected"]), None)
            hits += rank is not None
            rr += 1 / rank if rank else 0
            doc_rows.append({"id": item["id"], "hit_at_k": rank is not None, "rank": rank,
                             "top1_score": found[0][1] if found else None, "top_paths": paths})
        ooc_rows = [{"id": i["id"], "top1_score": (top(i["q"]) or [(None, None)])[0][1]} for i in data["out_of_corpus"]]
        doc_scores = [r["top1_score"] for r in doc_rows if r["top1_score"] is not None]
        ooc_scores = [r["top1_score"] for r in ooc_rows if r["top1_score"] is not None]
        separable = bool(doc_scores and ooc_scores and min(doc_scores) > max(ooc_scores))
        result = {
            "index": {k: manifest[k] for k in ("index_version", "n_chunks", "dimension", "embedding_model", "refused")},
            "recall_at_k": hits / len(data["documentary"]),
            "hits": f"{hits}/{len(data['documentary'])}",
            "mrr": rr / len(data["documentary"]),
            "documentary": doc_rows,
            "out_of_corpus": ooc_rows,
            "abstention_threshold": {
                "separable": separable,
                "suggested": round((min(doc_scores) + max(ooc_scores)) / 2, 3) if separable else None,
                "doc_min_top1": min(doc_scores) if doc_scores else None,
                "ooc_max_top1": max(ooc_scores) if ooc_scores else None,
            },
        }
        if llm is not None:
            chain = RagChain(FaissRetriever(index=index, embeddings=embeddings, k=k, min_score=min_score), llm)
            ooc_abst = [chain.answer(i["q"]).abstained for i in data["out_of_corpus"]]
            inj = []
            for item in data["injection"]:
                a = chain.answer(item["q"])
                bad = [s for s in item["must_not_contain"] if s.lower() in a.answer.lower()]
                inj.append({"id": item["id"], "resisted": not bad, "abstained": a.abstained, "leaked": bad})
            cited = [chain.answer(i["q"]) for i in data["documentary"]]
            result["generation"] = {
                "out_of_corpus_abstained": f"{sum(ooc_abst)}/{len(ooc_abst)}",
                "injection": inj,
                "documentary_grounded": f"{sum(a.grounded for a in cited)}/{len(cited)}",
            }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag_app.evaluate")
    parser.add_argument("--corpus", type=Path, required=True, help="racine du dépôt (docs/, security/)")
    parser.add_argument("--offline", action="store_true", help="embeddings lexicaux, sans Ollama (couverture seulement)")
    parser.add_argument("--generate", action="store_true", help="appelle aussi le LLM Ollama")
    args = parser.parse_args(argv)
    settings = Settings.load()
    if args.offline:
        from .offline import HashEmbeddings

        embeddings, model, llm = HashEmbeddings(), "offline-hash", None
    else:
        from langchain_ollama import ChatOllama, OllamaEmbeddings

        embeddings = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_url, client_kwargs={"timeout": 60})
        model = settings.embed_model
        llm = ChatOllama(model=settings.chat_model, base_url=settings.ollama_url, temperature=settings.temperature,
                         num_ctx=settings.num_ctx, num_predict=settings.num_predict, client_kwargs={"timeout": 60}) if args.generate else None
    print(json.dumps(run(args.corpus, embeddings, model, settings.top_k, llm, settings.min_score), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
