package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Port           string
	UploadsDir     string
	ThumbnailsDir  string
	ScaleTo        int
	MaxConcurrency int
}

func loadConfig() Config {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8001"
	}

	uploadsDir := os.Getenv("UPLOADS_DIR")
	if uploadsDir == "" {
		// Smart detection for local dev & docker
		candidates := []string{
			"/uploads",
			"backend/uploads",
			"../backend/uploads",
			"./uploads",
		}
		for _, c := range candidates {
			if info, err := os.Stat(c); err == nil && info.IsDir() {
				uploadsDir = c
				break
			}
		}
		if uploadsDir == "" {
			uploadsDir = "/uploads"
		}
	}

	thumbnailsDir := os.Getenv("THUMBNAILS_DIR")
	if thumbnailsDir == "" {
		thumbnailsDir = "./thumbnails"
	}

	scaleTo := 320
	if s := os.Getenv("THUMBNAIL_SCALE"); s != "" {
		if val, err := strconv.Atoi(s); err == nil && val > 0 {
			scaleTo = val
		}
	}

	concurrency := 4
	if c := os.Getenv("CONCURRENCY"); c != "" {
		if val, err := strconv.Atoi(c); err == nil && val > 0 {
			concurrency = val
		}
	}

	return Config{
		Port:           port,
		UploadsDir:     uploadsDir,
		ThumbnailsDir:  thumbnailsDir,
		ScaleTo:        scaleTo,
		MaxConcurrency: concurrency,
	}
}

// corsMiddleware sets permissive CORS headers for local and Docker access.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func jsonResponse(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func main() {
	cfg := loadConfig()

	// Ensure directories exist
	_ = os.MkdirAll(cfg.UploadsDir, 0755)
	_ = os.MkdirAll(cfg.ThumbnailsDir, 0755)

	mux := http.NewServeMux()

	// Health check
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, http.StatusOK, map[string]any{
			"status":    "ok",
			"service":   "pdf-preprocessor",
			"version":   "1.0.0",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	})

	// Preprocess endpoint
	mux.HandleFunc("POST /api/preprocess", func(w http.ResponseWriter, r *http.Request) {
		filename := r.URL.Query().Get("filename")

		// If filename was not in query params, check JSON body
		if filename == "" && strings.Contains(r.Header.Get("Content-Type"), "application/json") {
			var body struct {
				Filename string `json:"filename"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err == nil {
				filename = body.Filename
			}
		}

		// Or check if a multipart file was uploaded directly
		if filename == "" && strings.HasPrefix(r.Header.Get("Content-Type"), "multipart/form-data") {
			if err := r.ParseMultipartForm(50 << 20); err == nil {
				file, header, err := r.FormFile("file")
				if err == nil {
					defer file.Close()
					filename = header.Filename
					destPath := filepath.Join(cfg.UploadsDir, filename)
					out, err := os.Create(destPath)
					if err == nil {
						defer out.Close()
						_, _ = io.Copy(out, file)
					}
				}
			}
		}

		if filename == "" {
			jsonResponse(w, http.StatusBadRequest, map[string]string{
				"error": "filename parameter or multipart file required",
			})
			return
		}

		pdfPath := filepath.Join(cfg.UploadsDir, filename)
		if _, err := os.Stat(pdfPath); err != nil {
			jsonResponse(w, http.StatusNotFound, map[string]string{
				"error": fmt.Sprintf("PDF file not found in uploads: %s", filename),
			})
			return
		}

		metadata, err := PreprocessPDF(pdfPath, filename, cfg.ThumbnailsDir, cfg.MaxConcurrency, cfg.ScaleTo)
		if err != nil {
			log.Printf("[ERROR] Preprocessing failed for %s: %v", filename, err)
			jsonResponse(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to preprocess PDF: %v", err),
			})
			return
		}

		jsonResponse(w, http.StatusOK, metadata)
	})

	// Metadata lookup endpoint
	mux.HandleFunc("GET /api/metadata/{filename}", func(w http.ResponseWriter, r *http.Request) {
		filename := r.PathValue("filename")
		if filename == "" {
			jsonResponse(w, http.StatusBadRequest, map[string]string{"error": "filename required"})
			return
		}

		metaPath := filepath.Join(cfg.ThumbnailsDir, filename, "metadata.json")
		data, err := os.ReadFile(metaPath)
		if err != nil {
			// Try generating on the fly if PDF exists in uploads
			pdfPath := filepath.Join(cfg.UploadsDir, filename)
			if _, statErr := os.Stat(pdfPath); statErr == nil {
				meta, prepErr := PreprocessPDF(pdfPath, filename, cfg.ThumbnailsDir, cfg.MaxConcurrency, cfg.ScaleTo)
				if prepErr == nil {
					jsonResponse(w, http.StatusOK, meta)
					return
				}
			}
			jsonResponse(w, http.StatusNotFound, map[string]string{"error": "metadata not found"})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(data)
	})

	// Visual snippet cropping endpoint
	mux.HandleFunc("GET /api/snippet/crop", func(w http.ResponseWriter, r *http.Request) {
		filename := r.URL.Query().Get("filename")
		pageStr := r.URL.Query().Get("page")
		query := r.URL.Query().Get("query")
		termsStr := r.URL.Query().Get("terms")

		if filename == "" || pageStr == "" {
			jsonResponse(w, http.StatusBadRequest, map[string]string{
				"error": "filename and page parameters are required",
			})
			return
		}

		pageNum, err := strconv.Atoi(pageStr)
		if err != nil || pageNum <= 0 {
			pageNum = 1
		}

		pdfPath := filepath.Join(cfg.UploadsDir, filename)
		if _, err := os.Stat(pdfPath); err != nil {
			jsonResponse(w, http.StatusNotFound, map[string]string{
				"error": fmt.Sprintf("PDF file not found in uploads: %s", filename),
			})
			return
		}

		// 1. Extract layout
		pageLayout, err := ExtractBBoxLayout(pdfPath, pageNum)
		if err != nil {
			log.Printf("[ERROR] Layout extraction failed for %s p%d: %v", filename, pageNum, err)
			jsonResponse(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to extract layout: %v", err),
			})
			return
		}

		// 2. Parse query, answer, and search terms
		answer := r.URL.Query().Get("answer")
		var terms []string
		if termsStr != "" {
			for _, t := range strings.Split(termsStr, ",") {
				if tr := strings.TrimSpace(t); tr != "" {
					terms = append(terms, tr)
				}
			}
		}

		// 3. Find target section coordinates using universal layout alignment
		x0, y0, x1, y1, found := FindTargetSection(pageLayout, query, answer, terms)
		if !found {
			jsonResponse(w, http.StatusOK, map[string]any{
				"status":  "not_found",
				"message": "No specific focused section matched",
			})
			return
		}

		// 4. Crop image with pdftoppm
		snippetURL, err := CropPDFSnippet(pdfPath, cfg.ThumbnailsDir, filename, pageNum, x0, y0, x1, y1)
		if err != nil {
			log.Printf("[ERROR] Crop failed for %s p%d: %v", filename, pageNum, err)
			jsonResponse(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to crop snippet: %v", err),
			})
			return
		}

		jsonResponse(w, http.StatusOK, map[string]any{
			"status":      "ready",
			"snippet_url": snippetURL,
			"page":        pageNum,
			"box": map[string]float64{
				"x0":     x0,
				"y0":     y0,
				"x1":     x1,
				"y1":     y1,
				"width":  x1 - x0,
				"height": y1 - y0,
			},
		})
	})

	// Thumbnail image serving endpoint
	mux.HandleFunc("GET /thumbnails/{filename}/{pageFile}", func(w http.ResponseWriter, r *http.Request) {
		filename := r.PathValue("filename")
		pageFile := r.PathValue("pageFile")

		if filename == "" || pageFile == "" {
			http.NotFound(w, r)
			return
		}

		filePath := filepath.Join(cfg.ThumbnailsDir, filename, pageFile)

		// If thumbnail doesn't exist, try on-demand rendering
		if _, err := os.Stat(filePath); os.IsNotExist(err) {
			pdfPath := filepath.Join(cfg.UploadsDir, filename)
			if _, statErr := os.Stat(pdfPath); statErr == nil {
				// Parse page number from page-{n}.png
				trimmed := strings.TrimPrefix(pageFile, "page-")
				trimmed = strings.TrimSuffix(trimmed, ".png")
				if pageNum, parseErr := strconv.Atoi(trimmed); parseErr == nil && pageNum > 0 {
					outPrefix := filepath.Join(cfg.ThumbnailsDir, filename, fmt.Sprintf("page-%d", pageNum))
					_ = os.MkdirAll(filepath.Join(cfg.ThumbnailsDir, filename), 0755)
					_ = RenderSinglePage(pdfPath, outPrefix, pageNum, cfg.ScaleTo)
				}
			}
		}

		// Check again
		if _, err := os.Stat(filePath); err != nil {
			http.NotFound(w, r)
			return
		}

		w.Header().Set("Cache-Control", "public, max-age=86400") // Cache for 24h
		w.Header().Set("Content-Type", "image/png")
		http.ServeFile(w, r, filePath)
	})

	addr := ":" + cfg.Port
	log.Printf("🚀 PDF Preprocessor (Go) running on http://0.0.0.0%s", addr)
	log.Printf("📂 Uploads dir: %s | Thumbnails dir: %s", cfg.UploadsDir, cfg.ThumbnailsDir)

	server := &http.Server{
		Addr:         addr,
		Handler:      corsMiddleware(mux),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
	}

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server stopped: %v", err)
	}
}
