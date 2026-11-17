# Stage 1: Build the Go static binary
FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod ./
COPY *.go ./

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/preprocessor .

# Stage 2: Minimal runtime image with poppler-utils for PDF processing
FROM alpine:3.20

# Install poppler-utils (pdfinfo, pdftoppm) and ca-certificates
RUN apk add --no-cache poppler-utils ca-certificates tzdata wget

WORKDIR /app

COPY --from=builder /app/preprocessor /app/preprocessor

# Default storage directories
RUN mkdir -p /uploads /thumbnails

ENV PORT=8001
ENV UPLOADS_DIR=/uploads
ENV THUMBNAILS_DIR=/thumbnails
ENV THUMBNAIL_SCALE=320
ENV CONCURRENCY=4

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8001/health || exit 1

CMD ["/app/preprocessor"]

