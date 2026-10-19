from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .errors import APIError
from .models import User
from .schemas import Role

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: UUID
    role: Role


def issue_token(user: User, settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.issuer,
            "aud": settings.audience,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=settings.token_seconds),
            "jti": str(uuid4()),
        },
        settings.private_key,
        algorithm="RS256",
    )


def current_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(401, "UNAUTHORIZED", "Authentification requise")
    settings = request.app.state.settings
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.public_key,
            algorithms=["RS256"],
            audience=settings.audience,
            issuer=settings.issuer,
            options={"require": ["sub", "role", "exp", "iat", "nbf", "jti"]},
        )
        user_id, role = UUID(payload["sub"]), Role(payload["role"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise APIError(401, "UNAUTHORIZED", "Jeton invalide ou expiré") from None
    # Read only permitted columns; bank role cannot read password hashes.
    with request.app.state.engine.connect() as conn:
        row = conn.execute(
            select(User.id, User.role, User.is_active).where(User.id == user_id)
        ).first()
    if row is None or not row.is_active or row.role != role:
        raise APIError(401, "UNAUTHORIZED", "Identité inactive ou droits modifiés")
    return Principal(user_id, role)


def banking_user(principal: Principal = Depends(current_user)) -> Principal:
    if principal.role not in (Role.USER, Role.VALIDATOR):
        raise APIError(403, "FORBIDDEN", "Rôle bancaire requis")
    return principal
