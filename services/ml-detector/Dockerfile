# Contexte de build : racine du dépôt (docker compose -f docker-compose.yml -f docker-compose.ai.yml build ml-detector)
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY services/ml-detector/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt && pip check \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /var/log/resilience /var/lib/ml /models /data && chown app:app /var/log/resilience /var/lib/ml /models /data
COPY services/ml-detector/ml_app /app/ml_app
USER 10001:10001
EXPOSE 8003
CMD ["uvicorn", "--factory", "ml_app.main:app_factory", "--host", "0.0.0.0", "--port", "8003", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
