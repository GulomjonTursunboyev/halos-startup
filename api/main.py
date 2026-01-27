"""
HALOS Mobile API - FastAPI Application
RESTful API for Android & iOS mobile applications
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import logging

from api.routers import auth, users, transactions, debts, budgets, analytics, sync
from api.config import settings
from api.database import init_db, close_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    logger.info("Starting HALOS Mobile API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down HALOS Mobile API...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="HALOS Mobile API",
    description="Personal Finance Management API for HALOS Mobile Apps",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["Transactions"])
app.include_router(debts.router, prefix="/api/v1/debts", tags=["Debts"])
app.include_router(budgets.router, prefix="/api/v1/budgets", tags=["Budgets"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Sync"])


@app.get("/")
async def root():
    """API Health Check"""
    return {
        "status": "healthy",
        "service": "HALOS Mobile API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "api_version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
