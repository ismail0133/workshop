# Contexte de build : racine du dépôt.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY services/rag-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt && pip check \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /var/log/resilience /index && chown app:app /var/log/resilience /index
COPY services/rag-service/rag_app /app/rag_app
COPY services/rag-service/rag_eval /app/rag_eval
USER 10001:10001
EXPOSE 8004
CMD ["uvicorn", "--factory", "rag_app.main:app_factory", "--host", "0.0.0.0", "--port", "8004", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
