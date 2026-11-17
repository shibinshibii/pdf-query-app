package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
)

// PDFMetadata holds extracted metadata and generated thumbnail references.
type PDFMetadata struct {
	Filename   string   `json:"filename"`
	SHA256     string   `json:"sha256"`
	PageCount  int      `json:"page_count"`
	FileSize   int64    `json:"file_size"`
	Title      string   `json:"title,omitempty"`
	Author     string   `json:"author,omitempty"`
	Thumbnails []string `json:"thumbnails"`
}

// ComputeSHA256 returns the hexadecimal SHA-256 hash of a file.
func ComputeSHA256(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hasher.Sum(nil)), nil
}

// ExtractPDFInfo runs pdfinfo to parse page count and metadata.
func ExtractPDFInfo(pdfPath string) (int, string, string, error) {
	cmd := exec.Command("pdfinfo", pdfPath)
	output, err := cmd.Output()
	if err != nil {
		return 0, "", "", fmt.Errorf("pdfinfo failed: %w", err)
	}

	pageCount := 0
	title := ""
	author := ""

	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])

		switch key {
		case "Pages":
			if p, err := strconv.Atoi(val); err == nil {
				pageCount = p
			}
		case "Title":
			title = val
		case "Author":
			author = val
		}
	}

	if pageCount <= 0 {
		return 0, "", "", fmt.Errorf("could not determine page count from pdfinfo")
	}

	return pageCount, title, author, nil
}

// RenderSinglePage renders a single PDF page into a scaled PNG file.
func RenderSinglePage(pdfPath, outPrefix string, pageNum, scaleTo int) error {
	// pdftoppm -png -scale-to <scaleTo> -f <pageNum> -l <pageNum> -singlefile <pdfPath> <outPrefix>
	cmd := exec.Command(
		"pdftoppm",
		"-png",
		"-scale-to", strconv.Itoa(scaleTo),
		"-f", strconv.Itoa(pageNum),
		"-l", strconv.Itoa(pageNum),
		"-singlefile",
		pdfPath,
		outPrefix,
	)

	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("pdftoppm page %d failed: %w (output: %s)", pageNum, err, string(out))
	}
	return nil
}

// PreprocessPDF calculates hash, extracts metadata, and generates thumbnails concurrently.
func PreprocessPDF(pdfPath, filename, thumbnailsBaseDir string, maxConcurrency, scaleTo int) (*PDFMetadata, error) {
	fileInfo, err := os.Stat(pdfPath)
	if err != nil {
		return nil, fmt.Errorf("file not found: %w", err)
	}

	outDir := filepath.Join(thumbnailsBaseDir, filename)
	if err := os.MkdirAll(outDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create thumbnail dir: %w", err)
	}

	metaFile := filepath.Join(outDir, "metadata.json")

	// Compute hash for deduplication
	hash, err := ComputeSHA256(pdfPath)
	if err != nil {
		return nil, fmt.Errorf("failed to compute hash: %w", err)
	}

	// Check if already processed with matching hash
	if data, err := os.ReadFile(metaFile); err == nil {
		var cached PDFMetadata
		if err := json.Unmarshal(data, &cached); err == nil && cached.SHA256 == hash {
			return &cached, nil
		}
	}

	// Extract page count and metadata
	pageCount, title, author, err := ExtractPDFInfo(pdfPath)
	if err != nil {
		return nil, err
	}

	// Concurrently render page thumbnails using worker pool
	jobs := make(chan int, pageCount)
	errChan := make(chan error, pageCount)
	var wg sync.WaitGroup

	if maxConcurrency <= 0 {
		maxConcurrency = 4
	}

	for w := 0; w < maxConcurrency; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for page := range jobs {
				targetFile := filepath.Join(outDir, fmt.Sprintf("page-%d.png", page))
				// Skip if already generated
				if _, err := os.Stat(targetFile); err == nil {
					continue
				}
				prefix := filepath.Join(outDir, fmt.Sprintf("page-%d", page))
				if err := RenderSinglePage(pdfPath, prefix, page, scaleTo); err != nil {
					errChan <- err
				}
			}
		}()
	}

	for page := 1; page <= pageCount; page++ {
		jobs <- page
	}
	close(jobs)

	wg.Wait()
	close(errChan)

	// Collect any errors
	var renderErrors []string
	for err := range errChan {
		renderErrors = append(renderErrors, err.Error())
	}
	if len(renderErrors) > 0 && len(renderErrors) == pageCount {
		return nil, fmt.Errorf("all page renders failed: %s", strings.Join(renderErrors, "; "))
	}

	// Build thumbnail URLs
	thumbnails := make([]string, 0, pageCount)
	for p := 1; p <= pageCount; p++ {
		thumbnails = append(thumbnails, fmt.Sprintf("/thumbnails/%s/page-%d.png", filename, p))
	}

	result := &PDFMetadata{
		Filename:   filename,
		SHA256:     hash,
		PageCount:  pageCount,
		FileSize:   fileInfo.Size(),
		Title:      title,
		Author:     author,
		Thumbnails: thumbnails,
	}

	// Cache metadata to disk
	if data, err := json.MarshalIndent(result, "", "  "); err == nil {
		_ = os.WriteFile(metaFile, data, 0644)
	}

	return result, nil
}

