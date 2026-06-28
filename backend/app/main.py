import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import admin, assets, auth, catalog, internal, leads, platform, projects
from app.config import settings
from app.database import async_engine
from app.models import Base

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_starting", env=settings.app_env)
    yield
    await async_engine.dispose()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AI Wall Visualizer", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(platform.router, prefix="/api")
app.include_router(internal.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(assets.router, prefix="/api")


from app.services.queue_monitor import queue_snapshot


@app.get("/health")
async def health():
    snap = queue_snapshot()
    return {
        "status": "ok",
        "queue": snap,
    }
