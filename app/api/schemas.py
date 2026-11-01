from typing import Literal

from pydantic import BaseModel, Field


class CompressResult(BaseModel):
    id: str
    session_id: str
    original_name: str
    output_name: str
    original_size: int
    output_size: int
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    output_format: Literal["jpeg", "png", "webp"]
    saved_bytes: int
    saved_percentage: float
    output_larger: bool
    download_url: str
    preview_url: str


class CompressResponse(BaseModel):
    results: list[CompressResult]
    errors: list[dict[str, str]] = Field(default_factory=list)


class ZipRequest(BaseModel):
    session_id: str
    result_ids: list[str] = Field(min_length=1, max_length=10)


class SessionRequest(BaseModel):
    session_id: str
