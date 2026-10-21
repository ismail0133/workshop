import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPO = ROOT.parents[1]

WORD = re.compile(r"[a-zàâçéèêëîïôûùüÿœ0-9]{3,}")


class HashEmbeddings(Embeddings):
    """Embeddings lexicaux déterministes (sac de mots haché) : test hors Ollama uniquement."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for w in WORD.findall(text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
        return v

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class FakeChat(BaseChatModel):
    """LLM factice piloté par `mode` ; enregistre les prompts reçus."""

    mode: str = "cite"
    delay: float = 0.0
    calls: list = []
    prompts: list = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        text = "\n".join(str(m.content) for m in messages)
        self.calls.append(1)
        self.prompts.append(text)
        if self.delay:
            time.sleep(self.delay)
        context = text.split("<contexte>")[1].split("</contexte>")[0]
        body = context.split("\n", 2)[1] if "\n" in context else context
        out = {
            "cite": f"D'après la documentation : {body[:160]} [S1]",
            "cite_fake": f"{body[:120]} [S1] et aussi [S9]",
            "nomarker": body[:200],
            "nomarker_offtopic": "Les bananes jaunes poussent abondamment sous les tropiques humides.",
            "abstain": "ABSTENTION",
            "script": "Voici <script>alert(1)</script> la réponse. [S1]",
        }.get(self.mode)
        if self.mode == "down":
            raise httpx.ConnectError("ollama down")
        if self.mode == "timeout":
            raise httpx.ReadTimeout("slow")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=out))])


def make_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return priv, pub


@pytest.fixture(scope="session")
def keys(tmp_path_factory):
    priv, pub = make_keypair()
    other_priv, _ = make_keypair()
    path = tmp_path_factory.mktemp("keys") / "jwt_public.pem"
    path.write_bytes(pub)
    return {"priv": priv, "other": other_priv, "pub_path": path}


def token(
    keys,
    role="OPERATOR",
    *,
    key="priv",
    aud="resilience-alpha",
    iss="resilience-alpha-auth",
    exp=900,
    alg="RS256",
):
    now = int(time.time())
    claims = {
        "sub": "20000000-0000-4000-8000-000000000009",
        "role": role,
        "iss": iss,
        "aud": aud,
        "iat": now,
        "nbf": now,
        "exp": now + exp,
        "jti": "j",
    }
    return jwt.encode(claims, keys[key], algorithm=alg)


DOCS = {
    "docs/runbooks/RECOVERY_RUNBOOK.md": """# Runbook de reprise
## Incident RECOVERY_FAILED
Quand un incident passe en RECOVERY_FAILED, geler les actions du runner, conserver les journaux, puis
retirer le blocage WAF de l'adresse concernée et lancer un paiement de validation manuel.
## Blocage WAF
Le blocage WAF cible une adresse IPv4 unique pendant 120 secondes avec un fencing token.
""",
    "docs/pca-pra/PCA_PRA.md": """# PCA PRA
## Objectifs de reprise
Le RTO du scénario SC-01 est de 60 secondes et le RPO est de zéro transaction confirmée perdue.
## Sauvegarde
La base PostgreSQL est sauvegardée avant chaque séance puis restaurée vers un volume distinct.
""",
    "docs/security/SECURITY_ARCHITECTURE.md": """# Sécurité
## WAF
Le WAF Nginx avec ModSecurity filtre les routes publiques et refuse les chemins internes et metrics.
""",
}


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "corpus"
    for rel, text in DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


@pytest.fixture
def built(corpus, tmp_path):
    from rag_app.index import build_index

    out = tmp_path / "index"
    build_index(corpus, out, HashEmbeddings(), "fake-embed")
    return out


def settings_for(index_dir, keys, **over):
    from rag_app.config import Settings

    base = dict(
        corpus_root=Path("/nonexistent"),
        index_dir=index_dir,
        ollama_url="http://ollama",
        chat_model="qwen2.5:1.5b",
        embed_model="fake-embed",
        top_k=3,
        min_score=0.12,
        num_ctx=2048,
        num_predict=384,
        temperature=0.1,
        timeout_seconds=5,
        jwt_public_key_file=keys["pub_path"],
        issuer="resilience-alpha-auth",
        audience="resilience-alpha",
        roles=frozenset({"OPERATOR"}),
        log_dir=None,
    )
    base.update(over)
    return Settings(**base)
