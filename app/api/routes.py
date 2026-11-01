import asyncio
from pathlib import Path
import tempfile
import zipfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.api.schemas import CompressResponse, CompressResult, SessionRequest, ZipRequest
from app.core.config import settings
from app.core.security import safe_stem, valid_result_id, valid_session_id
from app.services.file_manager import StoredResult, result_store
from app.services.image_processor import ImageProcessingError, compress_image
from app.services.image_validator import ImageValidationError, validate_image


router = APIRouter(prefix="/api")
SUPPORTED_FORMATS = ("jpeg", "png", "webp")


async def _read_upload(upload: UploadFile) -> bytes:
    data = bytearray()
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > settings.max_upload_bytes:
            raise ImageValidationError("The image exceeds the 10 MB upload limit.")
    return bytes(data)


def _result_response(result: StoredResult) -> CompressResult:
    saved_bytes = result.original_size - result.output_size
    saved_percentage = (saved_bytes / result.original_size) * 100
    return CompressResult(
        id=result.id,
        session_id=result.session_id,
        original_name=result.original_name,
        output_name=result.output_name,
        original_size=result.original_size,
        output_size=result.output_size,
        original_width=result.original_width,
        original_height=result.original_height,
        output_width=result.output_width,
        output_height=result.output_height,
        output_format=result.output_format,
        saved_bytes=saved_bytes,
        saved_percentage=round(saved_percentage, 2),
        output_larger=saved_bytes < 0,
        download_url=f"/api/download/{result.id}",
        preview_url=f"/api/results/{result.id}/preview",
    )


def _release_downloads(result_ids: list[str], zip_path: Path) -> None:
    for result_id in result_ids:
        result_store.finish_download(result_id)
    zip_path.unlink(missing_ok=True)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config")
async def get_config() -> dict[str, object]:
    return {
        "max_upload_bytes": settings.max_upload_bytes,
        "max_upload_mb": round(settings.max_upload_bytes / (1024 * 1024), 1),
        "max_batch_files": settings.max_batch_files,
        "max_image_dimension": settings.max_image_dimension,
        "supported_input_formats": ["jpeg", "png", "webp"],
        "supported_output_formats": list(SUPPORTED_FORMATS),
        "quality": {"minimum": 10, "maximum": 100, "default": 80},
    }


@router.post("/compress", response_model=CompressResponse)
async def compress(
    request: Request,
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(default=None),
    output_format: str = Form(default="webp"),
    quality: int = Form(default=80),
    resize_mode: str = Form(default="original"),
    width: int | None = Form(default=None),
    height: int | None = Form(default=None),
    allow_enlarge: bool = Form(default=False),
    webp_lossless: bool = Form(default=False),
) -> CompressResponse | JSONResponse:
    result_store.cleanup_expired()
    if not files:
        raise HTTPException(status_code=422, detail="Choose at least one image.")
    if len(files) > settings.max_batch_files:
        raise HTTPException(status_code=413, detail=f"Upload no more than {settings.max_batch_files} images at a time.")
    if output_format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=422, detail="Choose JPEG, PNG, or WebP as the output format.")
    if not 10 <= quality <= 100:
        raise HTTPException(status_code=422, detail="Quality must be between 10 and 100.")
    if session_id is None:
        session_id = result_store.new_id()
    elif not valid_session_id(session_id):
        raise HTTPException(status_code=422, detail="The session identifier is invalid.")

    completed: list[StoredResult] = []
    errors: list[dict[str, str]] = []
    for upload in files:
        source_name = safe_stem(upload.filename or "image")
        try:
            data = await _read_upload(upload)
            input_format, original_width, original_height = validate_image(
                data, upload.filename or "", upload.content_type
            )
            async with request.app.state.processing_slots:
                output_data, output_width, output_height = await run_in_threadpool(
                    compress_image,
                    data,
                    output_format,
                    quality,
                    resize_mode,
                    width,
                    height,
                    allow_enlarge,
                    webp_lossless,
                )
            result_id = result_store.new_id()
            extension = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}[output_format]
            output_name = f"{source_name}_optimized_{result_id[:6]}{extension}"
            output_path = result_store.result_path(result_id, output_name)
            try:
                await run_in_threadpool(output_path.write_bytes, output_data)
            except OSError:
                result_store._remove_path(output_path)
                raise
            safe_original_name = (upload.filename or "image").replace("\\", "/").rsplit("/", 1)[-1][:120]
            result = StoredResult(
                id=result_id,
                session_id=session_id,
                output_path=output_path,
                output_name=output_name,
                original_name=safe_original_name or f"image.{input_format}",
                original_size=len(data),
                output_size=len(output_data),
                original_width=original_width,
                original_height=original_height,
                output_width=output_width,
                output_height=output_height,
                output_format=output_format,
            )
            result_store.add(result)
            completed.append(result)
        except (ImageValidationError, ImageProcessingError) as exc:
            errors.append({"filename": source_name, "message": str(exc)})
        finally:
            await upload.close()

    if not completed:
        return JSONResponse(status_code=422, content={"results": [], "errors": errors})
    return CompressResponse(results=[_result_response(item) for item in completed], errors=errors)


@router.get("/results/{result_id}")
async def get_result(result_id: str) -> CompressResult:
    if not valid_result_id(result_id):
        raise HTTPException(status_code=404, detail="Result not found.")
    result = result_store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return _result_response(result)


@router.get("/results/{result_id}/preview")
async def preview_result(result_id: str) -> FileResponse:
    if not valid_result_id(result_id):
        raise HTTPException(status_code=404, detail="Result not found.")
    result = result_store.begin_download(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return FileResponse(
        result.output_path,
        media_type=f"image/{'jpeg' if result.output_format == 'jpeg' else result.output_format}",
        filename=result.output_name,
        content_disposition_type="inline",
        background=BackgroundTask(result_store.finish_download, result_id),
    )


@router.get("/download/{result_id}")
async def download_result(result_id: str) -> FileResponse:
    if not valid_result_id(result_id):
        raise HTTPException(status_code=404, detail="Result not found.")
    result = result_store.begin_download(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return FileResponse(
        result.output_path,
        media_type=f"image/{'jpeg' if result.output_format == 'jpeg' else result.output_format}",
        filename=result.output_name,
        background=BackgroundTask(result_store.finish_download, result_id),
    )


@router.post("/download-zip")
async def download_zip(payload: ZipRequest) -> FileResponse:
    result_store.cleanup_expired()
    if not valid_session_id(payload.session_id) or any(
        not valid_result_id(result_id) for result_id in payload.result_ids
    ):
        raise HTTPException(status_code=422, detail="The session or result identifiers are invalid.")
    if len(set(payload.result_ids)) != len(payload.result_ids):
        raise HTTPException(status_code=422, detail="A result may only appear once in the ZIP.")

    results: list[StoredResult] = []
    for result_id in payload.result_ids:
        result = result_store.begin_download(result_id)
        if result is None or result.session_id != payload.session_id:
            if result is not None:
                result_store.finish_download(result_id)
            for acquired in results:
                result_store.finish_download(acquired.id)
            raise HTTPException(status_code=404, detail="One or more results were not found.")
        results.append(result)

    temp_handle = tempfile.NamedTemporaryFile(
        prefix="sic-", suffix=".zip", dir=settings.temp_dir, delete=False
    )
    zip_path = Path(temp_handle.name)
    temp_handle.close()
    try:
        def create_archive() -> None:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
                for result in results:
                    archive.write(result.output_path, arcname=result.output_name)

        await run_in_threadpool(create_archive)
    except Exception:
        _release_downloads([item.id for item in results], zip_path)
        raise

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="smart-image-compressor.zip",
        background=BackgroundTask(_release_downloads, [item.id for item in results], zip_path),
    )


@router.delete("/results/{result_id}")
async def delete_result(result_id: str) -> dict[str, str]:
    if not valid_result_id(result_id) or not result_store.delete(result_id):
        raise HTTPException(status_code=404, detail="Result not found.")
    return {"status": "deleted"}


@router.delete("/session")
async def delete_session(payload: SessionRequest) -> dict[str, int]:
    if not valid_session_id(payload.session_id):
        raise HTTPException(status_code=422, detail="The session identifier is invalid.")
    return {"deleted": result_store.delete_session(payload.session_id)}
