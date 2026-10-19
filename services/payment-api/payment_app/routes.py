from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from resilience_common.app import health
from resilience_common.pagination import Cursor
from resilience_common.schemas import AccountView, Health, Page, PaymentRequest, PaymentView
from resilience_common.security import Principal, banking_user

from . import repository
from .service import transfer

router = APIRouter()
Limit = Annotated[int, Query(ge=1, le=100)]
CursorParam = Annotated[str | None, Query(max_length=512)]


@router.get("/api/accounts", response_model=Page[AccountView])
def list_accounts(
    request: Request,
    principal: Principal = Depends(banking_user),
    limit: Limit = 20,
    cursor: CursorParam = None,
):
    codec = Cursor(request.app.state.settings.cursor_key)
    scope = f"accounts:{principal.id}"
    with request.app.state.sessions() as session:
        rows = repository.accounts(session, principal, limit, codec.decode(cursor, scope))
        return Page[AccountView](
            items=[AccountView.model_validate(a) for a in rows[:limit]],
            next_cursor=codec.encode(scope, [str(rows[limit - 1].id)])
            if len(rows) > limit
            else None,
        )


@router.get("/api/accounts/{id}", response_model=AccountView)
def get_account(id: UUID, request: Request, principal: Principal = Depends(banking_user)):
    with request.app.state.sessions() as session:
        return AccountView.model_validate(repository.account(session, principal, id))


@router.post(
    "/api/payments",
    response_model=PaymentView,
    status_code=201,
    responses={
        200: {"model": PaymentView},
        409: {"description": "Rejected payment or idempotency conflict"},
    },
)
def make_payment(
    body: PaymentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
    principal: Principal = Depends(banking_user),
):
    try:
        with request.app.state.sessions() as session:
            result, code = transfer(session, principal, body, idempotency_key)
    except Exception:
        request.app.state.payment_attempts.labels("failure").inc()
        raise
    request.app.state.payment_attempts.labels(
        "success" if result.status == "SUCCESS" else "failure"
    ).inc()
    response.status_code = code
    return result


@router.get("/api/payments", response_model=Page[PaymentView])
def list_payments(
    request: Request,
    principal: Principal = Depends(banking_user),
    limit: Limit = 20,
    cursor: CursorParam = None,
):
    codec = Cursor(request.app.state.settings.cursor_key)
    scope = f"payments:{principal.id}"
    with request.app.state.sessions() as session:
        rows = repository.payments(session, principal, limit, codec.decode(cursor, scope))
        return Page[PaymentView](
            items=[PaymentView.model_validate(t) for t in rows[:limit]],
            next_cursor=codec.encode(
                scope, [rows[limit - 1].created_at.isoformat(), str(rows[limit - 1].id)]
            )
            if len(rows) > limit
            else None,
        )


@router.get("/api/payments/{id}", response_model=PaymentView)
def get_payment(id: UUID, request: Request, principal: Principal = Depends(banking_user)):
    with request.app.state.sessions() as session:
        return PaymentView.model_validate(repository.payment(session, principal, id))


@router.get("/health/live", response_model=Health)
def live(request: Request):
    return health(request)


@router.get("/health/ready", response_model=Health)
def ready(request: Request):
    return health(request, ready=True)
