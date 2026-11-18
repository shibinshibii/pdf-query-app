package main

import (
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// Helper to construct a programmatic BBoxPage with realistic typography
func createMockBBoxPage() *BBoxPage {
	page := &BBoxPage{
		Width:  612.0,
		Height: 792.0,
		Flows: []BBoxFlow{
			{
				Blocks: []BBoxBlock{
					// [0] Document Title (Large font: 24pt)
					{
						XMin: 50.0, YMin: 40.0, XMax: 400.0, YMax: 68.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 40.0, XMax: 400.0, YMax: 68.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 40.0, XMax: 150.0, YMax: 68.0, Text: "SYSTEM"},
									{XMin: 160.0, YMin: 40.0, XMax: 400.0, YMax: 68.0, Text: "SPECIFICATION"},
								},
							},
						},
					},
					// [1] Section 1 Heading (Heading font: 16pt)
					{
						XMin: 50.0, YMin: 90.0, XMax: 200.0, YMax: 108.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 90.0, XMax: 200.0, YMax: 108.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 90.0, XMax: 70.0, YMax: 108.0, Text: "1."},
									{XMin: 75.0, YMin: 90.0, XMax: 200.0, YMax: 108.0, Text: "Overview"},
								},
							},
						},
					},
					// [2] Section 1 Body (Body font: 10pt)
					{
						XMin: 50.0, YMin: 115.0, XMax: 550.0, YMax: 145.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 115.0, XMax: 550.0, YMax: 127.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 115.0, XMax: 120.0, YMax: 127.0, Text: "This"},
									{XMin: 125.0, YMin: 115.0, XMax: 220.0, YMax: 127.0, Text: "document"},
									{XMin: 225.0, YMin: 115.0, XMax: 300.0, YMax: 127.0, Text: "outlines"},
									{XMin: 305.0, YMin: 115.0, XMax: 400.0, YMax: 127.0, Text: "the"},
									{XMin: 405.0, YMin: 115.0, XMax: 550.0, YMax: 127.0, Text: "architecture."},
								},
							},
						},
					},
					// [3] Section 2 Heading (Heading font: 16pt)
					{
						XMin: 50.0, YMin: 180.0, XMax: 250.0, YMax: 198.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 180.0, XMax: 250.0, YMax: 198.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 180.0, XMax: 70.0, YMax: 198.0, Text: "2."},
									{XMin: 75.0, YMin: 180.0, XMax: 140.0, YMax: 198.0, Text: "Tech"},
									{XMin: 145.0, YMin: 180.0, XMax: 250.0, YMax: 198.0, Text: "Stack"},
								},
							},
						},
					},
					// [4] Section 2 Bullet 1: Node.js (Body font: 10pt)
					{
						XMin: 70.0, YMin: 205.0, XMax: 300.0, YMax: 217.0,
						Lines: []BBoxLine{
							{
								XMin: 70.0, YMin: 205.0, XMax: 300.0, YMax: 217.0,
								Words: []BBoxWord{
									{XMin: 70.0, YMin: 205.0, XMax: 80.0, YMax: 217.0, Text: "●"},
									{XMin: 85.0, YMin: 205.0, XMax: 160.0, YMax: 217.0, Text: "Node.js"},
									{XMin: 165.0, YMin: 205.0, XMax: 210.0, YMax: 217.0, Text: "and"},
									{XMin: 215.0, YMin: 205.0, XMax: 300.0, YMax: 217.0, Text: "Express"},
								},
							},
						},
					},
					// [5] Section 2 Bullet 2: PostgreSQL (Body font: 10pt)
					{
						XMin: 70.0, YMin: 225.0, XMax: 350.0, YMax: 237.0,
						Lines: []BBoxLine{
							{
								XMin: 70.0, YMin: 225.0, XMax: 350.0, YMax: 237.0,
								Words: []BBoxWord{
									{XMin: 70.0, YMin: 225.0, XMax: 80.0, YMax: 237.0, Text: "●"},
									{XMin: 85.0, YMin: 225.0, XMax: 180.0, YMax: 237.0, Text: "PostgreSQL"},
									{XMin: 185.0, YMin: 225.0, XMax: 240.0, YMax: 237.0, Text: "with"},
									{XMin: 245.0, YMin: 225.0, XMax: 310.0, YMax: 237.0, Text: "Prisma"},
								},
							},
						},
					},
					// [6] Section 2 Bullet 3: FFmpeg (Body font: 10pt)
					{
						XMin: 70.0, YMin: 245.0, XMax: 320.0, YMax: 257.0,
						Lines: []BBoxLine{
							{
								XMin: 70.0, YMin: 245.0, XMax: 320.0, YMax: 257.0,
								Words: []BBoxWord{
									{XMin: 70.0, YMin: 245.0, XMax: 80.0, YMax: 257.0, Text: "●"},
									{XMin: 85.0, YMin: 245.0, XMax: 150.0, YMax: 257.0, Text: "FFmpeg"},
									{XMin: 155.0, YMin: 245.0, XMax: 210.0, YMax: 257.0, Text: "for"},
									{XMin: 215.0, YMin: 245.0, XMax: 320.0, YMax: 257.0, Text: "processing"},
								},
							},
						},
					},
					// [7] Section 3 Heading (Heading font: 16pt)
					{
						XMin: 50.0, YMin: 300.0, XMax: 250.0, YMax: 318.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 300.0, XMax: 250.0, YMax: 318.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 300.0, XMax: 70.0, YMax: 318.0, Text: "3."},
									{XMin: 75.0, YMin: 300.0, XMax: 250.0, YMax: 318.0, Text: "Deployment"},
								},
							},
						},
					},
					// [8] Section 3 Body (Body font: 10pt)
					{
						XMin: 50.0, YMin: 325.0, XMax: 500.0, YMax: 337.0,
						Lines: []BBoxLine{
							{
								XMin: 50.0, YMin: 325.0, XMax: 500.0, YMax: 337.0,
								Words: []BBoxWord{
									{XMin: 50.0, YMin: 325.0, XMax: 120.0, YMax: 337.0, Text: "Deploy"},
									{XMin: 125.0, YMin: 325.0, XMax: 200.0, YMax: 337.0, Text: "using"},
									{XMin: 205.0, YMin: 325.0, XMax: 280.0, YMax: 337.0, Text: "Docker"},
									{XMin: 285.0, YMin: 325.0, XMax: 380.0, YMax: 337.0, Text: "Compose."},
								},
							},
						},
					},
				},
			},
		},
	}
	return page
}

// 1. Portable Unit Test: Typographic Heading Classification
func TestTypographicHeadingDetection(t *testing.T) {
	page := createMockBBoxPage()
	blocks := FlattenAndAnalyzeBlocks(page)

	if len(blocks) != 9 {
		t.Fatalf("Expected 9 blocks, got %d", len(blocks))
	}

	// [0] "SYSTEM SPECIFICATION" -> Title/Heading
	if !blocks[0].IsHeading {
		t.Errorf("Expected block 0 to be marked as heading")
	}
	// [1] "1. Overview" -> Heading
	if !blocks[1].IsHeading {
		t.Errorf("Expected block 1 (1. Overview) to be marked as heading")
	}
	// [2] Body text -> NOT Heading
	if blocks[2].IsHeading {
		t.Errorf("Expected block 2 (body) to NOT be marked as heading")
	}
	// [3] "2. Tech Stack" -> Heading
	if !blocks[3].IsHeading {
		t.Errorf("Expected block 3 (2. Tech Stack) to be marked as heading")
	}
	// [4-6] Bullets -> NOT Heading
	if blocks[4].IsHeading || blocks[5].IsHeading || blocks[6].IsHeading {
		t.Errorf("Expected bullet blocks 4-6 to NOT be marked as heading")
	}
	// [7] "3. Deployment" -> Heading
	if !blocks[7].IsHeading {
		t.Errorf("Expected block 7 (3. Deployment) to be marked as heading")
	}
}

// 2. Portable Unit Test: Section Alignment and Upward Heading Pull
func TestSectionAlignmentAndUpwardHeadingPull(t *testing.T) {
	page := createMockBBoxPage()

	query := "what is the tech stack used in the project?"
	answer := "The project uses Node.js, PostgreSQL with Prisma, and FFmpeg for processing."
	terms := []string{"Node.js", "PostgreSQL", "Prisma", "FFmpeg"}

	x0, y0, x1, y1, found := FindTargetSection(page, query, answer, terms)
	if !found {
		t.Fatalf("Expected section to be found")
	}

	// Expected behavior:
	// - Even though the answer matches bullets [4], [5], [6], the upward crawl MUST include heading [3] ("2. Tech Stack" at YMin=180.0)
	// - The downward crawl MUST clamp cleanly before heading [7] ("3. Deployment" at YMin=300.0)
	if y0 > 175.0 {
		t.Errorf("Expected y0 to include '2. Tech Stack' (y0 <= 175), got y0=%.1f", y0)
	}
	if y1 > 300.0 {
		t.Errorf("Expected y1 to clamp before '3. Deployment' (y1 <= 300), got y1=%.1f", y1)
	}

	// Width must cover the content comfortably
	if (x1 - x0) < 300.0 {
		t.Errorf("Expected crop width >= 300, got %.1f", x1-x0)
	}
}

// 3. Portable Unit Test: Explicit Numbered Section Matching
func TestNumberedSectionConstraint(t *testing.T) {
	page := createMockBBoxPage()

	query := "what is in Section 3?"
	answer := "Section 3 covers deployment using Docker Compose."
	terms := []string{"Deployment", "Docker", "Compose"}

	_, y0, _, y1, found := FindTargetSection(page, query, answer, terms)
	if !found {
		t.Fatalf("Expected Section 3 to be found")
	}

	// Section 3 starts at YMin=300.0
	if y0 < 280.0 || y0 > 305.0 {
		t.Errorf("Expected Section 3 crop around y0 ~ 290-300, got y0=%.1f", y0)
	}
	if y1 < 330.0 {
		t.Errorf("Expected crop to cover Section 3 body text, got y1=%.1f", y1)
	}
}

// 4. Portable Integration Test: Real PDF in testdata/ (skipped if pdftotext is not installed)
func TestRealPDFLayoutExtraction(t *testing.T) {
	if _, err := exec.LookPath("pdftotext"); err != nil {
		t.Skip("pdftotext not installed on this system; skipping real PDF test")
	}

	// Portable relative path inside preprocessor/
	pdfPath := filepath.Join("testdata", "sample_task_sheet.pdf")

	page, err := ExtractBBoxLayout(pdfPath, 1)
	if err != nil {
		t.Fatalf("Failed to extract layout from %s: %v", pdfPath, err)
	}

	query := "what are the strict tech stack requirements?"
	answer := "You must use Node.js, Express.js, PostgreSQL with Prisma or Sequelize, FFmpeg, and Multer."
	terms := []string{"Node.js", "Express.js", "PostgreSQL", "FFmpeg", "Multer"}

	x0, y0, x1, y1, found := FindTargetSection(page, query, answer, terms)
	if !found {
		t.Fatalf("Expected section to be found in %s", pdfPath)
	}

	// Verify that the crop area covers the Tech Stack heading
	blocks := FlattenAndAnalyzeBlocks(page)
	matched := false
	for _, b := range blocks {
		if b.YMin >= y0 && b.YMax <= y1 && strings.Contains(b.Text, "Tech Stack") {
			matched = true
			break
		}
	}
	if !matched {
		t.Errorf("Tech Stack was not found within cropped box (%.1f, %.1f, %.1f, %.1f)", x0, y0, x1, y1)
	}
}
