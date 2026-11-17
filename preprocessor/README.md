# 🖼️ PDF Preprocessor Microservice (Go)

High-performance PDF metadata extraction, deduplication, and page thumbnail rendering engine written in Go.

## Features
- **SHA-256 Checksum Calculation**: Fast deduplication to prevent re-processing identical files.
- **Concurrent Thumbnail Rendering**: Scaled PNG/WebP page rendering powered by Poppler and Go worker pools.
- **Fast Static Delivery**: Serves generated thumbnails with aggressive 24h browser caching headers.
- **Ultra-lightweight**: Compiles to a ~25MB Alpine Linux container.

## API Endpoints
- `GET /health` — Health check
- `POST /api/preprocess?filename=<filename>` — Generates thumbnails and metadata
- `GET /api/metadata/<filename>` — Returns cached metadata JSON
- `GET /thumbnails/<filename>/page-<number>.png` — Serves the specific page thumbnail

## Running Locally
```bash
cd preprocessor
go run .
```

## Running with Docker
```bash
docker build -t pdf-preprocessor .
docker run -p 8001:8001 -v $(pwd)/../backend/uploads:/uploads pdf-preprocessor
```

