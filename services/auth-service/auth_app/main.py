from resilience_common.app import create_app

from .routes import router

app = create_app("auth-service")
app.include_router(router)
