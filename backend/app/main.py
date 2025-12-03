from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, init_db
from app.api import cameras, settings as settings_api, events, recordings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - import models before init
    from app import models  # noqa
    await init_db()
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(title="Motion Watch API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(cameras.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(recordings.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "Motion Watch API"}
