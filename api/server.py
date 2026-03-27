from fastapi import FastAPI # pyre-ignore[21]
from fastapi.middleware.cors import CORSMiddleware  # pyre-ignore[21]
from .config import settings    # pyre-ignore[21]
from .routes import auth, health, actions   # pyre-ignore[21]
from .database import init_db   # pyre-ignore[21]
import uvicorn  # pyre-ignore[21]
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    print("API Server: Database initialized.")
    yield
    # Shutdown
    print("API Server: Shutting down.")

app = FastAPI(
    title="JARVIS API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, prefix="/api/v1", tags=["system"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(actions.router, prefix="/api/v1/actions", tags=["actions"])

if __name__ == "__main__":
    uvicorn.run("api.server:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
