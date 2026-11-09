import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_engine, get_db
from app.db.base import Base
import app.models  # Ensure all SQLAlchemy models are registered
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context:
    - Auto-creates tables if running in development / test mode
    - Verifies DB connectivity
    """
    try:
        async with async_engine.begin() as conn:
            # Create tables if not existing
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        print(f"Warning: Could not auto-create tables on startup (normal if migrations run separately): {exc}")
    yield
    # Cleanup connection pool
    await async_engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Operational Task & Delegation Hub with Real-Time Read Receipts and Leader Verification Loops",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Static files setup
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/healthz", tags=["Health"], status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Standard health check endpoint for Render/Kubernetes probes.
    Verifies database connectivity and app readiness.
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "status": "ok" if "healthy" in db_status else "degraded",
        "service": settings.PROJECT_NAME,
        "database": db_status,
        "environment": settings.ENVIRONMENT
    }


@app.get("/", include_in_schema=False)
async def root():
    """
    Serves the executive web dashboard.
    """
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": f"Welcome to {settings.PROJECT_NAME} API. Visit /docs for OpenAPI specifications."}
