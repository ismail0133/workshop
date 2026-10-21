import json

import pytest
from conftest import REPO, FakeChat
from rag_app.evaluate import QUESTIONS, run
from rag_app.offline import HashEmbeddings

# Le corpus de l'assistant, ce sont les documents de l'équipe : ces tests lisent aussi les documents du pilier
# gouvernance (runbook, PCA/PRA, NIS2/DORA). Tant qu'ils ne sont pas présents, on ignore ces contrôles.
GOV_DOCS = ("docs/runbooks/RECOVERY_RUNBOOK.md", "docs/pca-pra/PCA_PRA.md", "docs/compliance/NIS2_DORA.md")
needs_gov_docs = pytest.mark.skipif(
    not all((REPO / p).is_file() for p in GOV_DOCS), reason="documents du pilier gouvernance absents du dépôt"
)



@needs_gov_docs
def test_recipe_file_is_well_formed_and_references_exist():
    data = json.loads(QUESTIONS.read_text())
    assert len(data["documentary"]) == 10 and len(data["out_of_corpus"]) == 3 and len(data["injection"]) == 3
    for item in data["documentary"]:
        assert item["expected"] and all((REPO / p).is_file() for p in item["expected"]), item["id"]
    assert all(i["must_not_contain"] for i in data["injection"])


@needs_gov_docs
def test_corpus_still_contains_the_answers_offline_coverage_guard():
    """Garde-fou de couverture (embeddings lexicaux) : NE mesure PAS la qualité de nomic-embed-text."""
    result = run(REPO, HashEmbeddings(), "offline-hash", k=3)
    assert result["index"]["refused"] == []                       # aucun secret dans le corpus réel
    assert result["recall_at_k"] >= 0.8, [r for r in result["documentary"] if not r["hit_at_k"]]
    assert all(not p.startswith(("infrastructure/", "frontend/", "database/")) for r in result["documentary"] for p in r["top_paths"])


@needs_gov_docs
def test_real_corpus_excludes_the_epsi_subject_and_secrets():
    from rag_app.corpus import load_chunks
    chunks, refused, _ = load_chunks(REPO)
    paths = {c.path for c in chunks}
    assert "docs/runbooks/RECOVERY_RUNBOOK.md" in paths and "docs/pca-pra/PCA_PRA.md" in paths
    assert not any(p.startswith(("docs/source", "infrastructure", "frontend", "database", "tests")) for p in paths)
    assert not any("secret" in p.lower() and "SECURITY" not in p for p in paths) and refused == []


def test_generation_branch_of_the_recipe_runs_with_a_fake_model():
    result = run(REPO, HashEmbeddings(), "offline-hash", k=3, llm=FakeChat(mode="cite", calls=[], prompts=[]), min_score=0.1)
    gen = result["generation"]
    assert len(gen["injection"]) == 3 and all(i["resisted"] for i in gen["injection"])
