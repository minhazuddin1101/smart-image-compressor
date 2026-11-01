from io import BytesIO
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.core.config import settings
from app.main import app
from tests.helpers import image_bytes


client = TestClient(app)
SESSION = "test-session-identifier-0001"


def upload(data, filename="photo.png", content_type="image/png", **extra):
    fields = {
        "session_id": SESSION,
        "output_format": "webp",
        "quality": "80",
        "resize_mode": "original",
    }
    fields.update(extra)
    return client.post(
        "/api/compress",
        files={"files": (filename, data, content_type)},
        data=fields,
    )


def test_startup_health_and_home():
    assert client.get("/").status_code == 200
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_has_supported_limits():
    config = client.get("/api/config").json()
    assert config["max_upload_bytes"] == settings.max_upload_bytes
    assert config["max_batch_files"] == 10
    assert config["supported_output_formats"] == ["jpeg", "png", "webp"]


def test_rejects_excessive_content_length():
    maximum = settings.max_upload_bytes * settings.max_batch_files + 1024 * 1024
    response = client.get("/api/config", headers={"content-length": str(maximum + 1)})
    assert response.status_code == 413
    assert response.json()["detail"] == "The request exceeds the upload limit."
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("image_format", "filename", "content_type"),
    [
        ("JPEG", "source.jpg", "image/jpeg"),
        ("PNG", "source.png", "image/png"),
        ("WEBP", "source.webp", "image/webp"),
    ],
)
def test_api_accepts_each_supported_input_format(image_format, filename, content_type):
    response = upload(image_bytes(image_format), filename=filename, content_type=content_type)
    assert response.status_code == 200
    assert response.json()["results"][0]["original_name"] == filename


def test_compress_download_preview_and_result_metadata():
    response = upload(image_bytes(), filename="photo.png")
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["original_name"] == "photo.png"
    assert result["output_size"] > 0
    assert result["saved_bytes"] == result["original_size"] - result["output_size"]
    expected = result["saved_bytes"] / result["original_size"] * 100
    assert result["saved_percentage"] == round(expected, 2)

    metadata = client.get(f"/api/results/{result['id']}")
    assert metadata.status_code == 200
    assert metadata.json()["output_width"] == 80
    output = client.get(result["download_url"])
    assert output.status_code == 200
    assert output.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(output.content)) as image:
        assert image.format == "WEBP"
    preview = client.get(result["preview_url"])
    assert preview.status_code == 200
    assert "inline" in preview.headers["content-disposition"]
    assert client.delete(f"/api/results/{result['id']}").status_code == 200


def test_reports_when_output_is_larger_than_original():
    response = upload(image_bytes("PNG", (2, 2)), filename="tiny.png", output_format="jpeg")
    result = response.json()["results"][0]
    assert result["output_larger"] is True
    assert result["saved_bytes"] < 0
    assert result["saved_percentage"] < 0


def test_rejects_corrupted_and_mime_mismatched_images():
    corrupted = upload(b"bad image data", filename="bad.png")
    assert corrupted.status_code == 422
    assert "valid" in corrupted.json()["errors"][0]["message"]
    mismatched = upload(image_bytes(), filename="bad.png", content_type="image/jpeg")
    assert mismatched.status_code == 422


def test_rejects_oversized_image():
    data = b"x" * (settings.max_upload_bytes + 1)
    response = upload(data, filename="big.png")
    assert response.status_code == 422
    assert "10 MB" in response.json()["errors"][0]["message"]


def test_resize_and_transparency_via_api():
    response = upload(
        image_bytes(size=(80, 40)),
        output_format="png",
        resize_mode="custom",
        width="20",
        height="20",
    )
    result = response.json()["results"][0]
    assert (result["output_width"], result["output_height"]) == (20, 10)
    output = client.get(result["download_url"])
    with Image.open(BytesIO(output.content)) as image:
        assert image.mode in ("RGBA", "LA", "P")


def test_zip_contains_only_session_outputs_and_is_cleaned():
    first = upload(image_bytes(), filename="first.png").json()["results"][0]
    second = upload(image_bytes("JPEG"), filename="second.jpg", content_type="image/jpeg").json()["results"][0]
    response = client.post(
        "/api/download-zip",
        json={"session_id": SESSION, "result_ids": [first["id"], second["id"]]},
    )
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == sorted([first["output_name"], second["output_name"]])
    assert list(settings.temp_dir.iterdir()) == []


def test_zip_rejects_results_from_other_sessions():
    result = upload(image_bytes()).json()["results"][0]
    response = client.post(
        "/api/download-zip",
        json={"session_id": "different-session-identifier-0001", "result_ids": [result["id"]]},
    )
    assert response.status_code == 404


def test_invalid_result_ids_and_path_traversal_are_not_found():
    assert client.get("/api/results/../../secrets").status_code == 404
    assert client.get("/api/download/../../secrets").status_code == 404
    assert client.delete("/api/results/../../secrets").status_code == 404


def test_session_cleanup_removes_results():
    result = upload(image_bytes()).json()["results"][0]
    response = client.request("DELETE", "/api/session", json={"session_id": SESSION})
    assert response.status_code == 200
    assert response.json()["deleted"] >= 1
    assert client.get(f"/api/results/{result['id']}").status_code == 404
