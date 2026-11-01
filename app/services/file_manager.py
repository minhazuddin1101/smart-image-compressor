from dataclasses import dataclass, field
from pathlib import Path
import secrets
import shutil
import threading
import time

from app.core.config import settings


@dataclass
class StoredResult:
    id: str
    session_id: str
    output_path: Path
    output_name: str
    original_name: str
    original_size: int
    output_size: int
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    output_format: str
    created_at: float = field(default_factory=time.time)


class ResultStore:
    def __init__(self) -> None:
        for directory in (settings.uploads_dir, settings.processed_dir, settings.temp_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._results: dict[str, StoredResult] = {}
        self._active_downloads: dict[str, int] = {}
        self._pending_deletions: dict[str, Path] = {}
        self._lock = threading.RLock()
        self.cleanup_orphaned_files()

    @staticmethod
    def new_id() -> str:
        return secrets.token_urlsafe(24)

    def result_path(self, result_id: str, filename: str) -> Path:
        directory = settings.processed_dir / result_id
        directory.mkdir(parents=True, exist_ok=False)
        return directory / filename

    def add(self, result: StoredResult) -> None:
        with self._lock:
            self._results[result.id] = result

    def get(self, result_id: str, session_id: str | None = None) -> StoredResult | None:
        self.cleanup_expired()
        with self._lock:
            result = self._results.get(result_id)
            if result is None or (session_id is not None and result.session_id != session_id):
                return None
            return result

    def begin_download(self, result_id: str) -> StoredResult | None:
        self.cleanup_expired()
        with self._lock:
            result = self._results.get(result_id)
            if result is None:
                return None
            self._active_downloads[result_id] = self._active_downloads.get(result_id, 0) + 1
            return result

    def finish_download(self, result_id: str) -> None:
        with self._lock:
            active = self._active_downloads.get(result_id, 0) - 1
            if active > 0:
                self._active_downloads[result_id] = active
                return
            self._active_downloads.pop(result_id, None)
            pending = self._pending_deletions.pop(result_id, None)
            if pending is not None:
                self._remove_path(pending)

    def delete(self, result_id: str) -> bool:
        with self._lock:
            result = self._results.pop(result_id, None)
            if result is None:
                return False
            if self._active_downloads.get(result_id, 0):
                self._pending_deletions[result_id] = result.output_path
            else:
                self._remove_path(result.output_path)
            return True

    def delete_session(self, session_id: str) -> int:
        with self._lock:
            result_ids = [key for key, result in self._results.items() if result.session_id == session_id]
            for result_id in result_ids:
                self.delete(result_id)
            return len(result_ids)

    def cleanup_expired(self) -> int:
        cutoff = time.time() - settings.result_ttl_seconds
        with self._lock:
            expired = [key for key, result in self._results.items() if result.created_at < cutoff]
            for result_id in expired:
                self.delete(result_id)
            return len(expired)

    @staticmethod
    def _remove_path(path: Path) -> None:
        try:
            resolved = path.resolve()
            if resolved.parent == settings.processed_dir.resolve():
                shutil.rmtree(resolved, ignore_errors=False)
            elif resolved.parent.parent == settings.processed_dir.resolve():
                resolved.unlink(missing_ok=True)
                resolved.parent.rmdir()
        except FileNotFoundError:
            pass

    @staticmethod
    def cleanup_orphaned_files() -> None:
        cutoff = time.time() - settings.result_ttl_seconds
        for directory in settings.processed_dir.iterdir():
            if directory.is_dir() and directory.stat().st_mtime < cutoff:
                shutil.rmtree(directory, ignore_errors=True)
        for path in settings.temp_dir.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)


result_store = ResultStore()
