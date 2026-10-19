from resilience_common.app import create_app

from .routes import router

app = create_app("payment-api")
app.include_router(router)
