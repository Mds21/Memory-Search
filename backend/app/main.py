import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .adapters import registry
from .config import get_settings
from .db import init_db
from .pipelines import runner
from .routers import assets, auth, library, misc, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    n = runner.resume_pending()
    if n:
        logging.getLogger("smriti").info("resumed %s pending assets", n)
    yield


app = FastAPI(title="Smriti API", version="1.0.0", lifespan=lifespan,
              description="Memory & document search backend. Interactive docs at /docs.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, assets.router, search.router, library.router, misc.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok", "adapters": registry.describe_adapters()}
