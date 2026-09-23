"""
Main FastAPI application entry point.

Creates the HTTP application, configures local-development CORS, and
registers the API routers.
"""

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.core.config import settings
from app.api.rag import router as rag_router
from app.api.conversations import router as conversations_router
from app.api.auth import router as auth_router
from app.api.tickets import router as tickets_router
from app.database.session import engine
from app.observability.setup import configure_observability
from app.health import database_is_ready


settings.validate_backend_http_runtime()


app = FastAPI(
    title=settings.app_name,
    description="A portfolio project for Agentic AI, RAG, FastAPI, Docker, and CI/CD.",
    version=settings.app_version,
)

# Browser origins are environment-configurable. Local defaults cover Vite;
# the R3 deployment workflow sets the deployed frontend origin explicitly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


configure_observability(app=app, engine=engine)

app.include_router(chat_router)

app.include_router(rag_router)

app.include_router(conversations_router)

app.include_router(auth_router)

app.include_router(tickets_router)


@app.get("/")
def root():
    """
    Basic endpoint.

    Used to check if the API is running.
    """
    return {"message": "Enterprise AI Assistant API is running"}


@app.get("/health")
def health():
    """Return process liveness without probing external dependencies."""

    return {"status": "ok"}


@app.get("/ready")
def readiness(response: Response):
    """Return whether the critical PostgreSQL dependency is available."""

    if not database_is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}

    return {"status": "ready"}
