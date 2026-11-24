import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .adapters import registry
from .config import get_settings
from .db import init_db
from .pipelines import runner
from .routers import assets, auth, library, misc, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _warm_models():
    try:
        ie = registry.image_embedder()
        if ie:
            ie.embed_text(["warm up"])
            logging.getLogger("smriti").info("image model ready: %s", ie.name)
    except Exception as e:  # noqa: BLE001 - missing optional packages: search falls back to text and tags
        logging.getLogger("smriti").warning("image model unavailable: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Load the image model in the background: it takes ~45 s, and otherwise the first search or upload would wait for it.
    threading.Thread(target=_warm_models, name="warm-models", daemon=True).start()
    n = runner.resume_pending()
    if n:
        logging.getLogger("smriti").info("resumed %s pending assets", n)
    yield


app = FastAPI(title="Smriti API", version="1.0.0", lifespan=lifespan,
              description="Memory & document search backend. Interactive docs at /docs.")
_origins = get_settings().origins
# Auth uses bearer tokens (no cookies), so "*" is safe when set explicitly.
app.add_middleware(CORSMiddleware, allow_origins=["*"] if "*" in _origins else _origins, allow_credentials="*" not in _origins,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, assets.router, search.router, library.router, misc.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok", "adapters": registry.describe_adapters()}
