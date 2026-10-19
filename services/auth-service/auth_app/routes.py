from fastapi import APIRouter, Depends, Request
from resilience_common.app import health
from resilience_common.models import User
from resilience_common.schemas import Health, LoginRequest, LoginResponse, UserView
from resilience_common.security import Principal, current_user

from .service import login

router = APIRouter()


@router.post("/api/auth/login", response_model=LoginResponse)
def login_route(body: LoginRequest, request: Request):
    request.app.state.limiter.check(request.client.host if request.client else "unknown")
    with request.app.state.sessions() as session:
        return login(session, body, request.app.state.settings)


@router.get("/api/auth/me", response_model=UserView)
def me(request: Request, principal: Principal = Depends(current_user)):
    with request.app.state.sessions() as session:
        return UserView.model_validate(session.get(User, principal.id))


@router.get("/health", response_model=Health)
def auth_health(request: Request):
    return health(request, ready=True)
