import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import PROJECT_ROOT, settings


app = FastAPI(title="Smart Image Compressor", docs_url=None, redoc_url=None)
logger = logging.getLogger(__name__)
app.state.processing_slots = asyncio.Semaphore(2)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
app.include_router(router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    request_too_large = content_length and content_length.isdecimal() and int(content_length) > (
        settings.max_upload_bytes * settings.max_batch_files + 1024 * 1024
    )
    if request_too_large:
        response = JSONResponse(status_code=413, content={"detail": "The request exceeds the upload limit."})
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(Path(PROJECT_ROOT / "app" / "templates" / "index.html"))


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "The request could not be completed."})
