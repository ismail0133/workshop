"""API REST de l'assistant : /api/assistant/chat et /api/assistant/health (rôle OPERATOR)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from uuid import UUID, uuid4

import httpx
import jwt
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException

from .chain import RagChain
from .config import Settings
from .index import IndexUnavailable, LoadedIndex, load_index
from .retriever import FaissRetriever

SERVICE = "rag-service"
log = logging.getLogger(SERVICE)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank")
        return value.strip()


class _Json(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            payload = json.loads(record.getMessage())
        except ValueError:
            payload = {"event_type": "LOG", "message": record.getMessage()}
        payload.update(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            service=SERVICE,
        )
        return json.dumps(payload)


def _configure_logging(settings: Settings) -> None:
    log.setLevel(logging.INFO)
    log.propagate = False
    if log.handlers:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_dir:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                settings.log_dir / "events.jsonl", maxBytes=10 * 1024 * 1024, backupCount=4
            )
        )
    for handler in handlers:
        handler.setFormatter(_Json())
        log.addHandler(handler)


def default_ollama_check(settings: Settings) -> bool:
    """Ollama joignable ET les deux modèles requis sont présents."""
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2.0)
        response.raise_for_status()
        names = {m.get("name", "") for m in response.json().get("models", [])}
    except (httpx.HTTPError, ValueError):
        return False
    return all(
        any(
            n == want or n.startswith(want + ":") or n == want.split(":")[0] + ":latest"
            for n in names
        )
        for want in (settings.chat_model, settings.embed_model)
    )


def create_app(
    settings: Settings | None = None,
    *,
    embeddings: Embeddings | None = None,
    llm: BaseChatModel | None = None,
    ollama_check=None,
) -> FastAPI:
    """Les paramètres `embeddings`/`llm`/`ollama_check` permettent de tester sans Ollama."""
    settings = settings or Settings.load()
    _configure_logging(settings)
    registry = CollectorRegistry()
    http_total = Counter(
        "http_requests_total",
        "Completed requests",
        ["service", "route", "method", "status_class", "traffic"],
        registry=registry,
    )
    http_seconds = Histogram(
        "http_request_duration_seconds",
        "Request duration",
        ["service", "route", "method", "traffic"],
        registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
    )
    outcomes = Counter("rag_requests_total", "Chat outcomes", ["outcome"], registry=registry)
    for outcome in ("answered", "abstained", "busy", "timeout", "unavailable"):
        outcomes.labels(outcome).inc(0)
    injections = Counter(
        "rag_injection_suspected_total", "Questions ressemblant à une injection", registry=registry
    )
    generation = Histogram(
        "rag_generation_seconds",
        "Durée retrieval+génération",
        registry=registry,
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
    )
    ready_gauge = Gauge("rag_ready", "1 si index et Ollama sont prêts", registry=registry)
    busy = threading.Lock()  # une seule génération simultanée (RAM, RAG_DESIGN)
    check = ollama_check or (lambda: default_ollama_check(settings))

    state: dict = {
        "index": None,
        "chain": None,
        "error": "INDEX_MISSING",
        "public_key": None,
        "ready_at": 0.0,
        "ready": False,
    }

    def make_models():
        if embeddings is not None and llm is not None:
            return embeddings, llm
        from langchain_ollama import (  # import tardif : absent des tests
            ChatOllama,
            OllamaEmbeddings,
        )

        return (
            embeddings
            or OllamaEmbeddings(
                model=settings.embed_model,
                base_url=settings.ollama_url,
                client_kwargs={"timeout": 10},
            ),
            llm
            or ChatOllama(
                model=settings.chat_model,
                base_url=settings.ollama_url,
                temperature=settings.temperature,
                num_ctx=settings.num_ctx,
                num_predict=settings.num_predict,
                keep_alive="10m",
                client_kwargs={"timeout": settings.timeout_seconds},
            ),
        )

    def load_state() -> None:
        if settings.jwt_public_key_file and settings.jwt_public_key_file.is_file():
            state["public_key"] = settings.jwt_public_key_file.read_text()
        try:
            index: LoadedIndex = load_index(settings.index_dir, settings.embed_model)
        except (IndexUnavailable, OSError, ValueError, KeyError) as exc:
            state["error"] = str(exc) or "INDEX_UNAVAILABLE"
            log.error(json.dumps({"event_type": "INDEX_NOT_LOADED", "reason": state["error"]}))
            return
        emb, chat = make_models()
        state.update(
            index=index,
            error="",
            chain=RagChain(
                FaissRetriever(
                    index=index, embeddings=emb, k=settings.top_k, min_score=settings.min_score
                ),
                chat,
            ),
        )

    def is_ready() -> bool:
        if state["index"] is None or state["public_key"] is None:
            return False
        if time.monotonic() - state["ready_at"] > 5:  # évite de marteler Ollama
            state["ready"], state["ready_at"] = bool(check()), time.monotonic()
            ready_gauge.set(1 if state["ready"] else 0)
        return state["ready"]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_state()
        yield

    app = FastAPI(
        title=SERVICE,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.rag = state

    # ---- erreurs au format commun {code, message, request_id} -----------------------------
    def err(
        request: Request, status: int, code: str, message: str, retry_after: int | None = None
    ) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=status,
            headers=headers,
            content={"code": code, "message": message, "request_id": request.state.request_id},
        )

    @app.exception_handler(ApiError)
    async def _api(request, exc):
        return err(request, exc.status, exc.code, exc.message, exc.retry_after)

    @app.exception_handler(RequestValidationError)
    async def _val(request, exc):
        return err(request, 422, "VALIDATION_ERROR", "Requête invalide")  # n'écho pas le contenu

    @app.exception_handler(HTTPException)
    async def _http(request, exc):
        return err(request, exc.status_code, "HTTP_ERROR", "Requête non disponible")

    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        request.state.request_id = str(uuid4())  # jamais un identifiant fourni par le client
        request.state.log = {}
        started = time.perf_counter()
        try:
            length = request.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > 16384):
                response = err(request, 413, "BODY_TOO_LARGE", "Corps trop volumineux")
            else:
                response = await call_next(request)
        except Exception:  # noqa: BLE001 — aucun détail d'exception dans la réponse
            response = err(request, 500, "INTERNAL_ERROR", "Erreur interne")
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        traffic = "business" if route.startswith("/api/") else "health"
        http_total.labels(
            SERVICE, route, request.method, f"{response.status_code // 100}xx", traffic
        ).inc()
        http_seconds.labels(SERVICE, route, request.method, traffic).observe(elapsed)
        response.headers.update(
            {
                "X-Request-ID": request.state.request_id,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            }
        )
        log.info(
            json.dumps(
                {
                    "event_type": "HTTP_REQUEST",
                    "request_id": request.state.request_id,
                    "route": route,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed * 1000, 3),
                    **request.state.log,
                }
            )
        )
        return response

    # ---- authentification : JWT RS256, rôle OPERATOR, aucune lecture de base ------------
    def operator(request: Request) -> UUID:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError(401, "UNAUTHORIZED", "Authentification requise")
        if state["public_key"] is None:
            raise ApiError(503, "AUTH_UNAVAILABLE", "Clé de vérification absente")
        try:
            claims = jwt.decode(
                token,
                state["public_key"],
                algorithms=["RS256"],
                audience=settings.audience,
                issuer=settings.issuer,
                options={"require": ["sub", "role", "exp", "iat", "nbf"]},
            )
            user, role = UUID(claims["sub"]), str(claims["role"])
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            raise ApiError(401, "UNAUTHORIZED", "Jeton invalide ou expiré") from None
        if role not in settings.roles:
            raise ApiError(403, "FORBIDDEN", "Rôle opérateur requis")
        return user

    # ---- routes -------------------------------------------------------------------------
    @app.post("/api/assistant/chat")
    async def chat(request: Request, body: ChatRequest, user: UUID = Depends(operator)):
        if state["index"] is None:
            outcomes.labels("unavailable").inc()
            raise ApiError(503, "INDEX_UNAVAILABLE", "Index documentaire indisponible")
        if not busy.acquire(blocking=False):
            outcomes.labels("busy").inc()
            raise ApiError(429, "ASSISTANT_BUSY", "Une génération est déjà en cours", retry_after=5)
        chain: RagChain = state["chain"]
        started = time.perf_counter()

        def work():
            try:
                return chain.answer(body.message)
            finally:
                busy.release()  # libéré à la fin RÉELLE du travail, même après un 504

        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, work), timeout=settings.timeout_seconds
            )
        except asyncio.TimeoutError:
            outcomes.labels("timeout").inc()
            raise ApiError(504, "GENERATION_TIMEOUT", "Génération trop lente") from None
        except IndexUnavailable:
            outcomes.labels("unavailable").inc()
            raise ApiError(
                503, "INDEX_UNAVAILABLE", "Index incompatible avec le modèle d'embedding"
            ) from None
        except httpx.TimeoutException:
            outcomes.labels("timeout").inc()
            raise ApiError(504, "GENERATION_TIMEOUT", "Génération trop lente") from None
        except Exception:  # noqa: BLE001 — Ollama arrêté, modèle absent, réponse invalide…
            outcomes.labels("unavailable").inc()
            raise ApiError(503, "ASSISTANT_UNAVAILABLE", "Moteur de langage indisponible") from None
        generation.observe(time.perf_counter() - started)
        outcomes.labels("abstained" if result.abstained else "answered").inc()
        if result.injection_suspected:
            injections.inc()
        request.state.log.update(
            user_id=str(user),
            question_len=len(body.message),
            question_sha256=hashlib.sha256(body.message.encode()).hexdigest()[
                :12
            ],  # jamais le texte
            grounded=result.grounded,
            abstained=result.abstained,
            injection_suspected=result.injection_suspected,
            top_score=None if result.top_score is None else round(result.top_score, 4),
            citations=len(result.citations),
        )
        return {
            "answer": result.answer,
            "citations": result.citations,
            "grounded": result.grounded,
            "model": settings.chat_model,
            "index_version": state["index"].version,
            "request_id": request.state.request_id,
        }

    @app.get("/api/assistant/health")
    def assistant_health(request: Request, user: UUID = Depends(operator)):
        if not is_ready():
            raise ApiError(503, "ASSISTANT_UNAVAILABLE", "Index ou Ollama indisponible")
        return {
            "status": "ok",
            "service": SERVICE,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/live")
    def live():
        return {
            "status": "ok",
            "service": SERVICE,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/ready")
    def ready():
        if not is_ready():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "service": SERVICE,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        return {
            "status": "ok",
            "service": SERVICE,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


def app_factory() -> FastAPI:  # uvicorn --factory rag_app.main:app_factory
    return create_app()
