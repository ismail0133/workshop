FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/shared:/app
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --requirement requirements.lock && pip check     && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app     && mkdir -p /var/log/resilience && chown app:app /var/log/resilience
COPY shared /app/shared

FROM base AS auth
COPY services/auth-service/auth_app /app/auth_app
USER 10001:10001
EXPOSE 8001
CMD ["uvicorn", "auth_app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-access-log", "--no-proxy-headers"]

FROM base AS payment
COPY services/payment-api/payment_app /app/payment_app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "payment_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]

FROM base AS tools
COPY database /app/database
COPY alembic.ini pyproject.toml /app/
COPY scripts /app/scripts
COPY tests /app/tests
COPY services/auth-service/auth_app /app/auth_app
COPY services/payment-api/payment_app /app/payment_app
CMD ["python", "--version"]
