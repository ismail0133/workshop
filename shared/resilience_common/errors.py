from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def error_response(request: Request, status: int, code: str, message: str):
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
    if status == 429:
        headers["Retry-After"] = "60"
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={"code": code, "message": message, "request_id": request.state.request_id},
    )


def register_errors(app):
    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo input/passwords from Pydantic error structures.
        return error_response(request, 422, "VALIDATION_ERROR", "Requête invalide")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(
            request, 503, "DATABASE_UNAVAILABLE", "Base indisponible, réessayer avec la même clé"
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, "HTTP_ERROR", "Requête non disponible")
