from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from resilience_common.errors import APIError
from resilience_common.schemas import LoginResponse, UserView
from resilience_common.security import issue_token

from .repository import find_by_email

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
# An absent account still incurs password verification; this is not a credential.
DUMMY_HASH = hasher.hash("non-authenticating-timing-placeholder")


def login(session, body, settings) -> LoginResponse:
    user = find_by_email(session, body.email)
    encoded = user.password_hash if user else DUMMY_HASH
    try:
        valid = hasher.verify(encoded, body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid or user is None or not user.is_active:
        raise APIError(401, "INVALID_CREDENTIALS", "Identifiants invalides")
    return LoginResponse(
        access_token=issue_token(user, settings), user=UserView.model_validate(user)
    )
