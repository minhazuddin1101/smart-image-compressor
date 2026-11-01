# Smart Image Compressor

A private, local-first web app for compressing, resizing, comparing, and downloading JPEG, PNG, and WebP images. FastAPI and Pillow process every image on the computer running the app; no image is sent to a cloud service.

## Features

- Drag-and-drop or browse to add up to 10 JPEG, PNG, or WebP images (10 MB each).
- Compare original and optimized previews, dimensions, file sizes, and correctly signed savings.
- Export as JPEG, optimized PNG, or WebP; WebP also supports lossless mode.
- Resize within custom or maximum dimensions while preserving aspect ratio. Enlargement is off unless selected.
- Download results individually or together as a ZIP.
- Remove individual results or clear the current session.
- No accounts, database, external processing service, or permanent original-image storage.

## Technology and requirements

- Python 3.11 
- FastAPI 0.115.12, Uvicorn 0.34.0, Pillow 11.1.0, and python-multipart 0.0.20.
- Pytest 8.3.5 and HTTPX 0.28.1 for tests.
- Modern browser with JavaScript enabled.

The pinned packages support Python 3.11 and Windows. Pillow provides Windows wheels for supported CPython versions. Git is not needed to run the application.

## Installation

Install Python 3.11 alongside any other Python version; the setup does not uninstall or change another Python installation. Open PowerShell in the project directory and run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Or run `scripts\setup.bat` from File Explorer or Command Prompt. It creates the local virtual environment and installs the pinned dependencies. If Python 3.11 is not installed, the script explains what is missing and exits without downloading Python.

The setup script does not replace an existing virtual environment. If `.venv` was created with a different Python version, rename or remove that environment before running setup.

## Start the application

```powershell
.\scripts\start.bat
```

Then open **http://127.0.0.1:8000** in your browser. The server binds to loopback only; it is not exposed to the local network or public internet. Stop it with **Ctrl+C** in the terminal.

Equivalent direct command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If dependencies are missing, `start.bat` prints the exact pip command to restore them. It does not silently install packages.

## Tests

Run the complete test suite using the project environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests create an isolated temporary storage directory and remove it when finished; they do not touch the application's normal storage.

## Configuration

Defaults are safe for a typical desktop computer. Override them with environment variables before starting the server:

| Variable | Default | Description |
|---|---:|---|
| `SIC_MAX_UPLOAD_BYTES` | `10485760` | Maximum bytes per uploaded image |
| `SIC_MAX_BATCH_FILES` | `10` | Maximum files accepted in one API batch |
| `SIC_MAX_IMAGE_PIXELS` | `40000000` | Maximum decoded image pixel count |
| `SIC_MAX_IMAGE_DIMENSION` | `12000` | Maximum image or requested output dimension |
| `SIC_RESULT_TTL_SECONDS` | `86400` | Lifetime of generated results (24 hours) |
| `SIC_STORAGE_DIR` | `storage` in the project | Local storage root |

`.env.example` lists the defaults for reference. It is not automatically loaded; set variables in the process environment or your preferred local shell configuration.

Results are held in memory and generated output files are kept under `storage\processed`. Original uploads are validated and processed in memory and are not saved there. Expired results are removed during API activity and expired orphaned files are cleaned when the app starts. Result records are not persisted, so results from a prior server process cannot be retrieved. ZIP archives use `storage\temp` and are removed after the download completes. Run `scripts\cleanup.bat` while the app is stopped to remove expired generated files and temporary archives.

## Image behavior and limitations

- Input and output formats: JPEG/JPG, PNG, and WebP. Animated WebP is rejected rather than silently flattened.
- JPEG uses Pillow quality, optimization, and progressive encoding. JPEG cannot retain transparency; transparent areas are composited onto white.
- PNG uses lossless optimization and preserves alpha. The quality slider does not affect PNG output.
- WebP uses the quality setting; optional lossless WebP preserves fidelity and transparency.
- Compression does not guarantee a smaller file. If an output is larger, the app reports negative savings honestly.
- EXIF orientation is applied during processing. Other image metadata is not copied to the output.
- Processing is CPU-based, sequential within each batch, and limited to two concurrent image jobs. Extremely large dimensions, pixel counts, or files are rejected.
- There are no accounts or persistent session database. Results are local to the running process and are not available after restart.
- The app is designed for one person on a trusted local computer, not as an internet-facing or multi-user service.

## API

All responses are local. Errors return an HTTP status and a safe message; internal paths and tracebacks are not returned.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Web application |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/config` | Active limits and supported formats |
| `POST` | `/api/compress` | Compress one or more multipart `files` |
| `GET` | `/api/results/{result_id}` | Result metadata and download/preview URLs |
| `GET` | `/api/results/{result_id}/preview` | Inline optimized image preview |
| `GET` | `/api/download/{result_id}` | Download one output |
| `POST` | `/api/download-zip` | Create a ZIP for a session's selected results |
| `DELETE` | `/api/results/{result_id}` | Remove one result |
| `DELETE` | `/api/session` | Remove all results for a session |

`POST /api/compress` accepts multipart form fields `files` (repeated), `session_id` (optional), `output_format` (`jpeg`, `png`, `webp`), `quality` (10–100, default 80), `resize_mode` (`original`, `custom`, `max`), optional integer `width` and `height`, `allow_enlarge` (default false), and `webp_lossless` (default false). Custom/max dimensions fit the image within the supplied bounds while maintaining aspect ratio. At least one bound is required unless mode is `original`.

`POST /api/download-zip` accepts JSON with `session_id` and a list of 1–10 `result_ids`. `DELETE /api/session` accepts JSON with `session_id`. IDs are opaque and generated by the server.

## Project layout

```text
app/
  api/          API routes and response schemas
  core/         Settings and filename/identifier safety
  services/     Image validation, processing, and result storage
  static/       CSS and browser JavaScript
  templates/    HTML page
scripts/        Windows setup, start, and cleanup scripts
storage/        Local uploads, generated results, and temporary ZIPs
tests/          API, image, validation, and security tests
```

## Troubleshooting

- **Python 3.11 not found:** install 64-bit Python 3.11 and make sure the Python launcher (`py`) can find it; existing Python versions can remain installed.
- **Port 8000 is occupied:** stop the other local service or change the `--port` in `scripts\start.bat` and use the matching URL.
- **Browser cannot connect:** confirm the terminal still shows Uvicorn running and visit `http://127.0.0.1:8000`.
- **Upload rejected:** check the file extension and actual image format, ensure the image is not animated, and keep it under the configured byte, pixel, and dimension limits.
- **Setup cannot install packages:** check network access to the configured Python package index, then rerun the pip install command shown above.
