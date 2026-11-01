import shutil
import time
from urllib.error import URLError
from urllib.request import urlopen

from app.core.config import settings


def cleanup_expired_storage() -> int:
    try:
        with urlopen("http://127.0.0.1:8000/api/health", timeout=1) as response:
            if response.status == 200:
                raise RuntimeError("Stop the running application before manual cleanup.")
    except URLError:
        pass

    cutoff = time.time() - settings.result_ttl_seconds
    removed = 0
    for path in settings.processed_dir.iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path)
            removed += 1
    for path in settings.temp_dir.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


if __name__ == "__main__":
    count = cleanup_expired_storage()
    print(f"Removed {count} expired item(s).")
