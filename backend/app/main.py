import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
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
origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
] if settings.CORS_ORIGINS and settings.CORS_ORIGINS != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


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


@app.get("/", tags=["Root"])
async def root():
    """
    API Service Root: Provides endpoint discovery and API health info.
    """
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": f"{settings.API_V1_STR}/openapi.json",
        "health": "/healthz"
    }

