import re
import unicodedata
from pathlib import PurePosixPath


_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")


def valid_session_id(value: str) -> bool:
    return bool(_SESSION_ID.fullmatch(value))


def safe_stem(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = PurePosixPath(basename).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    cleaned = _SAFE_STEM.sub("_", stem).strip("._-")[:70]
    return cleaned or "image"


def valid_result_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,64}", value))
