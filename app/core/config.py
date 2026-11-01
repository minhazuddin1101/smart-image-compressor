import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    max_upload_bytes: int = _positive_int("SIC_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    max_batch_files: int = _positive_int("SIC_MAX_BATCH_FILES", 10)
    max_image_pixels: int = _positive_int("SIC_MAX_IMAGE_PIXELS", 40_000_000)
    max_image_dimension: int = _positive_int("SIC_MAX_IMAGE_DIMENSION", 12_000)
    result_ttl_seconds: int = _positive_int("SIC_RESULT_TTL_SECONDS", 24 * 60 * 60)
    storage_root: Path = Path(os.getenv("SIC_STORAGE_DIR", str(PROJECT_ROOT / "storage"))).resolve()

    @property
    def uploads_dir(self) -> Path:
        return self.storage_root / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.storage_root / "processed"

    @property
    def temp_dir(self) -> Path:
        return self.storage_root / "temp"


settings = Settings()
