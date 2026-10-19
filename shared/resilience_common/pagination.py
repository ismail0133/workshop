import base64
import hashlib
import hmac
import json

from .errors import APIError


class Cursor:
    def __init__(self, key: str):
        self.key = key.encode()

    def encode(self, scope: str, after: list[str]) -> str:
        body = json.dumps({"scope": scope, "after": after}, separators=(",", ":")).encode()
        tag = hmac.new(self.key, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body + tag).decode()

    def decode(self, value: str | None, scope: str) -> list[str] | None:
        if value is None:
            return None
        try:
            raw = base64.b64decode(value, altchars=b"-_", validate=True)
            body, tag = raw[:-32], raw[-32:]
            if not hmac.compare_digest(tag, hmac.new(self.key, body, hashlib.sha256).digest()):
                raise ValueError
            data = json.loads(body)
            if data["scope"] != scope or not isinstance(data["after"], list):
                raise ValueError
            return data["after"]
        except (ValueError, KeyError, TypeError):
            raise APIError(422, "INVALID_CURSOR", "Curseur invalide") from None
