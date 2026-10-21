"""Écriture sûre de `ua:Token` dans `infrastructure/waf/blocklist/blocklist.txt`.

Contrat du WAF (infrastructure/waf/README.md) : une entrée par ligne, token `[A-Za-z0-9._-]{4,64}`,
comparaison insensible à la casse, écriture atomique (fichier temporaire puis renommage). Un blocage
`ua:` s'applique à TOUS les clients (l'allowlist ne protège que les IP) : un faux positif coupe donc
tous les utilisateurs qui portent ce User-Agent. Garde-fous, dans l'ordre :

  1. le token est dérivé du produit en tête du User-Agent (`ResilienceAttack/1.0` -> `ResilienceAttack`) ;
  2. il doit respecter le format du WAF ;
  3. il ne doit pas être une sous-chaîne d'un navigateur courant (même échantillon que le WAF) ni d'un
     User-Agent normal vu à l'entraînement ni d'une liste `never_block` fournie par l'exploitant ;
  4. plafond d'entrées posées par le détecteur ;
  5. par défaut, simulation (dry-run) : rien n'est écrit sans activation explicite.

Limite connue : la lecture-modification-écriture n'est pas verrouillée contre un autre écrivain
(l'orchestrateur de remédiation) ; la fenêtre de course est de quelques millisecondes.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")
_PRODUCT_RE = re.compile(r"^[A-Za-z0-9._-]+")
# Copie de BROWSER_UA_SAMPLE de infrastructure/waf/blocklist.sh : un token qui y figure est refusé par le WAF.
BROWSER_UA_SAMPLE = (
    "mozilla/5.0 (windows nt 10.0; win64; x64; linux; android; iphone; macintosh; intel mac os x) "
    "applewebkit/537.36 (khtml, like gecko) chrome/155.0.0.0 safari/537.36 edg/155 firefox/130 "
    "version/17 mobile opr/100"
)
MANAGED_MARK = "# ml-detector"


def candidate_token(user_agent: str) -> str | None:
    """Premier produit du User-Agent, ou None s'il n'en a pas de présentable."""
    match = _PRODUCT_RE.match(user_agent.strip())
    return match.group(0) if match else None


def check_token(token: str | None, normal_user_agents=(), never_block=()) -> str | None:
    """None si le token peut être bloqué, sinon le code de refus."""
    if not token or not TOKEN_RE.match(token):
        return "REFUSED_BAD_TOKEN"
    low = token.lower()
    if low in BROWSER_UA_SAMPLE:
        return "REFUSED_BROWSER"
    if any(low in ua.lower() for ua in normal_user_agents):
        return "REFUSED_SEEN_NORMAL"
    if any(low in protected.lower() or protected.lower() in low for protected in never_block if protected):
        return "REFUSED_PROTECTED"
    return None


@dataclass(frozen=True)
class BlockResult:
    status: str  # WRITTEN | DRY_RUN | ALREADY | CAP_REACHED | REFUSED_*
    token: str | None = None


class Blocklist:
    def __init__(self, path: Path, *, apply: bool = False, max_managed: int = 20,
                 normal_user_agents=(), never_block=()):
        self.path, self.apply, self.max_managed = Path(path), apply, max_managed
        self.normal_user_agents, self.never_block = tuple(normal_user_agents), tuple(never_block)

    def block(self, user_agent: str, *, score: float, now: datetime | None = None) -> BlockResult:
        token = candidate_token(user_agent)
        refusal = check_token(token, self.normal_user_agents, self.never_block)
        if refusal:
            return BlockResult(refusal, token)
        lines = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        entries = {line.split("#", 1)[0].strip().lower() for line in lines}
        if f"ua:{token}".lower() in entries:
            return BlockResult("ALREADY", token)
        if sum(MANAGED_MARK in line for line in lines) >= self.max_managed:
            return BlockResult("CAP_REACHED", token)
        if not self.apply:
            return BlockResult("DRY_RUN", token)
        stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f"ua:{token}  {MANAGED_MARK} {stamp} score={score:.3f}")
        self._atomic_write("\n".join(lines) + "\n")
        return BlockResult("WRITTEN", token)

    def _atomic_write(self, content: str) -> None:
        directory = self.path.parent
        mode = stat.S_IMODE(self.path.stat().st_mode) if self.path.exists() else 0o644
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".blocklist-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, mode)  # mkstemp crée en 0600 : le conteneur WAF (non-root) doit pouvoir lire
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
