import hashlib
import json

import pytest
from conftest import HashEmbeddings
from rag_app.corpus import contains_secret, discover, load_chunks
from rag_app.index import IndexUnavailable, build_index, load_index


def test_only_whitelisted_markdown_is_read(corpus):
    for rel, text in {
        ".env": "DB_PASSWORD=supersecretvalue1234",
        "infrastructure/secrets/runtime/notes.md": "# notes\nsecret",
        "docs/source/EPSI_EXTRACT.md": "# sujet EPSI",
        "docs/architecture/data.csv": "a,b",
        "docs/architecture/dump.sql": "insert into",
        "frontend/README.md": "# front",
    }.items():
        p = corpus / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    files, refused = discover(corpus)
    assert {f.relative_to(corpus.resolve()).as_posix() for f in files} == {
        "docs/runbooks/RECOVERY_RUNBOOK.md",
        "docs/pca-pra/PCA_PRA.md",
        "docs/security/SECURITY_ARCHITECTURE.md",
    }
    assert refused == []


def test_file_with_secret_material_is_refused_even_if_whitelisted(corpus):
    (corpus / "docs/architecture").mkdir(parents=True)
    (corpus / "docs/architecture/leak.md").write_text("# x\n-----BEGIN PRIVATE KEY-----\nabc\n")
    (corpus / "docs/architecture/leak2.md").write_text(
        "# y\nOn utilise password: Sup3rSecretValue12345 ici"
    )
    files, refused = discover(corpus)
    assert all("leak" not in f.name for f in files) and len(refused) == 2


def test_symlink_escaping_root_is_ignored(corpus, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# hors racine\nconfidentiel")
    (corpus / "docs/architecture").mkdir(parents=True)
    (corpus / "docs/architecture/link.md").symlink_to(outside)
    files, _ = discover(corpus)
    assert all(f.name != "link.md" for f in files)


def test_chunks_carry_verifiable_citation_metadata(corpus):
    chunks, _, corpus_sha = load_chunks(corpus)
    assert chunks and len(corpus_sha) == 64
    for c in chunks:
        assert c.sha256 == hashlib.sha256(c.text.encode()).hexdigest()
        assert c.chunk_id.startswith(c.document_id + "#") and c.path.endswith(".md")
        assert len(c.text) <= 1400
    assert any(c.section == "Runbook de reprise > Incident RECOVERY_FAILED" for c in chunks)


def test_external_links_are_stripped():
    from rag_app.corpus import split_markdown

    out = split_markdown(
        "# T\n## S\nVoir [la source officielle](https://example.org/x) pour le détail de la procédure complète ici."
    )
    assert "http" not in out[0][1] and "la source officielle" in out[0][1]


def test_roundtrip_search_and_files(built):
    idx = load_index(built, "fake-embed")
    emb = HashEmbeddings()
    hits = idx.search(emb.embed_query("blocage WAF adresse fencing token"), 3)
    assert hits[0][0]["path"] == "docs/runbooks/RECOVERY_RUNBOOK.md"
    assert sorted(p.name for p in built.iterdir()) == [
        "chunks.json",
        "index.faiss",
        "manifest.json",
    ]  # aucun pickle
    manifest = json.loads((built / "manifest.json").read_text())
    assert manifest["embedding_model"] == "fake-embed" and manifest["n_chunks"] == len(idx.chunks)


def test_tampering_is_detected(built):
    chunks = json.loads((built / "chunks.json").read_text())
    chunks[0]["text"] = "texte modifié"
    (built / "chunks.json").write_text(json.dumps(chunks))
    with pytest.raises(IndexUnavailable, match="INDEX_HASH_MISMATCH"):
        load_index(built, "fake-embed")


def test_models_and_dimensions_are_never_mixed(built):
    with pytest.raises(IndexUnavailable, match="EMBEDDING_MODEL_MISMATCH"):
        load_index(built, "autre-modele")
    idx = load_index(built, "fake-embed")
    with pytest.raises(IndexUnavailable, match="DIMENSION"):
        idx.search([0.1] * 64, 3)


def test_missing_index_and_empty_corpus(tmp_path):
    with pytest.raises(IndexUnavailable, match="INDEX_MISSING"):
        load_index(tmp_path, "m")
    with pytest.raises(IndexUnavailable, match="CORPUS_EMPTY"):
        build_index(tmp_path, tmp_path / "o", HashEmbeddings(), "m")


def test_secret_detector_examples():
    assert contains_secret("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij")
    assert not contains_secret("Le mot de passe est géré par SOPS ; jamais dans le dépôt.")
