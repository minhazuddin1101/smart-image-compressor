# Security

## Supported use

Smart Image Compressor is intended for a single user on a trusted Windows computer. Uvicorn binds to `127.0.0.1` by default. Do not change the bind address or expose it through a proxy/firewall as a public service; this app does not provide authentication or multi-user access control.

## Uploaded content

- Files are treated as untrusted. Both the extension and the decoded Pillow format must match; a browser-supplied MIME type is only an additional consistency check.
- Empty, unsupported, corrupted, animated, oversized, and excessive-dimension images are rejected.
- Pillow verification is performed before processing, with decompression-bomb warnings treated as errors and explicit dimension/pixel limits.
- Uploaded originals are held in memory only. They are never executed, rendered as HTML/SVG, or retained in the upload storage directory.
- Processing uses generated server-side identifiers and safe output basenames. Client filenames are never used as filesystem paths.

## Storage and downloads

- Generated images are written only under the configured `storage\processed` directory. Temporary ZIP files are written only under `storage\temp`.
- Result IDs are opaque random tokens. API handlers do not accept paths, and ZIP members use generated safe filenames rather than client-controlled archive paths.
- ZIPs include only explicitly requested results belonging to the supplied session.
- Result files are removed on deletion, when their configured TTL expires, or when the server restarts. An in-progress result download is allowed to finish before its file is removed.
- Do not run `scripts\cleanup.bat` while the app is active. The script refuses cleanup if it detects the default local health endpoint.
- HTTP responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`.

## Reporting a concern

For a security concern, stop using the affected local instance and retain only the minimal information needed to describe the issue. Do not publish private images or other sensitive material in a bug report.
