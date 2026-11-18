# 🖼️ PDF Preprocessor Microservice (Go)

High-performance PDF metadata extraction, deduplication, thumbnail rendering, and **universal visual citation cropping engine** written in Go.

## Features
- **🔍 Universal Visual Source Citations**: High-precision $180\text{ DPI}$ sub-rectangle cropping using Poppler `bbox-layout` and dynamic geometric/typographic analysis. Works on contracts, task sheets, research papers, and resumes with zero domain-specific keyword dictionaries.
- **⚡ Progressive Hydration**: Serves visual snippets asynchronously to the frontend with deterministic MD5 content-addressable disk caching.
- **🖼️ Concurrent Thumbnail Rendering**: Scaled page thumbnails and SHA-256 deduplication hashes generated in parallel using Go worker pools.
- **🚀 Fast Static Delivery**: Serves generated thumbnails and snippets with aggressive browser caching headers.
- **📦 Ultra-lightweight**: Compiles to a self-contained ~25MB Alpine Linux container with `poppler-utils`.

## Full Architecture Documentation
For deep-dive documentation into the layout alignment engine, relative font scaling, boundary crawling, and coordinate translation, see:
👉 **[VISUAL_CITATION_ARCHITECTURE.md](./VISUAL_CITATION_ARCHITECTURE.md)**

## API Endpoints
- `GET /health` — Health check
- `POST /api/preprocess?filename=<filename>` — Generates thumbnails and metadata
- `GET /api/metadata/<filename>` — Returns cached metadata JSON
- `GET /api/snippet/crop?filename=...&page=...&query=...&answer=...&terms=...` — Generates high-res visual citation snippet
- `GET /thumbnails/<filename>/page-<number>.png` — Serves full-page thumbnail
- `GET /thumbnails/<filename>/snippet_p<number>_<hash>.png` — Serves sub-rectangle visual citation snippet

## Running Unit Tests
```bash
cd preprocessor
go test -v ./...
```

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

