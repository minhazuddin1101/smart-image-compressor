import os
from pathlib import Path
import shutil
import tempfile

import pytest


_test_storage = Path(tempfile.mkdtemp(prefix="sic-test-storage-"))
os.environ["SIC_STORAGE_DIR"] = str(_test_storage)


@pytest.fixture(scope="session", autouse=True)
def remove_test_storage():
    yield
    shutil.rmtree(_test_storage, ignore_errors=True)
